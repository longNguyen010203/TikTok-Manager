"""Host-administration endpoints for managed Redroid provisioning."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.database import SessionLocal
from app.models import RedroidProvisioning
from app.schemas.redroid_provisioning import (
    RedroidDeprovisioningStatus,
    RedroidProvisioningStatus,
    RedroidProvisionRequest,
)
from app.routers.devices import screen_process_manager
from app.services.redroid_provisioning import (
    DeprovisioningEligibilityError,
    DeprovisioningFailedError,
    ProvisioningAllocationError,
    ProvisioningError,
    ProvisioningFailedError,
    ProvisioningIdempotencyConflict,
    ProvisioningRequest,
    RedroidProvisioningService,
)
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.redroid_provisioning_adapter import (
    ProvisioningConflictError,
    ProvisioningVerificationError,
    RedroidProvisioningAdapter,
)
from app.services.redroid_provisioning_config import (
    ProvisioningConfigurationError,
    RedroidProvisioningSettings,
)

router = APIRouter(prefix="/redroid-provisionings", tags=["redroid-provisionings"])


def get_redroid_provisioning_service() -> RedroidProvisioningService:
    try:
        settings = RedroidProvisioningSettings.from_environment()
    except ProvisioningConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Managed Redroid provisioning is not configured",
        ) from error
    return RedroidProvisioningService(
        SessionLocal,
        RedroidProvisioningAdapter(settings),
        settings,
        screen_manager=screen_process_manager,
        runtime_adapter=RedroidRuntimeAdapter(),
    )


ProvisioningService = Annotated[
    RedroidProvisioningService, Depends(get_redroid_provisioning_service)
]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$",
    ),
]


@router.post(
    "",
    response_model=RedroidProvisioningStatus,
    status_code=status.HTTP_201_CREATED,
    responses={202: {"model": RedroidProvisioningStatus}},
)
def provision_redroid(
    payload: RedroidProvisionRequest,
    response: Response,
    service: ProvisioningService,
    idempotency_key: IdempotencyKey,
) -> RedroidProvisioningStatus:
    request = ProvisioningRequest(
        name=payload.name,
        notes=payload.notes,
        profile=payload.profile,
    )
    try:
        attempt = service.provision(idempotency_key, request)
    except ProvisioningIdempotencyConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ProvisioningFailedError as error:
        attempt = service.get(error.provisioning_id)
        detail = {
            "message": _sanitized_error_message(attempt),
            "provisioning_id": attempt.id,
        }
        if error.stage == "preflight":
            raise HTTPException(status_code=503, detail=detail) from error
        if isinstance(
            error.cause,
            (ProvisioningAllocationError, ProvisioningConflictError, ProvisioningVerificationError),
        ) or attempt.state == "inconsistent":
            raise HTTPException(status_code=409, detail=detail) from error
        raise HTTPException(status_code=500, detail=detail) from error
    except ProvisioningError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if attempt.state == "completed":
        response.status_code = status.HTTP_201_CREATED
    elif attempt.state in {
        "requested", "preflighting", "reserved", "data_created",
        "network_created", "container_created", "inspected", "rolling_back",
        "deprovisioning",
    }:
        response.status_code = status.HTTP_202_ACCEPTED
    elif attempt.state in {"inconsistent", "deprovisioned", "deprovision_failed"}:
        raise HTTPException(
            status_code=409,
            detail={"message": _sanitized_error_message(attempt), "provisioning_id": attempt.id},
        )
    else:
        raise HTTPException(
            status_code=500,
            detail={"message": _sanitized_error_message(attempt), "provisioning_id": attempt.id},
        )
    return _status_response(attempt)


@router.get("/{provisioning_id}", response_model=RedroidProvisioningStatus)
def get_redroid_provisioning(
    provisioning_id: str, service: ProvisioningService
) -> RedroidProvisioningStatus:
    try:
        attempt = service.get(provisioning_id)
    except ProvisioningError as error:
        raise HTTPException(status_code=404, detail="Provisioning attempt not found") from error
    return _status_response(attempt)


@router.post(
    "/{provisioning_id}/deprovision",
    response_model=RedroidDeprovisioningStatus,
    responses={
        202: {"model": RedroidDeprovisioningStatus},
        409: {"model": RedroidDeprovisioningStatus},
    },
)
def deprovision_redroid(
    provisioning_id: str,
    response: Response,
    service: ProvisioningService,
) -> RedroidDeprovisioningStatus:
    try:
        attempt = service.deprovision(provisioning_id)
    except DeprovisioningEligibilityError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except DeprovisioningFailedError as error:
        attempt = service.get(error.provisioning_id)
        response.status_code = status.HTTP_409_CONFLICT
        return _deprovision_status_response(attempt)
    except ProvisioningError as error:
        if str(error) == "Provisioning attempt not found":
            raise HTTPException(
                status_code=404, detail="Provisioning attempt not found"
            ) from error
        raise HTTPException(status_code=500, detail="Deprovisioning failed unexpectedly") from error

    if attempt.state != "deprovisioned":
        response.status_code = status.HTTP_202_ACCEPTED
    return _deprovision_status_response(attempt)


def _status_response(attempt: RedroidProvisioning) -> RedroidProvisioningStatus:
    return RedroidProvisioningStatus(
        provisioning_id=attempt.id,
        state=attempt.state,
        device_number=attempt.device_number,
        container_name=attempt.container_name,
        adb_serial=attempt.adb_serial,
        data_path=attempt.data_path,
        network_name=attempt.network_name,
        image_reference=attempt.image_reference,
        device_id=attempt.device_id,
        runtime_id=attempt.runtime_id,
        data_directory_created=attempt.data_directory_created,
        network_created=attempt.network_created,
        container_created=attempt.container_created,
        error_code=attempt.error_code,
        error_message=_sanitized_error_message(attempt) if attempt.error_code else None,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


def _deprovision_status_response(
    attempt: RedroidProvisioning,
) -> RedroidDeprovisioningStatus:
    return RedroidDeprovisioningStatus(
        provisioning_id=attempt.id,
        state=attempt.state,
        container_removed=attempt.container_removed,
        network_removed=attempt.network_removed,
        data_preserved=attempt.data_preserved,
        data_path=attempt.data_path,
        device_id=attempt.historical_device_id or attempt.device_id,
        runtime_id=attempt.historical_runtime_id or attempt.runtime_id,
        error_code=attempt.error_code,
        error_message=(
            _sanitized_deprovision_error(attempt) if attempt.error_code else None
        ),
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


def _sanitized_error_message(attempt: RedroidProvisioning) -> str:
    messages = {
        "ProvisioningAllocationError": "No safe Redroid allocation is currently available",
        "ProvisioningConflictError": "A required provisioning resource conflicts with existing state",
        "ProvisioningVerificationError": "Provisioned resource configuration is inconsistent",
        "ProvisioningOwnershipError": "Provisioning rollback requires manual recovery",
        "ProvisioningAdapterError": "A required host provisioning operation failed",
    }
    if attempt.state == "rollback_failed":
        return "Provisioning rollback requires manual recovery"
    if attempt.state == "deprovisioned":
        return "This managed Redroid provisioning has been deprovisioned"
    if attempt.state == "deprovision_failed":
        return "Managed Redroid deprovisioning requires recovery"
    return messages.get(attempt.error_code or "", "Provisioning failed unexpectedly")


def _sanitized_deprovision_error(attempt: RedroidProvisioning) -> str:
    if attempt.error_code == "ProvisioningOwnershipError":
        return "Managed resource ownership could not be verified; resources were preserved"
    if attempt.error_code and "Screen" in attempt.error_code:
        return "The tracked device screen could not be closed; resources were preserved"
    if attempt.error_code and "Runtime" in attempt.error_code:
        return "The managed container could not be stopped safely"
    return "Managed Redroid deprovisioning requires recovery"
