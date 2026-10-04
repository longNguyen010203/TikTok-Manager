"""Deprovision boundary for Runtime-targeted automation Jobs."""

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Job, JobStatus
from app.services.job_logs import append_job_log
from app.services.runtime_operation_lock import RuntimeOperationGuard, RuntimeOperationLockBusy


class RuntimeAutomationBusyError(RuntimeError):
    pass


class RuntimeAutomationCleanupCoordinator:
    def __init__(self, session_factory: sessionmaker[Session], guard: RuntimeOperationGuard) -> None:
        self.session_factory = session_factory
        self.guard = guard

    def cleanup_before_delete(self, runtime_id: int) -> None:
        try:
            with self.guard.acquire_runtime(runtime_id, blocking=False):
                with self.session_factory() as session:
                    jobs = list(session.scalars(select(Job).where(
                        Job.runtime_id == runtime_id,
                        Job.job_type.like("device.%"),
                        Job.status.in_([JobStatus.PENDING.value, JobStatus.RETRYING.value, JobStatus.RUNNING.value, JobStatus.CANCELLING.value]),
                    )).all())
                    if any(job.status in {JobStatus.RUNNING.value, JobStatus.CANCELLING.value} for job in jobs):
                        raise RuntimeAutomationBusyError("Runtime has active automation")
                    for job in jobs:
                        job.status = JobStatus.CANCELLED.value
                        job.execution_stage = "runtime_deprovisioned"
                        append_job_log(session, job, level="info", event_type="runtime_deprovisioned", message="Job cancelled because its Runtime was deprovisioned")
                    session.commit()
        except RuntimeOperationLockBusy as error:
            raise RuntimeAutomationBusyError("Runtime automation is in progress") from error
