"""Encrypted-at-rest Runtime proxy credential storage and resolution."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AccountSecret, RuntimeNetworkConfig, RuntimeNetworkCredential
from app.models.timestamps import utc_now
from app.services.network_secrets import SecretResolver, SecretValue
from app.services.proxy_bridge import BridgeCredentials


class NetworkCredentialError(RuntimeError):
    """A sanitized credential-storage or resolution failure."""


class MasterKeyManager:
    """Load or securely create the installation's non-database master key."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        if not key_path.is_absolute():
            raise NetworkCredentialError("Credential key path must be absolute")

    def load_or_create(self, *, encrypted_credentials_exist: bool) -> bytes:
        try:
            info = self.key_path.lstat()
        except FileNotFoundError:
            if encrypted_credentials_exist:
                raise NetworkCredentialError(
                    "Credential master key is missing for existing encrypted credentials"
                )
            return self._create()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise NetworkCredentialError("Credential master key path is unsafe")
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
            raise NetworkCredentialError("Credential master key permissions are unsafe")
        try:
            descriptor = os.open(
                self.key_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            with os.fdopen(descriptor, "rb") as stream:
                key = stream.read()
            Fernet(key)
        except (OSError, ValueError) as error:
            raise NetworkCredentialError("Credential master key is invalid") from error
        return key

    def _create(self) -> bytes:
        parent = self.key_path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        parent_info = parent.lstat()
        if (
            stat.S_ISLNK(parent_info.st_mode)
            or not stat.S_ISDIR(parent_info.st_mode)
            or parent_info.st_uid != os.getuid()
        ):
            raise NetworkCredentialError("Credential key directory is unsafe")
        os.chmod(parent, 0o700)
        key = Fernet.generate_key()
        try:
            descriptor = os.open(
                self.key_path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
        except FileExistsError:
            return self.load_or_create(encrypted_credentials_exist=False)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(key)
        return key


class NetworkCredentialProvider:
    """Resolve encrypted credentials or temporary legacy environment references."""

    def __init__(
        self,
        key_manager: MasterKeyManager,
        *,
        legacy_resolver: SecretResolver | None = None,
    ) -> None:
        self.key_manager = key_manager
        self.legacy_resolver = legacy_resolver or SecretResolver()

    def resolve(
        self, session: Session, config: RuntimeNetworkConfig
    ) -> BridgeCredentials:
        if config.credential_source == "none":
            return BridgeCredentials()
        if config.credential_source == "environment_reference":
            return BridgeCredentials(
                username=(
                    self.legacy_resolver.resolve(config.proxy_username_secret_ref)
                    if config.proxy_username_secret_ref
                    else None
                ),
                password=(
                    self.legacy_resolver.resolve(config.proxy_password_secret_ref)
                    if config.proxy_password_secret_ref
                    else None
                ),
            )
        if config.credential_source != "stored_encrypted":
            raise NetworkCredentialError("Proxy credential source is unsupported")
        stored = session.get(RuntimeNetworkCredential, config.runtime_id)
        if stored is None or stored.encryption_version != "fernet-v1":
            raise NetworkCredentialError("Stored proxy credentials are unavailable")
        cipher = self._cipher(session)
        try:
            username = cipher.decrypt(stored.encrypted_username).decode("utf-8")
            password = cipher.decrypt(stored.encrypted_password).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise NetworkCredentialError("Stored proxy credentials cannot be decrypted") from error
        return BridgeCredentials(SecretValue(username), SecretValue(password))

    def replace(
        self,
        session: Session,
        runtime_id: int,
        username: SecretValue,
        password: SecretValue,
    ) -> None:
        cipher = self._cipher(session)
        stored = session.get(RuntimeNetworkCredential, runtime_id)
        now = utc_now()
        if stored is None:
            stored = RuntimeNetworkCredential(
                runtime_id=runtime_id,
                encrypted_username=b"pending",
                encrypted_password=b"pending",
                encryption_version="fernet-v1",
                created_at=now,
                updated_at=now,
            )
            session.add(stored)
        stored.encrypted_username = cipher.encrypt(username.reveal().encode("utf-8"))
        stored.encrypted_password = cipher.encrypt(password.reveal().encode("utf-8"))
        stored.encryption_version = "fernet-v1"
        stored.updated_at = now

    @staticmethod
    def clear(session: Session, runtime_id: int) -> None:
        stored = session.get(RuntimeNetworkCredential, runtime_id)
        if stored is not None:
            session.delete(stored)

    def ensure_key(self, session: Session) -> None:
        cipher = self._cipher(session)
        stored = session.scalar(select(RuntimeNetworkCredential).limit(1))
        if stored is None:
            return
        try:
            cipher.decrypt(stored.encrypted_username).decode("utf-8")
            cipher.decrypt(stored.encrypted_password).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise NetworkCredentialError(
                "Credential master key cannot decrypt stored credentials"
            ) from error

    def _cipher(self, session: Session) -> Fernet:
        network_count = session.scalar(
            select(func.count()).select_from(RuntimeNetworkCredential)
        ) or 0
        account_count = session.scalar(
            select(func.count()).select_from(AccountSecret)
        ) or 0
        key = self.key_manager.load_or_create(
            encrypted_credentials_exist=(network_count + account_count) > 0
        )
        try:
            return Fernet(key)
        except ValueError as error:
            raise NetworkCredentialError("Credential master key is invalid") from error
