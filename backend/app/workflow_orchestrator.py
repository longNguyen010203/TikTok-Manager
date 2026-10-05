"""Long-running local Workflow reconciliation process."""

from __future__ import annotations

import logging
import signal
import threading

from app.config import load_application_config
from app.database import SessionLocal
from app.services.workflow_lock import WorkflowOperationGuard
from app.services.workflow_orchestrator import WorkflowOrchestrator


LOGGER = logging.getLogger("tiktok_manager.workflow_orchestrator")
MAX_FAILURE_BACKOFF_SECONDS = 30.0


def poll_delay(base_interval: float, consecutive_failures: int) -> float:
    """Return a bounded poll delay without permitting an unbounded exponent."""
    if base_interval <= 0 or consecutive_failures < 0:
        raise ValueError("Workflow poll timing is invalid")
    exponent = min(consecutive_failures, 30)
    return min(base_interval * (2 ** exponent), MAX_FAILURE_BACKOFF_SECONDS)


def main() -> None:
    config = load_application_config()
    stopping = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    orchestrator = WorkflowOrchestrator(
        SessionLocal, WorkflowOperationGuard(config.workflow_lock_directory)
    )
    LOGGER.info("Workflow orchestrator started")
    consecutive_failures = 0
    while not stopping.is_set():
        try:
            orchestrator.run_once(limit=config.workflow_reconcile_batch_size)
            consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            LOGGER.exception("Workflow reconciliation pass failed")
        delay = poll_delay(config.workflow_poll_interval_seconds, consecutive_failures)
        stopping.wait(delay)
    LOGGER.info("Workflow orchestrator stopped")


if __name__ == "__main__":
    main()
