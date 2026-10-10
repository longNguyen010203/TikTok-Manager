"""Manual Account registration transitions and downstream readiness policy."""

from fastapi import HTTPException, status

from app.models import Account
from app.models.timestamps import utc_now
from app.schemas.account import AccountRegistrationComplete


USABLE_ACCOUNT_STATUSES = frozenset({"active"})


def registration_ready(account: Account) -> bool:
    """Return whether an Account is safe to select for downstream automation."""
    return (
        account.registration_state == "registered"
        and account.runtime_id is not None
        and account.runtime is not None
        and account.archived_at is None
        and account.status in USABLE_ACCOUNT_STATUSES
    )


def require_manual_completion_eligible(account: Account) -> None:
    """Validate invariants required before an operator can mark registration done."""
    if account.archived_at is not None or account.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived Account cannot be marked registered",
        )
    if account.runtime_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime assignment is required",
        )
    if account.runtime is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assigned Runtime not found",
        )


def complete_manual_registration(
    account: Account, payload: AccountRegistrationComplete
) -> None:
    """Apply one safe, idempotent operator-completion transition."""
    require_manual_completion_eligible(account)
    fields_set = payload.model_fields_set
    if "username" in fields_set:
        account.username = payload.username
    if "display_name" in fields_set:
        assert payload.display_name is not None
        account.display_name = payload.display_name
        account.name = payload.display_name
    if "notes" in fields_set:
        account.notes = payload.notes
    account.registration_state = "registered"
    account.status_reason = None
    account.registration_completed_at = account.registration_completed_at or utc_now()


def fail_manual_registration(account: Account, reason: str) -> None:
    """Record a bounded operator-visible registration failure."""
    if account.archived_at is not None or account.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived Account registration cannot be changed",
        )
    account.registration_state = "failed"
    account.status_reason = reason
    account.registration_completed_at = None


def reopen_manual_registration(account: Account) -> None:
    """Intentionally restart a completed or failed operator registration."""
    if account.archived_at is not None or account.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived Account registration cannot be changed",
        )
    if account.registration_state not in {"registered", "failed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only registered or failed Account registration can be reopened",
        )
    account.registration_state = "pending"
    account.status_reason = None
    account.registration_completed_at = None
