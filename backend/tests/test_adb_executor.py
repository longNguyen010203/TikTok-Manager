"""Safe ADB executor boundary tests."""

import subprocess

import pytest

from app.services.adb_executor import (
    AdbExecutor,
    AdbExecutorError,
    OwnedAdbProcessRegistry,
)


class RecordingRunner:
    def __init__(self, stdout: bytes = b"device\n", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, b"")


class LaunchRunner(RecordingRunner):
    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        stdout = (
            b"com.android.settings/.Settings\n"
            if "resolve-activity" in command
            else b"Starting: Intent\n"
        )
        return subprocess.CompletedProcess(command, 0, stdout, b"")


def test_exact_serial_and_shell_false_for_every_command() -> None:
    runner = RecordingRunner()
    executor = AdbExecutor(runner)
    assert executor.get_state("localhost:5588") == "device"
    command, options = runner.calls[0]
    assert command == ["adb", "-s", "localhost:5588", "get-state"]
    assert options["shell"] is False
    assert options["capture_output"] is True
    assert options["text"] is False


def test_launch_resolves_and_validates_component_before_start() -> None:
    runner = LaunchRunner()
    AdbExecutor(runner).launch_package("localhost:5588", "com.android.settings")
    assert runner.calls[0][0] == [
        "adb", "-s", "localhost:5588", "shell", "cmd", "package",
        "resolve-activity", "--brief", "-c",
        "android.intent.category.LAUNCHER", "com.android.settings",
    ]
    assert runner.calls[1][0] == [
        "adb", "-s", "localhost:5588", "shell", "am", "start", "-n",
        "com.android.settings/.Settings",
    ]


def test_launch_rejects_untrusted_component_output() -> None:
    with pytest.raises(AdbExecutorError, match="launcher activity"):
        AdbExecutor(RecordingRunner(b"other.package/.Unsafe\n")).launch_package(
            "localhost:5588", "com.android.settings"
        )


def test_media_lookup_matches_sanitized_name_locally_without_where_clause() -> None:
    runner = RecordingRunner(
        b"Row: 0 _id=19, _display_name=other.png\n"
        b"Row: 1 _id=20, _display_name=phase4.png\n"
    )
    assert AdbExecutor(runner).find_media_id(
        "localhost:5588", "phase4.png"
    ) == 20
    command = runner.calls[0][0]
    assert "--where" not in command
    assert "phase4.png" not in command


def test_timeout_is_sanitized() -> None:
    secret = "SHOULD-NOT-APPEAR"

    def timeout_runner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1, output=secret.encode())

    with pytest.raises(AdbExecutorError) as raised:
        AdbExecutor(timeout_runner).get_state("localhost:5588")
    assert raised.value.kind == "timeout"
    assert secret not in str(raised.value)


def test_nonzero_and_output_limit_errors_do_not_expose_output() -> None:
    secret = b"FAKE-ADB-SECRET"
    executor = AdbExecutor(RecordingRunner(secret, returncode=1))
    with pytest.raises(AdbExecutorError) as raised:
        executor.get_state("localhost:5588")
    assert secret.decode() not in str(raised.value)

    oversized = AdbExecutor(RecordingRunner(b"x" * 5), max_stdout_bytes=4)
    with pytest.raises(AdbExecutorError, match="safe limit"):
        oversized.get_state("localhost:5588")


def test_cancellation_placeholder_prevents_execution() -> None:
    runner = RecordingRunner()
    executor = AdbExecutor(runner, cancellation_hook=lambda: True)
    with pytest.raises(AdbExecutorError) as raised:
        executor.get_state("localhost:5588")
    assert raised.value.kind == "cancelled"
    assert runner.calls == []


def test_cancellation_terminates_only_owned_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signals: list[tuple[int, int]] = []
    checks = iter([False, True])

    class FakeProcess:
        pid = 43210
        returncode = None
        def poll(self):
            return self.returncode
        def communicate(self, timeout):
            raise subprocess.TimeoutExpired(["adb"], timeout)
        def wait(self, timeout):
            self.returncode = -15

    monkeypatch.setattr("app.services.adb_executor.subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr("app.services.adb_executor.os.killpg", lambda pid, sig: signals.append((pid, sig)))
    executor = AdbExecutor(cancellation_hook=lambda: next(checks))
    with pytest.raises(AdbExecutorError) as raised:
        executor.get_state("localhost:5588")
    assert raised.value.kind == "cancelled"
    assert signals and signals[0][0] == 43210


def test_owned_process_registry_terminates_only_registered_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminated: list[object] = []

    class FakeProcess:
        def poll(self):
            return None

    owned = FakeProcess()
    registry = OwnedAdbProcessRegistry()
    registry.register(owned)  # type: ignore[arg-type]
    monkeypatch.setattr(
        AdbExecutor,
        "_terminate_owned_process",
        lambda process: terminated.append(process),
    )

    assert registry.terminate_all() == 1
    assert terminated == [owned]
    assert registry.terminate_all() == 0


@pytest.mark.parametrize("serial", ["", "serial with spaces", "$(unsafe)"])
def test_invalid_serial_is_rejected(serial: str) -> None:
    with pytest.raises(ValueError):
        AdbExecutor(RecordingRunner()).get_state(serial)
