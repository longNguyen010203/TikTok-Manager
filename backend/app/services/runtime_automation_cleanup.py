"""Deprovision boundary for Runtime-targeted automation Jobs."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import Job, JobStatus
from app.services.job_logs import append_job_log
from app.services.content_delivery import ContentDeliveryService
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
                        or_(
                            Job.job_type.like("device.%"),
                            Job.job_type == "content.deliver",
                            Job.job_type.in_(["app.install", "app.verify"]),
                            Job.job_type.like("publishing.%"),
                            Job.job_type.like("tiktok.%"),
                        ),
                        Job.status.in_([JobStatus.PENDING.value, JobStatus.RETRYING.value, JobStatus.RUNNING.value, JobStatus.CANCELLING.value]),
                    )).all())
                    if any(job.status in {JobStatus.RUNNING.value, JobStatus.CANCELLING.value} for job in jobs):
                        raise RuntimeAutomationBusyError("Runtime has active automation")
                    for job in jobs:
                        job.status = JobStatus.CANCELLED.value
                        job.execution_stage = "runtime_deprovisioned"
                        append_job_log(session, job, level="info", event_type="runtime_deprovisioned", message="Job cancelled because its Runtime was deprovisioned")
                        ContentDeliveryService.mark_cancelled_for_job(session, job)
                    session.commit()
        except RuntimeOperationLockBusy as error:
            raise RuntimeAutomationBusyError("Runtime automation is in progress") from error
