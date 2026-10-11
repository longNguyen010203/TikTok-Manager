"""Tests for worker configuration."""

import pytest

from app.environment import ManagerEnvironment
from worker.config import WorkerConfig, parse_config


def test_environment_config_can_be_overridden_by_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKER_BACKEND_URL", "http://environment:8000/")
    monkeypatch.setenv("WORKER_POLL_INTERVAL_SECONDS", "12.5")
    monkeypatch.setenv("WORKER_RETRY_DELAY_SECONDS", "45")

    environment_config = parse_config([])
    override_config = parse_config(
        [
            "--backend-url",
            "https://api.example.test/",
            "--poll-interval",
            "2",
            "--retry-delay",
            "10",
        ]
    )

    assert environment_config.backend_url == "http://environment:8000"
    assert environment_config.poll_interval_seconds == 12.5
    assert environment_config.retry_delay_seconds == 45.0
    assert override_config.backend_url == "https://api.example.test"
    assert override_config.poll_interval_seconds == 2.0
    assert override_config.retry_delay_seconds == 10.0


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--backend-url", "backend:8000"], "absolute HTTP(S) URL"),
        (["--poll-interval", "0"], "greater than zero"),
        (["--retry-delay", "-1"], "must not be negative"),
    ],
)
def test_invalid_cli_config_is_rejected(
    arguments: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        parse_config(arguments)

    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ("production", "http://127.0.0.1:8000"),
        ("development", "http://127.0.0.1:8001"),
    ],
)
def test_worker_uses_environment_backend(
    monkeypatch: pytest.MonkeyPatch, environment: str, expected: str
) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", environment)
    monkeypatch.delenv("WORKER_BACKEND_URL", raising=False)

    config = WorkerConfig.from_environment()

    assert config.backend_url == expected
    assert config.environment is ManagerEnvironment(environment)


def test_development_worker_cannot_target_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TIKTOK_MANAGER_ENV", "development")
    monkeypatch.setenv("WORKER_BACKEND_URL", "http://127.0.0.1:8000")

    with pytest.raises(ValueError, match="development worker"):
        WorkerConfig.from_environment()


def test_legacy_installed_worker_port_implies_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TIKTOK_MANAGER_ENV", raising=False)
    monkeypatch.delenv("TIKTOK_MANAGER_RUNTIME_MODE", raising=False)
    monkeypatch.setenv("WORKER_BACKEND_URL", "http://127.0.0.1:8000")

    config = WorkerConfig.from_environment()

    assert config.environment is ManagerEnvironment.PRODUCTION
