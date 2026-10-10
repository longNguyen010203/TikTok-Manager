"""Canonical Account Registry CRUD, assignment, query, and secret endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import load_application_config
from app.database import get_db
from app.models import Account, AccountTag, Runtime
from app.models.timestamps import utc_now
from app.schemas.account import (
    AccountCreate,
    AccountList,
    AccountRead,
    AccountRegistrationComplete,
    AccountRegistrationFailure,
    AccountRuntimeAssignment,
    AccountSecretMetadata,
    AccountSecretType,
    AccountSecretWrite,
    AccountUpdate,
)
from app.services.account_registration_lifecycle import (
    complete_manual_registration,
    fail_manual_registration,
    registration_ready,
    reopen_manual_registration,
    require_manual_completion_eligible,
)
from app.services.account_secrets import AccountSecretError, AccountSecretProvider
from app.services.network_credentials import MasterKeyManager

router = APIRouter(prefix="/accounts", tags=["accounts"])
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_account_secret_provider() -> AccountSecretProvider:
    config = load_application_config()
    return AccountSecretProvider(MasterKeyManager(config.credential_key_path))


SecretProvider = Annotated[AccountSecretProvider, Depends(get_account_secret_provider)]


def _account_options():
    return (
        selectinload(Account.tags),
        selectinload(Account.secrets),
        selectinload(Account.runtime),
    )


def _get_account_or_404(
    account_id: int, session: Session, *, include_archived: bool = False
) -> Account:
    account = session.scalar(
        select(Account).options(*_account_options()).where(Account.id == account_id)
    )
    if account is None or (account.archived_at is not None and not include_archived):
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _validate_runtime_id(runtime_id: int | None, session: Session) -> None:
    if runtime_id is not None and session.get(Runtime, runtime_id) is None:
        raise HTTPException(status_code=404, detail="Runtime not found")


def _read(account: Account) -> AccountRead:
    secret_types = sorted(secret.secret_type for secret in account.secrets)
    return AccountRead(
        id=account.id,
        name=account.name,
        display_name=account.display_name or account.name,
        username=account.username,
        email=account.email,
        phone=account.phone,
        platform=account.platform,
        status=account.status,
        registration_state=account.registration_state,
        registration_ready=registration_ready(account),
        registration_completed_at=account.registration_completed_at,
        health_status=account.health_status,
        status_reason=account.status_reason,
        niche=account.niche,
        notes=account.notes,
        tags=sorted(tag.tag for tag in account.tags),
        runtime_id=account.runtime_id,
        device_id=account.runtime.device_id if account.runtime is not None else None,
        follower_count=account.follower_count,
        following_count=account.following_count,
        likes_count=account.likes_count,
        video_count=account.video_count,
        metrics_updated_at=account.metrics_updated_at,
        secret_present=bool(secret_types),
        secret_types=secret_types,  # type: ignore[arg-type]
        created_at=account.created_at,
        updated_at=account.updated_at,
        archived_at=account.archived_at,
    )


def _replace_tags(account: Account, tags: list[str]) -> None:
    account.tags[:] = [AccountTag(tag=tag) for tag in tags]


@router.get("", response_model=AccountList)
def list_accounts(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    account_status: Annotated[str | None, Query(alias="status", min_length=1)] = None,
    niche: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    runtime_id: Annotated[int | None, Query(gt=0)] = None,
    device_id: Annotated[int | None, Query(gt=0)] = None,
    tag: Annotated[str | None, Query(min_length=1, max_length=50)] = None,
    query: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    include_archived: bool = False,
) -> AccountList:
    """Search and filter Accounts before deterministic newest-first pagination."""
    filters = []
    if not include_archived:
        filters.append(Account.archived_at.is_(None))
    if account_status is not None:
        filters.append(Account.status == account_status)
    if niche is not None:
        filters.append(func.lower(Account.niche) == niche.strip().lower())
    if runtime_id is not None:
        filters.append(Account.runtime_id == runtime_id)
    if device_id is not None:
        filters.append(Account.runtime.has(Runtime.device_id == device_id))
    if tag is not None:
        filters.append(Account.tags.any(AccountTag.tag == " ".join(tag.lower().split())))
    if query is not None:
        needle = query.strip()
        filters.append(
            or_(
                Account.name.contains(needle, autoescape=True),
                Account.display_name.contains(needle, autoescape=True),
                Account.username.contains(needle, autoescape=True),
                Account.email.contains(needle, autoescape=True),
                Account.niche.contains(needle, autoescape=True),
            )
        )

    total = session.scalar(select(func.count()).select_from(Account).where(*filters))
    accounts = session.scalars(
        select(Account)
        .options(*_account_options())
        .where(*filters)
        .order_by(Account.created_at.desc(), Account.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AccountList(
        items=[_read(account) for account in accounts],
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: int, session: DatabaseSession) -> AccountRead:
    return _read(_get_account_or_404(account_id, session))


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, session: DatabaseSession) -> AccountRead:
    _validate_runtime_id(payload.runtime_id, session)
    data = payload.model_dump(exclude={"tags", "name", "display_name"})
    display_name = payload.display_name or payload.name
    assert display_name is not None
    account = Account(name=display_name, display_name=display_name, **data)
    if account.registration_state == "registered":
        # Preserve the original create contract while applying the same safety
        # invariant as the explicit completion endpoint.
        account.runtime = session.get(Runtime, account.runtime_id)
        require_manual_completion_eligible(account)
        account.registration_completed_at = utc_now()
    _replace_tags(account, payload.tags)
    session.add(account)
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.patch("/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int, payload: AccountUpdate, session: DatabaseSession
) -> AccountRead:
    account = _get_account_or_404(account_id, session, include_archived=True)
    update_data = payload.model_dump(
        exclude_unset=True, exclude={"tags", "name", "display_name"}
    )
    if "runtime_id" in update_data:
        _validate_runtime_id(update_data["runtime_id"], session)
    if "display_name" in payload.model_fields_set or "name" in payload.model_fields_set:
        display_name = payload.display_name or payload.name
        assert display_name is not None
        account.display_name = display_name
        account.name = display_name
    if payload.tags is not None:
        _replace_tags(account, payload.tags)
    for field, value in update_data.items():
        setattr(account, field, value)
    if "status" in update_data:
        if update_data["status"] == "archived":
            account.archived_at = account.archived_at or utc_now()
        elif account.archived_at is not None:
            account.archived_at = None
    if (
        "registration_state" in update_data
        and account.registration_state == "registered"
    ):
        # Legacy PATCH support remains compatible, but cannot bypass the
        # canonical registration-completion invariants.
        if account.runtime_id is not None:
            account.runtime = session.get(Runtime, account.runtime_id)
        require_manual_completion_eligible(account)
        account.status_reason = None
        account.registration_completed_at = (
            account.registration_completed_at or utc_now()
        )
    elif (
        "registration_state" in update_data
        and account.registration_state != "registered"
    ):
        account.registration_completed_at = None
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session, include_archived=True))


@router.put("/{account_id}/runtime", response_model=AccountRead)
def assign_runtime(
    account_id: int, payload: AccountRuntimeAssignment, session: DatabaseSession
) -> AccountRead:
    account = _get_account_or_404(account_id, session)
    _validate_runtime_id(payload.runtime_id, session)
    account.runtime_id = payload.runtime_id
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.delete("/{account_id}/runtime", response_model=AccountRead)
def unassign_runtime(account_id: int, session: DatabaseSession) -> AccountRead:
    account = _get_account_or_404(account_id, session)
    account.runtime_id = None
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.post("/{account_id}/registration/complete", response_model=AccountRead)
def complete_account_registration(
    account_id: int,
    payload: AccountRegistrationComplete,
    session: DatabaseSession,
) -> AccountRead:
    account = _get_account_or_404(account_id, session)
    complete_manual_registration(account, payload)
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.post("/{account_id}/registration/fail", response_model=AccountRead)
def fail_account_registration(
    account_id: int,
    payload: AccountRegistrationFailure,
    session: DatabaseSession,
) -> AccountRead:
    account = _get_account_or_404(account_id, session)
    fail_manual_registration(account, payload.reason)
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.post("/{account_id}/registration/reopen", response_model=AccountRead)
def reopen_account_registration(
    account_id: int, session: DatabaseSession
) -> AccountRead:
    account = _get_account_or_404(account_id, session)
    reopen_manual_registration(account)
    session.commit()
    session.expire_all()
    return _read(_get_account_or_404(account.id, session))


@router.get("/{account_id}/secrets", response_model=list[AccountSecretMetadata])
def list_account_secrets(
    account_id: int, session: DatabaseSession
) -> list[AccountSecretMetadata]:
    account = _get_account_or_404(account_id, session)
    return [
        AccountSecretMetadata(
            secret_type=secret.secret_type,  # type: ignore[arg-type]
            present=True,
            updated_at=secret.updated_at,
        )
        for secret in sorted(account.secrets, key=lambda item: item.secret_type)
    ]


@router.put("/{account_id}/secrets/{secret_type}", response_model=AccountSecretMetadata)
def put_account_secret(
    account_id: int,
    secret_type: AccountSecretType,
    payload: AccountSecretWrite,
    session: DatabaseSession,
    provider: SecretProvider,
) -> AccountSecretMetadata:
    _get_account_or_404(account_id, session)
    try:
        stored = provider.replace(
            session, account_id, secret_type, payload.value.get_secret_value()
        )
        session.commit()
    except AccountSecretError as error:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Account secret storage is unavailable",
        ) from error
    return AccountSecretMetadata(
        secret_type=secret_type, present=True, updated_at=stored.updated_at
    )


@router.delete(
    "/{account_id}/secrets/{secret_type}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_account_secret(
    account_id: int, secret_type: AccountSecretType, session: DatabaseSession
) -> Response:
    _get_account_or_404(account_id, session)
    AccountSecretProvider.clear(session, account_id, secret_type)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, session: DatabaseSession) -> Response:
    """Soft-archive an Account while preserving all historical references."""
    account = _get_account_or_404(account_id, session)
    account.status = "archived"
    account.archived_at = utc_now()
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
