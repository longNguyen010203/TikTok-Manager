"""Durable per-user configuration for the local TikTok Manager runtime."""

from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path


VERIFIED_REDROID_IMAGE = (
    "redroid/redroid@sha256:"
    "a6c464bbedcf1dcb67dbf91f329fbb19bee5b50631f0ca6bda6ed7c41b0e64e2"
)


class ApplicationConfigurationError(ValueError):
    """Raised when durable local-host configuration is missing or unsafe."""


def default_config_directory() -> Path:
    root = os.getenv("XDG_CONFIG_HOME")
    return (Path(root) if root else Path.home() / ".config") / "tiktok-manager"


def default_data_directory() -> Path:
    root = os.getenv("XDG_DATA_HOME")
    return (Path(root) if root else Path.home() / ".local" / "share") / "tiktok-manager"


def configured_config_path() -> Path:
    override = os.getenv("TIKTOK_MANAGER_CONFIG")
    return Path(override).expanduser() if override else default_config_directory() / "config.toml"


def _absolute_without_following_symlinks(path: Path) -> Path:
    """Make a path absolute while preserving the final component for lstat()."""
    return Path(os.path.abspath(path.expanduser()))


@dataclass(frozen=True)
class ApplicationConfig:
    config_path: Path
    database_path: Path
    credential_key_path: Path
    installation_id: str
    redroid_image: str
    redroid_data_root: Path
    redroid_base_adb_port: int
    redroid_profile: str
    redroid_network_prefix: str
    bridge_port_start: int
    bridge_port_end: int
    bridge_device_port: int
    bridge_state_directory: Path
    bridge_lock_directory: Path
    bridge_systemd_scope: str
    artifact_root: Path
    artifact_max_size_bytes: int
    stop_managed_devices_on_shutdown: bool


def default_application_config(path: Path | None = None) -> ApplicationConfig:
    config_path = _absolute_without_following_symlinks(path or configured_config_path())
    data_directory = default_data_directory()
    return ApplicationConfig(
        config_path=config_path,
        database_path=data_directory / "tiktok_manager.db",
        credential_key_path=config_path.parent / "credentials.key",
        installation_id="tiktok-manager-longnguyen-host-01",
        redroid_image=VERIFIED_REDROID_IMAGE,
        redroid_data_root=Path.home() / "redroid-test",
        redroid_base_adb_port=5554,
        redroid_profile="android-12-redroid",
        redroid_network_prefix="redroid-device",
        bridge_port_start=8800,
        bridge_port_end=8899,
        bridge_device_port=8888,
        bridge_state_directory=Path(f"/run/user/{os.getuid()}/tiktok-manager-network"),
        bridge_lock_directory=Path("/tmp/tiktok-manager-network-locks"),
        bridge_systemd_scope="user",
        artifact_root=data_directory / "artifacts",
        artifact_max_size_bytes=100 * 1024 * 1024,
        stop_managed_devices_on_shutdown=False,
    )


