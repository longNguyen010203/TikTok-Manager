"""Unit tests for the local Redroid runtime adapter."""

import subprocess
from unittest.mock import call, patch

import pytest

from app.services.redroid_runtime import (
    RedroidAdbTimeoutError,
    RedroidBootTimeoutError,
    RedroidCommandError,
    RedroidConfigurationError,
    RedroidRuntimeAdapter,
)


def completed_process(
    command: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


@patch("app.services.redroid_runtime.subprocess.run")
def test_get_container_status_uses_docker_inspect(mock_run) -> None:
    mock_run.return_value = completed_process([], stdout="running\n")
    adapter = RedroidRuntimeAdapter()

    assert adapter.get_container_status("redroid-device-01") == "running"
    mock_run.assert_called_once_with(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}}",
            "redroid-device-01",
        ],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize("action", ["start", "stop", "restart"])
@patch("app.services.redroid_runtime.subprocess.run")
def test_container_actions_use_docker(mock_run, action: str) -> None:
    mock_run.return_value = completed_process([], stdout="redroid-device-01\n")
    adapter = RedroidRuntimeAdapter()

    result = getattr(adapter, f"{action}_container")("redroid-device-01")

    assert result == "redroid-device-01"
    mock_run.assert_called_once_with(
        ["docker", action, "redroid-device-01"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("app.services.redroid_runtime.subprocess.run")
def test_failed_container_command_raises_clear_adapter_error(mock_run) -> None:
    mock_run.return_value = completed_process(
        [], returncode=1, stderr="No such container"
    )

    with pytest.raises(RedroidCommandError) as raised:
        RedroidRuntimeAdapter().start_container("missing-container")

    error = raised.value
    assert error.command == ("docker", "start", "missing-container")
    assert error.returncode == 1
    assert error.stderr == "No such container"
    assert "exit code 1: No such container" in str(error)


@patch("app.services.redroid_runtime.subprocess.run")
def test_missing_executable_raises_adapter_error(mock_run) -> None:
    mock_run.side_effect = FileNotFoundError("docker not found")

    with pytest.raises(RedroidCommandError, match="Unable to execute 'docker'"):
        RedroidRuntimeAdapter().get_container_status("redroid-device-01")


@patch("app.services.redroid_runtime.time.sleep")
@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_boot_polls_until_boot_completed(mock_run, mock_sleep) -> None:
    mock_run.side_effect = [
        completed_process([], stdout="\n"),
        completed_process([], stdout="1\n"),
    ]

    assert (
        RedroidRuntimeAdapter(boot_poll_interval=0.01).wait_for_boot(
            "redroid-device-01", timeout=5
        )
        is True
    )
    assert mock_run.call_args_list == [
        call(
            [
                "docker",
                "exec",
                "redroid-device-01",
                "getprop",
                "sys.boot_completed",
            ],
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        ),
        call(
            [
                "docker",
                "exec",
                "redroid-device-01",
                "getprop",
                "sys.boot_completed",
            ],
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        ),
    ]
    mock_sleep.assert_called_once()


@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_boot_timeout_retains_last_command_error(mock_run) -> None:
    mock_run.return_value = completed_process(
        [], returncode=1, stderr="container is not running"
    )

    with pytest.raises(RedroidBootTimeoutError) as raised:
        RedroidRuntimeAdapter().wait_for_boot("redroid-device-01", timeout=0)

    assert raised.value.container_name == "redroid-device-01"
    assert raised.value.timeout == 0
    assert raised.value.last_error is not None
    assert "container is not running" in str(raised.value)


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [(0, "1\n", True), (0, "\n", False), (1, "", False)],
)
@patch("app.services.redroid_runtime.subprocess.run")
def test_check_boot_reports_readiness(
    mock_run, returncode: int, stdout: str, expected: bool
) -> None:
    mock_run.return_value = completed_process(
        [], returncode=returncode, stdout=stdout, stderr="not ready"
    )

    assert RedroidRuntimeAdapter().check_boot("redroid-device-01") is expected
    mock_run.assert_called_once_with(
        [
            "docker",
            "exec",
            "redroid-device-01",
            "getprop",
            "sys.boot_completed",
        ],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected"),
    [(0, "device\n", True), (0, "offline\n", False), (1, "", False)],
)
@patch("app.services.redroid_runtime.subprocess.run")
def test_check_adb_reports_readiness(
    mock_run, returncode: int, stdout: str, expected: bool
) -> None:
    mock_run.return_value = completed_process(
        [], returncode=returncode, stdout=stdout, stderr="not ready"
    )

    assert RedroidRuntimeAdapter().check_adb("localhost:5555") is expected
    mock_run.assert_called_once_with(
        ["adb", "-s", "localhost:5555", "get-state"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("app.services.redroid_runtime.subprocess.run")
def test_connect_adb_uses_target_serial(mock_run) -> None:
    mock_run.return_value = completed_process(
        [], stdout="connected to localhost:5555\n"
    )

    result = RedroidRuntimeAdapter().connect_adb("localhost:5555")

    assert result == "connected to localhost:5555"
    mock_run.assert_called_once_with(
        ["adb", "connect", "localhost:5555"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("app.services.redroid_runtime.subprocess.run")
def test_disconnect_adb_uses_target_serial(mock_run) -> None:
    mock_run.return_value = completed_process(
        [], stdout="disconnected localhost:5555\n"
    )

    result = RedroidRuntimeAdapter().disconnect_adb("localhost:5555")

    assert result == "disconnected localhost:5555"
    mock_run.assert_called_once_with(
        ["adb", "disconnect", "localhost:5555"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("app.services.redroid_runtime.time.sleep")
@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_adb_reconnects_stale_transport(mock_run, mock_sleep) -> None:
    mock_run.side_effect = [
        completed_process([], returncode=1, stderr="device offline"),
        completed_process([], stdout="disconnected localhost:5555\n"),
        completed_process([], stdout="connected to localhost:5555\n"),
        completed_process([], stdout="offline\n"),
        completed_process([], stdout="device\n"),
    ]

    assert (
        RedroidRuntimeAdapter(boot_poll_interval=0.01).wait_for_adb(
            "localhost:5555", timeout=5
        )
        is True
    )
    assert mock_run.call_args_list[1].args[0] == [
        "adb",
        "disconnect",
        "localhost:5555",
    ]
    assert mock_run.call_args_list[2].args[0] == [
        "adb",
        "connect",
        "localhost:5555",
    ]
    mock_sleep.assert_called_once()


@patch("app.services.redroid_runtime.time.sleep")
@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_adb_connects_missing_transport(mock_run, mock_sleep) -> None:
    mock_run.side_effect = [
        completed_process(
            [],
            returncode=1,
            stderr="adb: no such device 'localhost:5555'\n",
        ),
        completed_process([], stdout="connected to localhost:5555\n"),
        completed_process([], stdout="device\n"),
    ]

    assert (
        RedroidRuntimeAdapter().wait_for_adb("localhost:5555", timeout=5) is True
    )
    assert [item.args[0] for item in mock_run.call_args_list] == [
        ["adb", "-s", "localhost:5555", "get-state"],
        ["adb", "connect", "localhost:5555"],
        ["adb", "-s", "localhost:5555", "get-state"],
    ]
    mock_sleep.assert_not_called()


@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_adb_missing_transport_times_out(mock_run) -> None:
    missing = completed_process(
        [], returncode=1, stderr="adb: device 'localhost:5555' not found\n"
    )
    mock_run.side_effect = [
        missing,
        completed_process([], stdout="connected to localhost:5555\n"),
        missing,
    ]

    with pytest.raises(RedroidAdbTimeoutError, match="within 0 seconds"):
        RedroidRuntimeAdapter().wait_for_adb("localhost:5555", timeout=0)

    assert [item.args[0] for item in mock_run.call_args_list] == [
        ["adb", "-s", "localhost:5555", "get-state"],
        ["adb", "connect", "localhost:5555"],
        ["adb", "-s", "localhost:5555", "get-state"],
    ]


@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_adb_keeps_existing_device_transport(mock_run) -> None:
    mock_run.return_value = completed_process([], stdout="device\n")

    assert (
        RedroidRuntimeAdapter().wait_for_adb("localhost:5555", timeout=5) is True
    )
    mock_run.assert_called_once_with(
        ["adb", "-s", "localhost:5555", "get-state"],
        shell=False,
        capture_output=True,
        text=True,
        check=False,
    )


@patch("app.services.redroid_runtime.subprocess.run")
def test_wait_for_adb_times_out(mock_run) -> None:
    mock_run.side_effect = [
        completed_process([], returncode=1),
        completed_process([], stdout="disconnected localhost:5555\n"),
        completed_process([], stdout="connected to localhost:5555\n"),
        completed_process([], stdout="offline\n"),
    ]

    with pytest.raises(RedroidAdbTimeoutError, match="within 0 seconds"):
        RedroidRuntimeAdapter().wait_for_adb("localhost:5555", timeout=0)

@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        ("get_container_status", (" ",)),
        ("start_container", ("",)),
        ("stop_container", ("",)),
        ("restart_container", ("",)),
        ("check_boot", ("",)),
        ("wait_for_boot", ("", 1)),
        ("check_adb", ("",)),
        ("connect_adb", ("",)),
        ("disconnect_adb", ("",)),
        ("wait_for_adb", ("", 1)),
    ],
)
@patch("app.services.redroid_runtime.subprocess.run")
def test_empty_identifiers_are_rejected_without_running_commands(
    mock_run, method_name: str, arguments: tuple[object, ...]
) -> None:
    adapter = RedroidRuntimeAdapter()

    with pytest.raises(RedroidConfigurationError, match="must not be empty"):
        getattr(adapter, method_name)(*arguments)

    mock_run.assert_not_called()


def test_invalid_timing_values_are_rejected() -> None:
    with pytest.raises(RedroidConfigurationError, match="boot_poll_interval"):
        RedroidRuntimeAdapter(boot_poll_interval=0)

    with pytest.raises(RedroidConfigurationError, match="timeout"):
        RedroidRuntimeAdapter().wait_for_boot("redroid-device-01", timeout=-1)

    with pytest.raises(RedroidConfigurationError, match="timeout"):
        RedroidRuntimeAdapter().wait_for_adb("localhost:5555", timeout=-1)
