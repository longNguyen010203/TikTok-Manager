"""State-driven Account registration architecture and calibration gate.

Phase 1 deliberately exposes no executable Job or public Workflow template.
Only HOME is backed by a live-calibrated TIK-024 screen. Registration screen
names below are candidate semantic states and cannot authorize UI mutation
until a later immutable UI profile marks them calibrated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class RegistrationUiState(str, Enum):
    UNKNOWN = "UNKNOWN"
    HOME = "HOME"
    PROFILE = "PROFILE"
    REGISTRATION_ENTRY = "REGISTRATION_ENTRY"
    LOGIN_OR_SIGNUP = "LOGIN_OR_SIGNUP"
    SIGNUP_METHOD = "SIGNUP_METHOD"
    DOB = "DOB"
    EMAIL_OR_PHONE = "EMAIL_OR_PHONE"
    EMAIL_ENTRY = "EMAIL_ENTRY"
    PASSWORD_ENTRY = "PASSWORD_ENTRY"
    USERNAME_ENTRY = "USERNAME_ENTRY"
    REGISTRATION_REVIEW = "REGISTRATION_REVIEW"
    REGISTRATION_COMPLETE = "REGISTRATION_COMPLETE"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"


class RegistrationWorkflowPhase(str, Enum):
    DETECTING_ENTRY = "detecting_entry"
    ROUTING_ENTRY = "routing_entry"
    ENTERING_CANONICAL_FLOW = "entering_canonical_flow"
    IN_CANONICAL_FLOW = "in_canonical_flow"
    VERIFICATION_REQUIRED = "verification_required"
    COMPLETED = "completed"
    TERMINAL_FAILED = "terminal_failed"


class RegistrationEntryPath(str, Enum):
    FRESH_DIRECT = "fresh_direct"
    EXISTING_SESSION = "existing_session"
    RESUME_INTERMEDIATE = "resume_intermediate"
    OPERATOR_REQUIRED = "operator_required"
    CALIBRATION_REQUIRED = "calibration_required"
    STOP_UNKNOWN = "stop_unknown"


class VerificationType(str, Enum):
    CAPTCHA = "captcha"
    OTP = "otp"
    EMAIL_VERIFICATION = "email_verification"
    SMS_VERIFICATION = "sms_verification"
    SUSPICIOUS_LOGIN = "suspicious_login"
    IDENTITY_CHALLENGE = "identity_challenge"
    UNKNOWN_CHALLENGE = "unknown_challenge"


@dataclass(frozen=True)
class RegistrationScreenCalibration:
    state: RegistrationUiState
    calibrated: bool
    source: str


@dataclass(frozen=True)
class RegistrationActionBoundary:
    key: str
    source_states: tuple[RegistrationUiState, ...]
    target_states: tuple[RegistrationUiState, ...]
    mutates_ui: bool
    required_secret_type: str | None = None
    max_attempts_after_mutation: int = 1
    calibrated: bool = False


@dataclass(frozen=True)
class RegistrationTemplateBlueprint:
    key: str
    version: int
    label: str
    required_bindings: tuple[str, ...]
    controller_step_type: str
    publicly_executable: bool


ACCOUNT_REGISTRATION_V1 = RegistrationTemplateBlueprint(
    key="account_registration",
    version=1,
    label="Account Registration",
    required_bindings=(
        "account_id",
        "runtime_id",
        "managed_app_id",
        "managed_app_version_id",
    ),
    controller_step_type="registration.state_machine",
    publicly_executable=False,
)


_DEFAULT_CALIBRATIONS = {
    state: RegistrationScreenCalibration(
        state=state,
        calibrated=state == RegistrationUiState.HOME,
        source=("TIK-024 Trill 44.4.3 HOME profile" if state == RegistrationUiState.HOME else "awaiting live calibration"),
    )
    for state in RegistrationUiState
}
DEFAULT_REGISTRATION_CALIBRATIONS: Mapping[
    RegistrationUiState, RegistrationScreenCalibration
] = MappingProxyType(_DEFAULT_CALIBRATIONS)


REGISTRATION_ACTION_BOUNDARIES: tuple[RegistrationActionBoundary, ...] = (
    RegistrationActionBoundary(
        "registration.detect_entry",
        tuple(RegistrationUiState),
        tuple(RegistrationUiState),
        mutates_ui=False,
    ),
    RegistrationActionBoundary(
        "registration.open_profile",
        (RegistrationUiState.HOME,),
        (RegistrationUiState.PROFILE,),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.open_add_account",
        (RegistrationUiState.PROFILE,),
        (RegistrationUiState.REGISTRATION_ENTRY, RegistrationUiState.LOGIN_OR_SIGNUP),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.choose_signup",
        (RegistrationUiState.REGISTRATION_ENTRY, RegistrationUiState.LOGIN_OR_SIGNUP),
        (RegistrationUiState.SIGNUP_METHOD,),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.enter_dob",
        (RegistrationUiState.DOB,),
        (RegistrationUiState.EMAIL_OR_PHONE,),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.choose_email",
        (RegistrationUiState.EMAIL_OR_PHONE,),
        (RegistrationUiState.EMAIL_ENTRY,),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.enter_email",
        (RegistrationUiState.EMAIL_ENTRY,),
        (RegistrationUiState.PASSWORD_ENTRY, RegistrationUiState.VERIFICATION_REQUIRED),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.enter_password",
        (RegistrationUiState.PASSWORD_ENTRY,),
        (RegistrationUiState.USERNAME_ENTRY, RegistrationUiState.REGISTRATION_REVIEW),
        mutates_ui=True,
        required_secret_type="account_password",
    ),
    RegistrationActionBoundary(
        "registration.enter_username",
        (RegistrationUiState.USERNAME_ENTRY,),
        (RegistrationUiState.REGISTRATION_REVIEW,),
        mutates_ui=True,
    ),
    RegistrationActionBoundary(
        "registration.confirm_complete",
        (RegistrationUiState.REGISTRATION_REVIEW,),
        (RegistrationUiState.REGISTRATION_COMPLETE, RegistrationUiState.VERIFICATION_REQUIRED),
        mutates_ui=True,
    ),
)

CANONICAL_CONVERGENCE_STATE = RegistrationUiState.SIGNUP_METHOD
_FRESH_ENTRY_STATES = {
    RegistrationUiState.REGISTRATION_ENTRY,
    RegistrationUiState.LOGIN_OR_SIGNUP,
    RegistrationUiState.SIGNUP_METHOD,
}
_INTERMEDIATE_STATES = {
    RegistrationUiState.DOB,
    RegistrationUiState.EMAIL_OR_PHONE,
    RegistrationUiState.EMAIL_ENTRY,
    RegistrationUiState.PASSWORD_ENTRY,
    RegistrationUiState.USERNAME_ENTRY,
    RegistrationUiState.REGISTRATION_REVIEW,
}


@dataclass(frozen=True)
class RegistrationObservation:
    account_id: int
    runtime_id: int
    device_id: int
    state: RegistrationUiState
    snapshot_fingerprint: str
    profile_fingerprint: str
    verification_type: VerificationType | None = None

    def __post_init__(self) -> None:
        if min(self.account_id, self.runtime_id, self.device_id) <= 0:
            raise ValueError("Registration bindings must be positive identifiers")
        if not self.snapshot_fingerprint or not self.profile_fingerprint:
            raise ValueError("Registration observation fingerprints are required")


@dataclass(frozen=True)
class RegistrationRouteDecision:
    phase: RegistrationWorkflowPhase
    entry_path: RegistrationEntryPath
    observed_state: RegistrationUiState
    next_action_key: str | None
    mutation_allowed: bool
    waiting_reason: str | None
    safe_metadata: Mapping[str, object]


@dataclass(frozen=True)
class RegistrationMutationState:
    active_job_id: int | None = None
    pending_action_key: str | None = None
    completed_action_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class RegistrationJobRequest:
    """Safe IDs-only request projection for a future typed action Job."""

    workflow_id: int
    account_id: int
    runtime_id: int
    managed_app_id: int
    ui_profile_id: int
    action_key: str
    idempotency_key: str

    def payload(self) -> dict[str, int | str]:
        return {
            "workflow_id": self.workflow_id,
            "account_id": self.account_id,
            "runtime_id": self.runtime_id,
            "managed_app_id": self.managed_app_id,
            "ui_profile_id": self.ui_profile_id,
            "action_key": self.action_key,
        }


class RegistrationEntryRouter:
    def __init__(
        self,
        calibrations: Mapping[
            RegistrationUiState, RegistrationScreenCalibration
        ] = DEFAULT_REGISTRATION_CALIBRATIONS,
        actions: tuple[RegistrationActionBoundary, ...] = REGISTRATION_ACTION_BOUNDARIES,
    ) -> None:
        self.calibrations = calibrations
        self.actions = {item.key: item for item in actions}

    def route(self, observation: RegistrationObservation) -> RegistrationRouteDecision:
        metadata: dict[str, object] = {
            "account_id": observation.account_id,
            "runtime_id": observation.runtime_id,
            "device_id": observation.device_id,
            "screen": observation.state.value,
        }
        if observation.verification_type is not None or observation.state == RegistrationUiState.VERIFICATION_REQUIRED:
            verification = observation.verification_type or VerificationType.UNKNOWN_CHALLENGE
            metadata["verification_type"] = verification.value
            return RegistrationRouteDecision(
                RegistrationWorkflowPhase.VERIFICATION_REQUIRED,
                RegistrationEntryPath.OPERATOR_REQUIRED,
                observation.state,
                None,
                False,
                "verification_required",
                MappingProxyType(metadata),
            )
        if observation.state == RegistrationUiState.UNKNOWN:
            return RegistrationRouteDecision(
                RegistrationWorkflowPhase.DETECTING_ENTRY,
                RegistrationEntryPath.STOP_UNKNOWN,
                observation.state,
                None,
                False,
                "unknown_screen",
                MappingProxyType(metadata),
            )
        calibration = self.calibrations.get(observation.state)
        if calibration is None or not calibration.calibrated:
            return RegistrationRouteDecision(
                RegistrationWorkflowPhase.ROUTING_ENTRY,
                RegistrationEntryPath.CALIBRATION_REQUIRED,
                observation.state,
                None,
                False,
                "screen_calibration_required",
                MappingProxyType(metadata),
            )
        if observation.state in {RegistrationUiState.HOME, RegistrationUiState.PROFILE}:
            action_key = (
                "registration.open_profile"
                if observation.state == RegistrationUiState.HOME
                else "registration.open_add_account"
            )
            return self._action_decision(
                observation,
                RegistrationWorkflowPhase.ENTERING_CANONICAL_FLOW,
                RegistrationEntryPath.EXISTING_SESSION,
                action_key,
                metadata,
            )
        if observation.state in _FRESH_ENTRY_STATES:
            action_key = None if observation.state == CANONICAL_CONVERGENCE_STATE else "registration.choose_signup"
            return self._action_decision(
                observation,
                RegistrationWorkflowPhase.ENTERING_CANONICAL_FLOW,
                RegistrationEntryPath.FRESH_DIRECT,
                action_key,
                metadata,
            )
        if observation.state in _INTERMEDIATE_STATES:
            return RegistrationRouteDecision(
                RegistrationWorkflowPhase.IN_CANONICAL_FLOW,
                RegistrationEntryPath.RESUME_INTERMEDIATE,
                observation.state,
                None,
                False,
                "typed_action_calibration_required",
                MappingProxyType(metadata),
            )
        if observation.state == RegistrationUiState.REGISTRATION_COMPLETE:
            return RegistrationRouteDecision(
                RegistrationWorkflowPhase.COMPLETED,
                RegistrationEntryPath.RESUME_INTERMEDIATE,
                observation.state,
                None,
                False,
                None,
                MappingProxyType(metadata),
            )
        return RegistrationRouteDecision(
            RegistrationWorkflowPhase.DETECTING_ENTRY,
            RegistrationEntryPath.STOP_UNKNOWN,
            observation.state,
            None,
            False,
            "unsupported_screen",
            MappingProxyType(metadata),
        )

    def can_schedule_mutation(
        self,
        decision: RegistrationRouteDecision,
        durable_state: RegistrationMutationState,
    ) -> bool:
        action_key = decision.next_action_key
        return bool(
            decision.mutation_allowed
            and action_key
            and durable_state.active_job_id is None
            and durable_state.pending_action_key is None
            and action_key not in durable_state.completed_action_keys
        )

    @staticmethod
    def job_request(
        *,
        workflow_id: int,
        observation: RegistrationObservation,
        managed_app_id: int,
        ui_profile_id: int,
        action_key: str,
    ) -> RegistrationJobRequest:
        identity = {
            "workflow_id": workflow_id,
            "account_id": observation.account_id,
            "runtime_id": observation.runtime_id,
            "managed_app_id": managed_app_id,
            "ui_profile_id": ui_profile_id,
            "action_key": action_key,
            "snapshot_fingerprint": observation.snapshot_fingerprint,
        }
        digest = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return RegistrationJobRequest(
            workflow_id=workflow_id,
            account_id=observation.account_id,
            runtime_id=observation.runtime_id,
            managed_app_id=managed_app_id,
            ui_profile_id=ui_profile_id,
            action_key=action_key,
            idempotency_key=f"registration:{digest}",
        )

    def _action_decision(
        self,
        observation: RegistrationObservation,
        phase: RegistrationWorkflowPhase,
        path: RegistrationEntryPath,
        action_key: str | None,
        metadata: dict[str, object],
    ) -> RegistrationRouteDecision:
        action = self.actions.get(action_key) if action_key else None
        mutation_allowed = bool(action and action.calibrated)
        return RegistrationRouteDecision(
            phase,
            path,
            observation.state,
            action_key,
            mutation_allowed,
            None if mutation_allowed or action_key is None else "action_calibration_required",
            MappingProxyType(metadata),
        )
