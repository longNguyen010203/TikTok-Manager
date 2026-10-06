"""Convergence-based managed APK installation for one exact Runtime."""

from __future__ import annotations

from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ContentAssetVersion, ContentBlob, ManagedApp, ManagedAppVersion
from app.services.adb_executor import AdbExecutor, AdbExecutorError, AdbInstalledPackage
from app.services.android_automation import (
    AutomationReadinessService,
    RuntimeTarget,
    RuntimeTargetResolver,
    ScreenSessionInspector,
)
from app.services.automation_errors import AutomationError
from app.services.content_storage import ContentStorageError, ContentStorageService
from app.services.redroid_runtime import RedroidRuntimeAdapter
from app.services.runtime_operation_lock import RuntimeOperationGuard, RuntimeOperationLockBusy


_MESSAGES = {
    "APP_NOT_INSTALLED": "Managed application is not installed",
    "APP_PACKAGE_MISMATCH": "Installed package does not match the managed application",
    "APP_BASIC_UPDATE_REQUIRES_VERIFIED": "Updating an existing package requires verified APK inspection",
    "APP_VERSION_MISMATCH": "Installed application version is not trusted",
    "APP_SIGNATURE_MISMATCH": "Installed application signature does not match",
    "APP_INSTALL_FAILED": "Managed application installation failed",
    "APP_VERIFY_FAILED": "Managed application verification failed",
    "APP_PACKAGE_DISABLED": "Managed application package is disabled",
    "APP_DOWNGRADE_BLOCKED": "Managed application downgrade is blocked",
    "APP_VERSION_NOT_READY": "Managed application version is not ready",
    "APP_BLOB_MISSING": "Managed application package bytes are unavailable",
    "APP_BLOB_INVALID": "Managed application package bytes failed validation",
    "APP_RUNTIME_UNAVAILABLE": "Managed application Runtime is unavailable",
    "APP_OPERATION_CANCELLED": "Managed application operation was cancelled",
}


class AppManagementError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        retryable: bool = False,
        observation: AdbInstalledPackage | None = None,
        diagnostic_code: str | None = None,
    ) -> None:
        self.code = code
        self.safe_message = _MESSAGES[code]
        self.retryable = retryable
        self.observation = observation
        self.diagnostic_code = diagnostic_code
        super().__init__(self.safe_message)


@dataclass(frozen=True)
class AppObservation:
    runtime_id: int
    managed_app_id: int
    desired_version_id: int
    observed_managed_app_version_id: int | None
    package_name: str | None
    version_name: str | None
    version_code: int | None
    signer_fingerprint: str | None
    installed: bool
    changed: bool
    inspection_level: str
    package_verification: str


