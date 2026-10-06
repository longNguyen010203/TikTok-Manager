"""Durable desired state, Job scheduling, and readiness for Runtime apps."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Job,
    JobStatus,
    ManagedApp,
    ManagedAppEvent,
    ManagedAppVersion,
    Runtime,
    RuntimeAppInstallation,
    RuntimeAppInstallationRun,
)
from app.models.timestamps import utc_now


ACTIVE_JOB_STATES = {
    JobStatus.PENDING.value,
    JobStatus.RUNNING.value,
    JobStatus.RETRYING.value,
    JobStatus.CANCELLING.value,
}


def _version_is_installable(app: ManagedApp, version: ManagedAppVersion | None) -> bool:
    if version is None or version.managed_app_id != app.id or version.status != "ready":
        return False
    if version.inspection_level == "verified":
        return (
            version.discovered_package_name == app.android_package_name
            and version.version_code is not None
        )
    return version.inspection_level == "basic" and version.basic_approved_at is not None


class RuntimeAppError(RuntimeError):
    def __init__(self, code: str, safe_message: str) -> None:
        self.code = code
        self.safe_message = safe_message
        super().__init__(safe_message)


@dataclass(frozen=True)
class PublishingReadiness:
    runtime_id: int
    runtime_ready: bool
    required_apps_ready: bool
    publishing_ready: bool
    required_count: int
    installed_count: int
    pending_count: int
    failed_count: int
    outdated_count: int


class RuntimeAppService:
    """Manage installation intent without executing ADB in request transactions."""

    @staticmethod
    def initialize_required(session: Session, runtime: Runtime) -> list[RuntimeAppInstallation]:
        rows: list[RuntimeAppInstallation] = []
        apps = list(session.scalars(select(ManagedApp).where(
            ManagedApp.status == "active",
            ManagedApp.install_policy == "required",
        )).all())
        for app in apps:
            if app.current_version_id is None:
                continue
            version = session.get(ManagedAppVersion, app.current_version_id)
            if not _version_is_installable(app, version):
                continue
            existing = session.scalar(select(RuntimeAppInstallation).where(
                RuntimeAppInstallation.runtime_id == runtime.id,
                RuntimeAppInstallation.managed_app_id == app.id,
            ))
            if existing is not None:
                rows.append(existing)
                continue
            row = RuntimeAppInstallation(
                runtime_id=runtime.id,
                runtime_id_snapshot=runtime.id,
                managed_app_id=app.id,
                desired_managed_app_version_id=version.id,
                status="pending",
            )
            session.add(row)
            session.flush()
            session.add(_event(row, "installation_created"))
            rows.append(row)
        return rows

    @staticmethod
    def ensure_desired(
        session: Session,
        *,
        runtime_id: int,
        app_id: int,
        version_id: int | None = None,
    ) -> RuntimeAppInstallation:
        runtime = session.get(Runtime, runtime_id)
        if runtime is None or runtime.runtime_type != "redroid":
            raise RuntimeAppError("APP_RUNTIME_UNAVAILABLE", "Runtime is unavailable")
        app = session.get(ManagedApp, app_id)
        if app is None or app.status != "active" or app.install_policy == "disabled":
            raise RuntimeAppError("MANAGED_APP_NOT_FOUND", "Managed app is unavailable")
        desired_id = version_id or app.current_version_id
        version = session.get(ManagedAppVersion, desired_id) if desired_id else None
        if not _version_is_installable(app, version):
            raise RuntimeAppError("APP_VERSION_NOT_READY", "Managed app version is not ready")
        row = session.scalar(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id == runtime.id,
            RuntimeAppInstallation.managed_app_id == app.id,
        ))
        if row is None:
            row = RuntimeAppInstallation(
                runtime_id=runtime.id,
                runtime_id_snapshot=runtime.id,
                managed_app_id=app.id,
                desired_managed_app_version_id=version.id,
                status="pending",
            )
            session.add(row)
            session.flush()
            session.add(_event(row, "installation_created"))
        elif row.desired_managed_app_version_id != version.id:
            row.desired_managed_app_version_id = version.id
            row.status = "outdated" if row.observed_managed_app_version_id else "pending"
            row.error_code = None
            row.error_message = None
            session.add(_event(row, "marked_outdated"))
        return row

    @staticmethod
    def enqueue(
        session: Session,
        installation: RuntimeAppInstallation,
        *,
        operation: str,
    ) -> Job:
        if operation not in {"install", "verify"}:
            raise ValueError("Runtime app operation is invalid")
        if installation.runtime_id is None:
            raise RuntimeAppError("APP_RUNTIME_UNAVAILABLE", "Runtime is unavailable")
        if installation.latest_job_id is not None:
            existing = session.get(Job, installation.latest_job_id)
            if existing is not None and existing.status in ACTIVE_JOB_STATES:
                return existing
        job = Job(
            job_type=f"app.{operation}",
            status=JobStatus.PENDING.value,
            runtime_id=installation.runtime_id,
            payload={"runtime_app_installation_id": installation.id},
            max_attempts=3,
            execution_stage="queued",
        )
        session.add(job)
        session.flush()
        installation.latest_job_id = job.id
        if operation == "install":
            installation.status = "pending"
        session.add(RuntimeAppInstallationRun(
            runtime_app_installation_id=installation.id,
            desired_managed_app_version_id=installation.desired_managed_app_version_id,
            job_id=job.id,
        ))
        session.add(_event(
            installation,
            "install_requested" if operation == "install" else "verify_requested",
            job_id=job.id,
        ))
        return job

    @classmethod
    def converge_required(
        cls,
        session: Session,
        runtime_id: int,
        *,
        schedule: bool,
        verify_installed: bool = False,
    ) -> list[RuntimeAppInstallation]:
        runtime = session.get(Runtime, runtime_id)
        if runtime is None:
            raise RuntimeAppError("APP_RUNTIME_UNAVAILABLE", "Runtime is unavailable")
        rows = cls.initialize_required(session, runtime)
        required_apps = list(session.scalars(select(ManagedApp).where(
            ManagedApp.status == "active",
            ManagedApp.install_policy == "required",
        )).all())
        by_app = {row.managed_app_id: row for row in rows}
        for app in required_apps:
            if app.current_version_id is None:
                continue
            row = by_app.get(app.id)
            if row is None:
                row = cls.ensure_desired(
                    session, runtime_id=runtime.id, app_id=app.id,
                    version_id=app.current_version_id,
                )
                rows.append(row)
            elif row.desired_managed_app_version_id != app.current_version_id:
                row.desired_managed_app_version_id = app.current_version_id
                row.status = "outdated"
                session.add(_event(row, "marked_outdated"))
            exact = (
                row.status == "installed"
                and row.observed_managed_app_version_id == row.desired_managed_app_version_id
            )
            if schedule and runtime.status == "running":
                if exact and verify_installed:
                    cls.enqueue(session, row, operation="verify")
                elif not exact:
                    cls.enqueue(session, row, operation="install")
        return rows

    @classmethod
    def reconcile_jobs(cls, session: Session) -> int:
        """Recover DB-only gaps without performing any Runtime operation."""
        changed = 0
        rows = list(session.scalars(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id.is_not(None),
            RuntimeAppInstallation.status.in_(["pending", "installing", "outdated"]),
        )).all())
        for row in rows:
            runtime = session.get(Runtime, row.runtime_id)
            if runtime is None or runtime.status != "running":
                continue
            job = session.get(Job, row.latest_job_id) if row.latest_job_id else None
            if job is not None and job.status in ACTIVE_JOB_STATES:
                continue
            if job is not None and job.status == JobStatus.CANCELLED.value:
                continue
            if job is not None and job.status == JobStatus.SUCCEEDED.value:
                result = job.result if isinstance(job.result, dict) else {}
                if (
                    result.get("installation_id") == row.id
                    and result.get("desired_version_id") == row.desired_managed_app_version_id
                    and result.get("status") == "installed"
                ):
                    row.status = "installed"
                    row.observed_managed_app_version_id = row.desired_managed_app_version_id
                    row.observed_package_name = result.get("observed_package")
                    row.observed_version_name = result.get("observed_version_name")
                    row.observed_version_code = result.get("observed_version_code")
                    row.verified_at = job.completed_at or utc_now()
                    row.error_code = None
                    row.error_message = None
                    changed += 1
                    continue
            if job is not None and job.status == JobStatus.FAILED.value and not job.error_retryable:
                continue
            cls.enqueue(session, row, operation="install")
            changed += 1
        if changed:
            session.commit()
        return changed

    @staticmethod
    def readiness(session: Session, runtime: Runtime, *, runtime_ready: bool) -> PublishingReadiness:
        apps = list(session.scalars(select(ManagedApp).where(
            ManagedApp.status == "active",
            ManagedApp.install_policy == "required",
        )).all())
        rows = list(session.scalars(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id == runtime.id,
        )).all())
        by_app = {row.managed_app_id: row for row in rows}
        installed = pending = failed = outdated = 0
        for app in apps:
            row = by_app.get(app.id)
            exact = (
                row is not None
                and app.current_version_id is not None
                and row.status == "installed"
                and row.desired_managed_app_version_id == app.current_version_id
                and row.observed_managed_app_version_id == app.current_version_id
            )
            if exact:
                installed += 1
            elif row is None or row.status in {"pending", "installing"}:
                pending += 1
            elif row.status == "failed":
                failed += 1
            else:
                outdated += 1
        required_ready = installed == len(apps)
        return PublishingReadiness(
            runtime_id=runtime.id,
            runtime_ready=runtime_ready,
            required_apps_ready=required_ready,
            publishing_ready=runtime_ready and required_ready,
            required_count=len(apps),
            installed_count=installed,
            pending_count=pending,
            failed_count=failed,
            outdated_count=outdated,
        )

    @staticmethod
    def mark_runtime_removed(session: Session, runtime_id: int) -> None:
        rows = list(session.scalars(select(RuntimeAppInstallation).where(
            RuntimeAppInstallation.runtime_id == runtime_id
        )).all())
        for row in rows:
            row.runtime_id = None
            row.status = "removed"
            session.add(_event(row, "runtime_removed"))

    @staticmethod
    def sync_failed_job(session: Session, job: Job) -> None:
        if job.job_type not in {"app.install", "app.verify"}:
            return
        run = session.scalar(select(RuntimeAppInstallationRun).where(
            RuntimeAppInstallationRun.job_id == job.id
        ))
        if run is None:
            return
        row = session.get(RuntimeAppInstallation, run.runtime_app_installation_id)
        if row is None or job.status == JobStatus.PENDING.value:
            return
        row.status = "failed"
        row.error_code = (job.error_code or "APP_INSTALL_FAILED")[:100]
        row.error_message = (job.error_message or "Managed app operation failed")[:500]
        session.add(_event(row, "install_failed", job_id=job.id, metadata={
            "error_code": row.error_code,
        }))


def _event(
    installation: RuntimeAppInstallation,
    event_type: str,
    *,
    job_id: int | None = None,
    metadata: dict | None = None,
) -> ManagedAppEvent:
    values = {"installation_id": installation.id, "runtime_id": installation.runtime_id_snapshot}
    if metadata:
        values.update(metadata)
    return ManagedAppEvent(
        managed_app_id=installation.managed_app_id,
        managed_app_version_id=installation.desired_managed_app_version_id,
        job_id=job_id,
        event_type=event_type,
        metadata_json=values,
    )
