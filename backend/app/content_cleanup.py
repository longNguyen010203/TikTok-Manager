"""One-shot, cross-process-safe reusable-content cleanup."""

from __future__ import annotations

import logging
from datetime import timedelta

from app.config import load_application_config
from app.database import SessionLocal
from app.services.content_storage import ContentMaintenanceBusy, ContentStorageService

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = load_application_config()
    storage = ContentStorageService(
        config.content_root,
        max_upload_bytes=config.content_max_upload_bytes,
        max_total_bytes=config.content_max_total_bytes,
    )
    with SessionLocal() as session:
        try:
            result = storage.cleanup(
                session,
                orphan_grace=timedelta(hours=config.content_orphan_grace_hours),
                wait=False,
            )
        except ContentMaintenanceBusy:
            logger.info("Content cleanup skipped: maintenance already running")
            return
    logger.info(
        "Content cleanup complete staging=%d orphan_blobs=%d bytes_reclaimed=%d missing=%d uncertain=%d",
        result.removed_staging_files, result.deleted_orphan_blobs,
        result.bytes_reclaimed, result.missing_blobs, len(result.uncertain_files),
    )


if __name__ == "__main__":
    main()