class AndroidAppManagementService:
    """Install or inspect only DB-pinned, previously inspected APK versions."""

    def __init__(
        self,
        session: Session,
        *,
        adb: AdbExecutor,
        runtime_adapter: RedroidRuntimeAdapter,
        guard: RuntimeOperationGuard,
        storage: ContentStorageService,
        screen_inspector: ScreenSessionInspector | None = None,
        readiness_timeout: float = 30.0,
        lock_timeout: float = 0,
        install_timeout: float = 300.0,
    ) -> None:
        self.session = session
        self.adb = adb
        self.guard = guard
        self.storage = storage
        self.resolver = RuntimeTargetResolver(session)
        self.readiness = AutomationReadinessService(
            runtime_adapter,
            adb,
            screen_inspector=screen_inspector,
            wait_timeout=readiness_timeout,
        )
        self.lock_timeout = lock_timeout
        self.install_timeout = install_timeout

    def verify(self, runtime_id: int, version_id: int) -> AppObservation:
        return self._with_target(
            runtime_id,
            lambda target: self._observe_desired(target, self._resolve_version(version_id)),
        )

    def install(
        self,
        runtime_id: int,
        version_id: int,
        *,
        known_installed: bool = False,
        known_version_name: str | None = None,
        known_version_code: int | None = None,
    ) -> AppObservation:
        def operation(target: RuntimeTarget) -> AppObservation:
            app, desired, blob = self._resolve_apk(version_id)
            observed = self._observe(target, app, desired)
            if observed is not None:
                self._validate_enabled_and_signer(observed, desired)
                if self._is_exact(observed, desired) or (
                    desired.inspection_level == "basic"
                    and known_installed
                    and self._matches_known_basic(
                        observed,
                        version_name=known_version_name,
                        version_code=known_version_code,
                    )
                ):
                    return self._result(target, app, desired, observed, changed=False)
                if desired.inspection_level == "basic":
                    raise AppManagementError(
                        "APP_BASIC_UPDATE_REQUIRES_VERIFIED", observation=observed
                    )
                self._validate_update_candidate(app, desired, observed)
            try:
                with self.storage.temporary_apk_view(blob) as apk_path:
                    self.adb.install_package(
                        target.adb_serial, apk_path, timeout=self.install_timeout
                    )
            except ContentStorageError as error:
                code = (
                    "APP_BLOB_MISSING"
                    if error.code == "CONTENT_BLOB_MISSING"
                    else "APP_BLOB_INVALID"
                )
                raise AppManagementError(
                    code, diagnostic_code="managed_apk_view_failed"
                ) from error
            except AdbExecutorError as error:
                if error.kind == "cancelled":
                    raise AppManagementError("APP_OPERATION_CANCELLED", retryable=True) from error
                diagnostics = {
                    "failed": "adb_nonzero_exit",
                    "timeout": "adb_timeout",
                    "output_limit": "adb_output_limit",
                    "unavailable": "adb_unavailable",
                }
                raise AppManagementError(
                    "APP_INSTALL_FAILED",
                    retryable=True,
                    diagnostic_code=diagnostics.get(error.kind, "adb_install_failed"),
                ) from error
            # The install command is never authoritative. A second package
            # manager observation must prove exact convergence.
            final = self._observe(target, app, desired)
            if final is None:
                raise AppManagementError("APP_PACKAGE_MISMATCH")
            self._validate_enabled_and_signer(final, desired)
            if desired.inspection_level == "verified" and not self._is_exact(final, desired):
                raise AppManagementError("APP_VERIFY_FAILED", observation=final)
            return self._result(target, app, desired, final, changed=True)

        return self._with_target(runtime_id, operation)

    def _with_target(self, runtime_id: int, operation):
        try:
            with self.guard.acquire_runtime(runtime_id, timeout=self.lock_timeout):
                target = self.resolver.resolve(runtime_id)
                self.readiness.wait_until_ready(target)
                return operation(target)
        except RuntimeOperationLockBusy as error:
            raise AutomationError(
                "RUNTIME_BUSY", "Runtime is busy with another operation", retryable=True
            ) from error
        except AutomationError:
            raise
        except AdbExecutorError as error:
            if error.kind == "cancelled":
                raise AppManagementError("APP_OPERATION_CANCELLED", retryable=True) from error
            raise AppManagementError("APP_VERIFY_FAILED", retryable=True) from error

    def _resolve_version(self, version_id: int) -> tuple[ManagedApp, ManagedAppVersion]:
        version = self.session.get(ManagedAppVersion, version_id)
        if version is None or version.status != "ready":
            raise AppManagementError("APP_VERSION_NOT_READY")
        app = self.session.get(ManagedApp, version.managed_app_id)
        if app is None:
            raise AppManagementError("APP_VERSION_NOT_READY")
        verified = (
            version.inspection_level == "verified"
            and version.discovered_package_name == app.android_package_name
            and version.version_code is not None
        )
        approved_basic = (
            version.inspection_level == "basic"
            and version.basic_approved_at is not None
        )
        if not (verified or approved_basic):
            raise AppManagementError("APP_VERSION_NOT_READY")
        return app, version

    def _resolve_apk(
        self, version_id: int
    ) -> tuple[ManagedApp, ManagedAppVersion, ContentBlob]:
        app, version = self._resolve_version(version_id)
        content_version = self.session.get(
            ContentAssetVersion, version.content_asset_version_id
        )
        blob = (
            self.session.get(ContentBlob, content_version.blob_id)
            if content_version is not None
            else None
        )
        if blob is None or blob.status != "active":
            raise AppManagementError("APP_BLOB_MISSING")
        if blob.sha256 != version.sha256:
            raise AppManagementError("APP_BLOB_INVALID")
        return app, version, blob

    def _observe_desired(
        self,
        target: RuntimeTarget,
        resolved: tuple[ManagedApp, ManagedAppVersion],
    ) -> AppObservation:
        app, desired = resolved
        observed = self._observe(target, app, desired)
        if observed is None:
            raise AppManagementError("APP_NOT_INSTALLED")
        self._validate_enabled_and_signer(observed, desired)
        if desired.inspection_level == "verified" and not self._is_exact(observed, desired):
            raise AppManagementError("APP_VERSION_MISMATCH", observation=observed)
        return self._result(target, app, desired, observed, changed=False)

    def _observe(
        self, target: RuntimeTarget, app: ManagedApp, desired: ManagedAppVersion
    ) -> AdbInstalledPackage | None:
        try:
            observed = self.adb.installed_package(
                target.adb_serial, app.android_package_name
            )
            if observed is not None and (
                observed.package_name != app.android_package_name
                or not observed.package_path.startswith("/data/app/")
            ):
                raise AppManagementError(
                    "APP_PACKAGE_MISMATCH", observation=observed
                )
            return observed
        except AdbExecutorError as error:
            if error.kind == "cancelled":
                raise AppManagementError("APP_OPERATION_CANCELLED", retryable=True) from error
            raise AppManagementError("APP_VERIFY_FAILED", retryable=True) from error

    @staticmethod
    def _is_exact(observed: AdbInstalledPackage, desired: ManagedAppVersion) -> bool:
        return (
            observed.version_code == desired.version_code
            and (desired.version_name is None or observed.version_name == desired.version_name)
        )

    @staticmethod
    def _matches_known_basic(
        observed: AdbInstalledPackage,
        *,
        version_name: str | None,
        version_code: int | None,
    ) -> bool:
        if version_code is not None and observed.version_code != version_code:
            return False
        if version_name is not None and observed.version_name != version_name:
            return False
        return version_code is not None or version_name is not None

    @staticmethod
    def _validate_enabled_and_signer(
        observed: AdbInstalledPackage, desired: ManagedAppVersion
    ) -> None:
        if not observed.enabled:
            raise AppManagementError("APP_PACKAGE_DISABLED", observation=observed)
        if (
            desired.inspection_level == "verified"
            and
            observed.signer_fingerprint is not None
            and desired.signer_fingerprint is not None
            and observed.signer_fingerprint != desired.signer_fingerprint
        ):
            raise AppManagementError("APP_SIGNATURE_MISMATCH", observation=observed)

    def _validate_update_candidate(
        self,
        app: ManagedApp,
        desired: ManagedAppVersion,
        observed: AdbInstalledPackage,
    ) -> None:
        if observed.version_code is None or desired.version_code is None:
            raise AppManagementError("APP_VERSION_MISMATCH", observation=observed)
        if observed.version_code > desired.version_code:
            raise AppManagementError("APP_DOWNGRADE_BLOCKED", observation=observed)
        if observed.version_code == desired.version_code:
            raise AppManagementError("APP_VERSION_MISMATCH", observation=observed)
        known = self.session.scalar(
            select(ManagedAppVersion).where(
                ManagedAppVersion.managed_app_id == app.id,
                ManagedAppVersion.status.in_(["ready", "retired"]),
                ManagedAppVersion.version_code == observed.version_code,
            )
        )
        if known is None:
            raise AppManagementError("APP_VERSION_MISMATCH", observation=observed)
        if (
            desired.signer_fingerprint
            and known.signer_fingerprint != desired.signer_fingerprint
        ):
            raise AppManagementError("APP_SIGNATURE_MISMATCH", observation=observed)
        if (
            observed.signer_fingerprint
            and desired.signer_fingerprint
            and observed.signer_fingerprint != desired.signer_fingerprint
        ):
            raise AppManagementError("APP_SIGNATURE_MISMATCH", observation=observed)

    @staticmethod
    def _result(
        target: RuntimeTarget,
        app: ManagedApp,
        desired: ManagedAppVersion,
        observed: AdbInstalledPackage,
        *,
        changed: bool,
    ) -> AppObservation:
        return AppObservation(
            runtime_id=target.runtime_id,
            managed_app_id=app.id,
            desired_version_id=desired.id,
            observed_managed_app_version_id=desired.id,
            package_name=observed.package_name,
            version_name=observed.version_name,
            version_code=observed.version_code,
            signer_fingerprint=observed.signer_fingerprint,
            installed=True,
            changed=changed,
            inspection_level=desired.inspection_level,
            package_verification=(
                "pre_and_post_install"
                if desired.inspection_level == "verified"
                else "post_install"
            ),
        )
