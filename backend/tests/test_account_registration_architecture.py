"""Phase 1 registration routing and safety architecture tests."""

import json
from dataclasses import replace

from app.services.account_registration import (
    ACCOUNT_REGISTRATION_V1,
    DEFAULT_REGISTRATION_CALIBRATIONS,
    REGISTRATION_ACTION_BOUNDARIES,
    RegistrationEntryPath,
    RegistrationEntryRouter,
    RegistrationMutationState,
    RegistrationObservation,
    RegistrationScreenCalibration,
    RegistrationUiState,
    RegistrationWorkflowPhase,
    VerificationType,
)
from app.services.workflow_templates import list_workflow_templates


def observation(
    state: RegistrationUiState,
    verification: VerificationType | None = None,
) -> RegistrationObservation:
    return RegistrationObservation(
        account_id=7,
        runtime_id=17,
        device_id=17,
        state=state,
        snapshot_fingerprint="snapshot-safe-fingerprint",
        profile_fingerprint="profile-safe-fingerprint",
        verification_type=verification,
    )


def calibrated_router(*states: RegistrationUiState) -> RegistrationEntryRouter:
    calibrations = dict(DEFAULT_REGISTRATION_CALIBRATIONS)
    for state in states:
        calibrations[state] = RegistrationScreenCalibration(
            state, True, "test live calibration"
        )
    return RegistrationEntryRouter(calibrations)


def test_template_blueprint_is_server_owned_and_not_executable_yet() -> None:
    assert ACCOUNT_REGISTRATION_V1.key == "account_registration"
    assert ACCOUNT_REGISTRATION_V1.required_bindings == (
        "account_id", "runtime_id", "managed_app_id", "managed_app_version_id"
    )
    assert ACCOUNT_REGISTRATION_V1.controller_step_type == "registration.state_machine"
    assert ACCOUNT_REGISTRATION_V1.publicly_executable is False
    assert "account_registration" not in {
        template.key for template in list_workflow_templates()
    }


def test_fresh_device_entry_routes_directly_only_after_calibration() -> None:
    uncalibrated = RegistrationEntryRouter().route(
        observation(RegistrationUiState.LOGIN_OR_SIGNUP)
    )
    assert uncalibrated.entry_path == RegistrationEntryPath.CALIBRATION_REQUIRED
    assert uncalibrated.mutation_allowed is False

    routed = calibrated_router(RegistrationUiState.LOGIN_OR_SIGNUP).route(
        observation(RegistrationUiState.LOGIN_OR_SIGNUP)
    )
    assert routed.entry_path == RegistrationEntryPath.FRESH_DIRECT
    assert routed.phase == RegistrationWorkflowPhase.ENTERING_CANONICAL_FLOW
    assert routed.next_action_key == "registration.choose_signup"
    assert routed.mutation_allowed is False  # Action itself is not calibrated yet.


def test_existing_account_home_uses_distinct_entry_path() -> None:
    routed = RegistrationEntryRouter().route(observation(RegistrationUiState.HOME))
    assert routed.entry_path == RegistrationEntryPath.EXISTING_SESSION
    assert routed.next_action_key == "registration.open_profile"
    assert routed.mutation_allowed is False
    assert routed.waiting_reason == "action_calibration_required"


def test_resume_from_calibrated_intermediate_state_never_replays_entry() -> None:
    routed = calibrated_router(RegistrationUiState.DOB).route(
        observation(RegistrationUiState.DOB)
    )
    assert routed.entry_path == RegistrationEntryPath.RESUME_INTERMEDIATE
    assert routed.phase == RegistrationWorkflowPhase.IN_CANONICAL_FLOW
    assert routed.next_action_key is None
    assert routed.mutation_allowed is False


def test_unknown_state_stops_safely() -> None:
    routed = RegistrationEntryRouter().route(observation(RegistrationUiState.UNKNOWN))
    assert routed.entry_path == RegistrationEntryPath.STOP_UNKNOWN
    assert routed.mutation_allowed is False
    assert routed.waiting_reason == "unknown_screen"


def test_verification_required_is_durable_operator_boundary() -> None:
    routed = RegistrationEntryRouter().route(
        observation(RegistrationUiState.EMAIL_ENTRY, VerificationType.CAPTCHA)
    )
    assert routed.entry_path == RegistrationEntryPath.OPERATOR_REQUIRED
    assert routed.phase == RegistrationWorkflowPhase.VERIFICATION_REQUIRED
    assert routed.waiting_reason == "verification_required"
    assert routed.safe_metadata == {
        "account_id": 7,
        "runtime_id": 17,
        "device_id": 17,
        "screen": "EMAIL_ENTRY",
        "verification_type": "captcha",
    }


def test_safe_job_request_contains_ids_only_and_no_secret() -> None:
    request = RegistrationEntryRouter.job_request(
        workflow_id=101,
        observation=observation(RegistrationUiState.HOME),
        managed_app_id=1,
        ui_profile_id=11,
        action_key="registration.open_profile",
    )
    serialized = json.dumps(request.payload(), sort_keys=True)
    assert request.idempotency_key.startswith("registration:")
    assert set(request.payload()) == {
        "workflow_id", "account_id", "runtime_id", "managed_app_id",
        "ui_profile_id", "action_key",
    }
    for forbidden in ("password", "secret", "credential", "email_password"):
        assert forbidden not in serialized.lower()


def test_restart_recomputes_same_route_and_idempotency_key() -> None:
    router = RegistrationEntryRouter()
    observed = observation(RegistrationUiState.HOME)
    assert router.route(observed) == RegistrationEntryRouter().route(observed)
    first = router.job_request(
        workflow_id=101, observation=observed, managed_app_id=1,
        ui_profile_id=11, action_key="registration.open_profile",
    )
    recovered = RegistrationEntryRouter.job_request(
        workflow_id=101, observation=observed, managed_app_id=1,
        ui_profile_id=11, action_key="registration.open_profile",
    )
    assert first.idempotency_key == recovered.idempotency_key


def test_active_or_completed_mutation_cannot_be_scheduled_twice() -> None:
    actions = tuple(
        replace(item, calibrated=True)
        if item.key == "registration.open_profile" else item
        for item in REGISTRATION_ACTION_BOUNDARIES
    )
    router = RegistrationEntryRouter(actions=actions)
    decision = router.route(observation(RegistrationUiState.HOME))
    assert router.can_schedule_mutation(decision, RegistrationMutationState()) is True
    assert router.can_schedule_mutation(
        decision, RegistrationMutationState(active_job_id=22)
    ) is False
    assert router.can_schedule_mutation(
        decision, RegistrationMutationState(pending_action_key="registration.open_profile")
    ) is False
    assert router.can_schedule_mutation(
        decision,
        RegistrationMutationState(completed_action_keys=("registration.open_profile",)),
    ) is False


def test_secret_consuming_boundaries_are_single_attempt_and_not_calibrated() -> None:
    password = next(
        item for item in REGISTRATION_ACTION_BOUNDARIES
        if item.key == "registration.enter_password"
    )
    assert password.required_secret_type == "account_password"
    assert password.max_attempts_after_mutation == 1
    assert password.calibrated is False
