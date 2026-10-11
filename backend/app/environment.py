"""Central environment and mutable-path resolution for TikTok Manager."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping


ENVIRONMENT_VARIABLE = "TIKTOK_MANAGER_ENV"
LEGACY_RUNTIME_MODE_VARIABLE = "TIKTOK_MANAGER_RUNTIME_MODE"


class EnvironmentConfigurationError(ValueError):
    """Raised when an environment name or environment-owned path is unsafe."""


class ManagerEnvironment(str, Enum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


@dataclass(frozen=True)
class EnvironmentSettings:
    environment: ManagerEnvironment
    data_root: Path
    config_root: Path
    runtime_root: Path
    temporary_root: Path
    database_path: Path
    backend_port: int
    frontend_port: int
    host_reconciliation_enabled: bool


def resolve_environment(
    environ: Mapping[str, str] | None = None,
) -> ManagerEnvironment:
    """Resolve the one canonical environment, retaining the old production flag.

    An unset environment is deliberately development.  Installed production
    units from before TIK-027R remain compatible because their legacy runtime
    mode explicitly says ``production``.
    """
    values = os.environ if environ is None else environ
    raw = values.get(ENVIRONMENT_VARIABLE, "").strip().lower()
    if not raw:
        legacy = values.get(LEGACY_RUNTIME_MODE_VARIABLE, "").strip().lower()
        raw = "production" if legacy == "production" else "development"
    try:
        return ManagerEnvironment(raw)
    except ValueError as error:
        choices = ", ".join(item.value for item in ManagerEnvironment)
        raise EnvironmentConfigurationError(
            f"{ENVIRONMENT_VARIABLE} must be one of: {choices}"
        ) from error


def resolve_environment_settings(
    environ: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
) -> EnvironmentSettings:
    values = os.environ if environ is None else environ
    environment = resolve_environment(values)
    home_directory = (home or Path.home()).expanduser().resolve()

    if environment is ManagerEnvironment.PRODUCTION:
        suffix = "tiktok-manager"
        backend_port, frontend_port = 8000, 3000
    elif environment is ManagerEnvironment.DEVELOPMENT:
        suffix = "tiktok-manager-dev"
        backend_port, frontend_port = 8001, 3001
    else:
        test_root = Path(
            values.get(
                "TIKTOK_MANAGER_TEST_ROOT",
                str(Path(tempfile.gettempdir()) / f"tiktok-manager-test-{os.getuid()}-{os.getpid()}"),
            )
        ).expanduser().resolve()
        return EnvironmentSettings(
            environment=environment,
            data_root=test_root,
            config_root=test_root / "config",
            runtime_root=test_root / "run",
            temporary_root=test_root / "tmp",
            database_path=test_root / "tiktok_manager.db",
            backend_port=0,
            frontend_port=0,
            host_reconciliation_enabled=False,
        )

    data_root = home_directory / ".local" / "share" / suffix
    return EnvironmentSettings(
        environment=environment,
        data_root=data_root,
        config_root=home_directory / ".config" / suffix,
        runtime_root=Path(f"/run/user/{os.getuid()}/{suffix}"),
        temporary_root=Path(tempfile.gettempdir()) / suffix,
        database_path=data_root / "tiktok_manager.db",
        backend_port=backend_port,
        frontend_port=frontend_port,
        host_reconciliation_enabled=environment is ManagerEnvironment.PRODUCTION,
    )


def path_is_within(path: Path, root: Path) -> bool:
    resolved_path = path.expanduser().resolve()
    resolved_root = root.expanduser().resolve()
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def validate_environment_path(
    path: Path,
    *,
    settings: EnvironmentSettings,
    label: str,
) -> Path:
    """Reject a mutable path owned by the opposite operational environment."""
    resolved = path.expanduser().resolve()
    production = resolve_environment_settings(
        {ENVIRONMENT_VARIABLE: ManagerEnvironment.PRODUCTION.value},
        home=Path.home(),
    )
    development = resolve_environment_settings(
        {ENVIRONMENT_VARIABLE: ManagerEnvironment.DEVELOPMENT.value},
        home=Path.home(),
    )
    other = (
        development
        if settings.environment is ManagerEnvironment.PRODUCTION
        else production
    )
    forbidden_roots = (
        other.data_root,
        other.config_root,
        other.runtime_root,
        other.temporary_root,
    )
    for forbidden in forbidden_roots:
        if path_is_within(resolved, forbidden):
            raise EnvironmentConfigurationError(
                f"{label} for {settings.environment.value} must not use {forbidden}"
            )
    return resolved
