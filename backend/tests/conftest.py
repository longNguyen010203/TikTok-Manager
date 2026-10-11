"""Global test-process safety defaults."""

import os
import tempfile
from pathlib import Path


os.environ["TIKTOK_MANAGER_ENV"] = "test"
os.environ["TIKTOK_MANAGER_TEST_ROOT"] = str(
    Path(tempfile.gettempdir()) / f"tiktok-manager-pytest-{os.getpid()}"
)
