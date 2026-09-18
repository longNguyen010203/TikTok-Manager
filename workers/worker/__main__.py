"""Command-line entry point for the worker."""

from __future__ import annotations

import logging
import signal
from types import FrameType

from worker.client import BackendClient
from worker.config import parse_config
from worker.runner import Worker


def main() -> None:
    """Configure and run the worker until Ctrl+C or a termination signal."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config = parse_config()
    worker = Worker(config, BackendClient(config.backend_url))

    def request_shutdown(
        signum: int, frame: FrameType | None  # noqa: ARG001
    ) -> None:
        worker.stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    worker.run()


if __name__ == "__main__":
    main()