def bootstrap_application_config(path: Path | None = None) -> ApplicationConfig:
    """Create a mode-0600 config once, without replacing an existing file."""
    desired = default_application_config(path)
    parent = desired.config_path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _require_safe_directory(parent)
    payload = _serialize(desired).encode("utf-8")
    try:
        descriptor = os.open(
            desired.config_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except FileExistsError:
        return load_application_config(desired.config_path)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    return load_application_config(desired.config_path)


def load_application_config(
    path: Path | None = None, *, bootstrap: bool = False
) -> ApplicationConfig:
    config_path = _absolute_without_following_symlinks(path or configured_config_path())
    if not config_path.exists():
        if bootstrap:
            return bootstrap_application_config(config_path)
        return _with_environment_overrides(default_application_config(config_path))
    _require_safe_file(config_path, maximum_mode=0o644)
    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        database = data["database"]
        provisioning = data["provisioning"]
        network = data["network"]
        automation = data.get("automation", {})
        runtime = data.get("runtime", {})
        security = data.get("security", {})
        result = ApplicationConfig(
            config_path=config_path,
            database_path=Path(str(database["path"])).expanduser(),
            credential_key_path=Path(
                str(security.get("credential_key_path", config_path.parent / "credentials.key"))
            ).expanduser(),
            installation_id=str(provisioning["installation_id"]),
            redroid_image=str(provisioning["image"]),
            redroid_data_root=Path(str(provisioning["data_root"])).expanduser(),
            redroid_base_adb_port=int(provisioning.get("base_adb_port", 5554)),
            redroid_profile=str(provisioning.get("profile", "android-12-redroid")),
            redroid_network_prefix=str(provisioning.get("network_prefix", "redroid-device")),
            bridge_port_start=int(network.get("bridge_port_start", 8800)),
            bridge_port_end=int(network.get("bridge_port_end", 8899)),
            bridge_device_port=int(network.get("bridge_device_port", 8888)),
            bridge_state_directory=Path(str(network["bridge_state_directory"])).expanduser(),
            bridge_lock_directory=Path(str(network["bridge_lock_directory"])).expanduser(),
            bridge_systemd_scope=str(network.get("bridge_systemd_scope", "user")),
            artifact_root=Path(
                str(automation.get("artifact_root", default_data_directory() / "artifacts"))
            ).expanduser(),
            artifact_max_size_bytes=int(
                automation.get("artifact_max_size_bytes", 100 * 1024 * 1024)
            ),
            stop_managed_devices_on_shutdown=bool(
                runtime.get("stop_managed_devices_on_shutdown", False)
            ),
        )
    except (KeyError, TypeError, ValueError, tomllib.TOMLDecodeError) as error:
        raise ApplicationConfigurationError("Application config is invalid") from error
    return _with_environment_overrides(result)


def _with_environment_overrides(config: ApplicationConfig) -> ApplicationConfig:
    """Keep explicit legacy/dev overrides without requiring them in production."""
    try:
        return ApplicationConfig(
            config_path=config.config_path,
            database_path=config.database_path,
            credential_key_path=Path(
                os.getenv("TIKTOK_MANAGER_CREDENTIAL_KEY_PATH", str(config.credential_key_path))
            ),
            installation_id=os.getenv("TIKTOK_MANAGER_INSTALLATION_ID", config.installation_id),
            redroid_image=os.getenv("REDROID_PROVISIONING_IMAGE", config.redroid_image),
            redroid_data_root=Path(
                os.getenv("REDROID_PROVISIONING_DATA_ROOT", str(config.redroid_data_root))
            ),
            redroid_base_adb_port=int(
                os.getenv("REDROID_PROVISIONING_BASE_ADB_PORT", str(config.redroid_base_adb_port))
            ),
            redroid_profile=os.getenv("REDROID_PROVISIONING_PROFILE", config.redroid_profile),
            redroid_network_prefix=os.getenv(
                "REDROID_PROVISIONING_NETWORK_PREFIX", config.redroid_network_prefix
            ),
            bridge_port_start=int(
                os.getenv("RUNTIME_NETWORK_BRIDGE_PORT_START", str(config.bridge_port_start))
            ),
            bridge_port_end=int(
                os.getenv("RUNTIME_NETWORK_BRIDGE_PORT_END", str(config.bridge_port_end))
            ),
            bridge_device_port=int(
                os.getenv("RUNTIME_NETWORK_BRIDGE_DEVICE_PORT", str(config.bridge_device_port))
            ),
            bridge_state_directory=Path(
                os.getenv(
                    "RUNTIME_NETWORK_BRIDGE_STATE_DIRECTORY",
                    str(config.bridge_state_directory),
                )
            ),
            bridge_lock_directory=Path(
                os.getenv("RUNTIME_NETWORK_LOCK_DIRECTORY", str(config.bridge_lock_directory))
            ),
            bridge_systemd_scope=os.getenv(
                "RUNTIME_NETWORK_BRIDGE_SYSTEMD_SCOPE", config.bridge_systemd_scope
            ),
            artifact_root=Path(
                os.getenv("TIKTOK_MANAGER_ARTIFACT_ROOT", str(config.artifact_root))
            ),
            artifact_max_size_bytes=int(
                os.getenv(
                    "TIKTOK_MANAGER_ARTIFACT_MAX_SIZE_BYTES",
                    str(config.artifact_max_size_bytes),
                )
            ),
            stop_managed_devices_on_shutdown=_environment_bool(
                "STOP_MANAGED_DEVICES_ON_SHUTDOWN",
                config.stop_managed_devices_on_shutdown,
            ),
        )
    except ValueError as error:
        raise ApplicationConfigurationError("Application environment override is invalid") from error


def _environment_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    if raw.lower() in {"1", "true", "yes", "on"}:
        return True
    if raw.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _require_safe_directory(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise ApplicationConfigurationError("Application config directory is unsafe")
    if info.st_uid != os.getuid():
        raise ApplicationConfigurationError("Application config directory has the wrong owner")
    os.chmod(path, 0o700)


def _require_safe_file(path: Path, *, maximum_mode: int) -> None:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise ApplicationConfigurationError("Application config file is unsafe")
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & ~maximum_mode:
        raise ApplicationConfigurationError("Application config permissions are unsafe")


def _quote(value: object) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _serialize(config: ApplicationConfig) -> str:
    return "\n".join(
        [
            "[database]",
            f"path = {_quote(config.database_path)}",
            "",
            "[security]",
            f"credential_key_path = {_quote(config.credential_key_path)}",
            "",
            "[provisioning]",
            f"installation_id = {_quote(config.installation_id)}",
            f"image = {_quote(config.redroid_image)}",
            f"data_root = {_quote(config.redroid_data_root)}",
            f"base_adb_port = {config.redroid_base_adb_port}",
            f"profile = {_quote(config.redroid_profile)}",
            f"network_prefix = {_quote(config.redroid_network_prefix)}",
            "",
            "[network]",
            f"bridge_port_start = {config.bridge_port_start}",
            f"bridge_port_end = {config.bridge_port_end}",
            f"bridge_device_port = {config.bridge_device_port}",
            f"bridge_state_directory = {_quote(config.bridge_state_directory)}",
            f"bridge_lock_directory = {_quote(config.bridge_lock_directory)}",
            f"bridge_systemd_scope = {_quote(config.bridge_systemd_scope)}",
            "",
            "[automation]",
            f"artifact_root = {_quote(config.artifact_root)}",
            f"artifact_max_size_bytes = {config.artifact_max_size_bytes}",
            "",
            "[runtime]",
            "stop_managed_devices_on_shutdown = "
            + ("true" if config.stop_managed_devices_on_shutdown else "false"),
            "",
        ]
    )
