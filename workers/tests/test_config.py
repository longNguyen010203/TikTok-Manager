"""Tests for worker configuration."""

import pytest

from worker.config import parse_config


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
