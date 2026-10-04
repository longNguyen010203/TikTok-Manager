"""One-shot, cross-process-safe artifact retention maintenance."""

from __future__ import annotations

import logging

from app.database import SessionLocal
from app.services.automation_artifacts import (
    ArtifactCleanupBusy,
    AutomationArtifactStore,
)

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    store = AutomationArtifactStore.from_application_config()
    with SessionLocal() as session:
        try:
            result = store.cleanup(session, wait=False)
        except ArtifactCleanupBusy:
            logger.info("Artifact cleanup skipped: maintenance already running")
            return
    logger.info(
        "Artifact cleanup complete expired=%d missing=%d failed=%d "
        "bytes_released=%d active_bytes=%d",
        result.expired,
        result.missing,
        result.failed,
        result.bytes_released,
        result.active_bytes,
    )


if __name__ == "__main__":
    main()
