"""Write-only encrypted Account secret boundary."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccountSecret, RuntimeNetworkCredential
from app.models.timestamps import utc_now
from app.services.network_credentials import MasterKeyManager, NetworkCredentialError


class AccountSecretError(RuntimeError):
    """Sanitized account-secret storage failure."""


class AccountSecretProvider:
    """Encrypt, replace, remove, and startup-validate Account credentials."""

    def __init__(self, key_manager: MasterKeyManager) -> None:
        self.key_manager = key_manager

    def replace(
        self, session: Session, account_id: int, secret_type: str, value: str
    ) -> AccountSecret:
        try:
            cipher = self._cipher(session)
        except NetworkCredentialError as error:
            raise AccountSecretError("Account secret encryption is unavailable") from error
        stored = session.scalar(
            select(AccountSecret).where(
                AccountSecret.account_id == account_id,
                AccountSecret.secret_type == secret_type,
            )
        )
        now = utc_now()
        if stored is None:
            stored = AccountSecret(
                account_id=account_id,
                secret_type=secret_type,
                encrypted_value=b"pending",
                encryption_version="fernet-v1",
                created_at=now,
                updated_at=now,
            )
            session.add(stored)
        stored.encrypted_value = cipher.encrypt(value.encode("utf-8"))
        stored.encryption_version = "fernet-v1"
        stored.updated_at = now
        return stored

    @staticmethod
    def clear(session: Session, account_id: int, secret_type: str) -> bool:
        stored = session.scalar(
            select(AccountSecret).where(
                AccountSecret.account_id == account_id,
                AccountSecret.secret_type == secret_type,
            )
        )
        if stored is None:
            return False
        session.delete(stored)
        return True

    def ensure_key(self, session: Session) -> None:
        try:
            cipher = self._cipher(session)
        except NetworkCredentialError as error:
            raise AccountSecretError("Account secret encryption is unavailable") from error
        stored = session.scalar(select(AccountSecret).limit(1))
        if stored is None:
            return
        try:
            cipher.decrypt(stored.encrypted_value).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise AccountSecretError(
                "Credential master key cannot decrypt stored account secrets"
            ) from error

    def _cipher(self, session: Session) -> Fernet:
        account_count = session.scalar(select(func.count()).select_from(AccountSecret)) or 0
        network_count = session.scalar(
            select(func.count()).select_from(RuntimeNetworkCredential)
        ) or 0
        key = self.key_manager.load_or_create(
            encrypted_credentials_exist=(account_count + network_count) > 0
        )
        return Fernet(key)
