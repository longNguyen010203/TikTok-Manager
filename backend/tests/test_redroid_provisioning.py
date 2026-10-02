"""Tests for durable, rollback-safe managed Redroid provisioning."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.models import Device, Runtime
from app.services.redroid_provisioning import (
    ProvisioningFailedError,
    ProvisioningIdempotencyConflict,
    ProvisioningRequest,
    RedroidProvisioningService,
)
from app.services.redroid_provisioning_adapter import (
    OccupiedResources,
    ProvisioningAllocation,
    ProvisioningOwnershipError,
    ProvisioningVerificationError,
    RedroidProvisioningAdapter,
)
from app.services.redroid_provisioning_config import (
    ProvisioningConfigurationError,
    RedroidProvisioningSettings,
)


class FakeAdapter:
    def __init__(self, occupied: OccupiedResources | None = None, fail_at: str | None = None):
        self.occupied = occupied or OccupiedResources(frozenset(), frozenset(), frozenset(), frozenset())
        self.fail_at = fail_at
        self.calls: list[str] = []

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_at == name:
            if name == "inspect":
                raise ProvisioningVerificationError("inspection failed")
            raise RuntimeError(f"{name} failed")

    def preflight(self) -> None: self._call("preflight")
    def occupied_resources(self) -> OccupiedResources: return self.occupied
    def port_is_available(self, port: int) -> bool: return True
    def create_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self._call("data"); return True
    def create_network(self, allocation: ProvisioningAllocation) -> str:
        self._call("network"); return "network-id"
    def verify_network(self, allocation: ProvisioningAllocation, network_id: str) -> None:
        self._call("network_inspect")
    def create_container(self, allocation: ProvisioningAllocation) -> str:
        self._call("container"); return "container-id"
    def verify_container(self, allocation: ProvisioningAllocation, container_id: str) -> None:
        self._call("inspect")
    def remove_owned_container(self, allocation: ProvisioningAllocation, container_id: str) -> bool:
        self._call("remove_container"); return True
    def owned_container_id(self, allocation: ProvisioningAllocation) -> str | None: return None
    def remove_owned_network(self, allocation: ProvisioningAllocation, network_id: str) -> bool:
        self._call("remove_network"); return True
    def owned_network_id(self, allocation: ProvisioningAllocation) -> str | None: return None
    def remove_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool:
        self._call("remove_data"); return True


@pytest.fixture
def settings(tmp_path: Path) -> RedroidProvisioningSettings:
    root = tmp_path / "redroid-data"
    root.mkdir()
    return RedroidProvisioningSettings(
        installation_id="test-installation",
        image_reference="redroid/redroid@sha256:" + "a" * 64,
        data_root=root,
    )


@pytest.fixture
def factory(tmp_path: Path) -> sessionmaker[Session]:
    url = URL.create("sqlite", database=str(tmp_path / "provisioning.db"))
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 10})
    init_db(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def request(settings: RedroidProvisioningSettings, name: str = "Redroid Device 03") -> ProvisioningRequest:
    return ProvisioningRequest(name=name, profile=settings.supported_profile)


def test_configuration_rejects_unstable_or_mutable_values(tmp_path: Path) -> None:
    with pytest.raises(ProvisioningConfigurationError, match="installation_id"):
        RedroidProvisioningSettings("", "redroid/redroid@sha256:" + "a" * 64, tmp_path)
    with pytest.raises(ProvisioningConfigurationError, match="immutable"):
        RedroidProvisioningSettings("install", "redroid/redroid:12", tmp_path)
    with pytest.raises(ProvisioningConfigurationError, match="absolute"):
        RedroidProvisioningSettings(
            "install", "image@sha256:" + "a" * 64, Path("relative")
        )


def test_allocation_skips_legacy_and_occupied_tuple(factory, settings) -> None:
    with factory() as session:
        for number in (1, 2):
            device = Device(name=f"Legacy {number}", device_type="emulator", platform="android", os_version="12", status="offline")
            session.add(device); session.flush()
            session.add(Runtime(device_id=device.id, name=f"legacy-{number}", runtime_type="redroid", docker_container_name=f"redroid-device-{number:02d}", adb_serial=f"localhost:{5554 + number}", status="stopped"))
        session.commit()
    occupied = OccupiedResources(
        frozenset({"redroid-device-03"}),
        frozenset({"redroid-device-04-net"}),
        frozenset({settings.data_root.resolve() / "device-05-data"}),
        frozenset({5560}),
    )
    service = RedroidProvisioningService(factory, FakeAdapter(occupied), settings)
    attempt = service.get_or_create_request("key", request(settings))
    reserved = service.reserve(attempt.id)
    assert reserved.device_number == 7
    assert reserved.container_name == "redroid-device-07"
    assert reserved.adb_host_port == 5561


def test_reserved_number_is_never_reused(factory, settings) -> None:
    service = RedroidProvisioningService(factory, FakeAdapter(), settings)
    first = service.reserve(service.get_or_create_request("one", request(settings, "One")).id)
    service._set_state(first.id, "rolled_back")
    second = service.reserve(service.get_or_create_request("two", request(settings, "Two")).id)
    assert (first.device_number, second.device_number) == (1, 2)


def test_idempotency_and_fingerprint_conflict(factory, settings) -> None:
    service = RedroidProvisioningService(factory, FakeAdapter(), settings)
    first = service.get_or_create_request("same-key", request(settings))
    same = service.get_or_create_request("same-key", request(settings))
    assert same.id == first.id
    with pytest.raises(ProvisioningIdempotencyConflict):
        service.get_or_create_request("same-key", request(settings, "Different"))


def test_concurrent_reservations_are_unique(factory, settings) -> None:
    adapter = FakeAdapter()
    service = RedroidProvisioningService(factory, adapter, settings)
    attempts = [
        service.get_or_create_request(f"key-{index}", request(settings, f"Device {index}"))
        for index in range(8)
    ]
    with ThreadPoolExecutor(max_workers=8) as executor:
        reserved = list(executor.map(lambda item: service.reserve(item.id), attempts))
    assert len({item.device_number for item in reserved}) == 8
    assert len({item.adb_host_port for item in reserved}) == 8


def test_success_commits_device_runtime_together_after_inspection(factory, settings) -> None:
    adapter = FakeAdapter()
    service = RedroidProvisioningService(factory, adapter, settings)
    completed = service.provision("success", request(settings))
    assert completed.state == "completed"
    assert completed.data_directory_created is True
    assert completed.network_created is True
    assert completed.container_created is True
    assert completed.docker_network_id == "network-id"
    assert completed.docker_container_id == "container-id"
    assert adapter.calls == [
        "preflight", "data", "network", "network_inspect", "container", "inspect"
    ]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Device)) == 1
        assert session.scalar(select(func.count()).select_from(Runtime)) == 1
        runtime = session.get(Runtime, completed.runtime_id)
        assert runtime is not None
        assert runtime.device_id == completed.device_id
        assert runtime.status == "stopped"


@pytest.mark.parametrize(
    ("stage", "expected_cleanup"),
    [
        ("data", []),
        ("network", ["remove_data"]),
        ("network_inspect", ["remove_network", "remove_data"]),
        ("container", ["remove_network", "remove_data"]),
        ("inspect", ["remove_container", "remove_network", "remove_data"]),
    ],
)
def test_stage_failures_roll_back_only_created_resources(factory, settings, stage, expected_cleanup) -> None:
    adapter = FakeAdapter(fail_at=stage)
    service = RedroidProvisioningService(factory, adapter, settings)
    with pytest.raises(ProvisioningFailedError) as caught:
        service.provision(f"fail-{stage}", request(settings))
    attempt = service.get(caught.value.provisioning_id)
    assert attempt.state == "rolled_back"
    assert [item for item in adapter.calls if item.startswith("remove_")] == expected_cleanup
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Device)) == 0
        assert session.scalar(select(func.count()).select_from(Runtime)) == 0


def test_database_completion_failure_rolls_back_without_partial_rows(factory, settings, monkeypatch) -> None:
    adapter = FakeAdapter()
    service = RedroidProvisioningService(factory, adapter, settings)
    monkeypatch.setattr(service, "_complete", lambda *_: (_ for _ in ()).throw(RuntimeError("db failed")))
    with pytest.raises(ProvisioningFailedError):
        service.provision("db-failure", request(settings))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Device)) == 0
        assert session.scalar(select(func.count()).select_from(Runtime)) == 0
    assert adapter.calls[-3:] == ["remove_container", "remove_network", "remove_data"]


def test_preflight_failure_records_failed_without_allocating(factory, settings) -> None:
    adapter = FakeAdapter(fail_at="preflight")
    service = RedroidProvisioningService(factory, adapter, settings)
    with pytest.raises(ProvisioningFailedError) as caught:
        service.provision("preflight-failure", request(settings))
    attempt = service.get(caught.value.provisioning_id)
    assert attempt.state == "failed"
    assert attempt.device_number is None
    assert [call for call in adapter.calls if call.startswith("remove_")] == []


@pytest.mark.parametrize(
    ("resume_state", "expected_calls"),
    [
        ("reserved", ["preflight", "data", "network", "network_inspect", "container", "inspect"]),
        ("data_created", ["preflight", "network", "network_inspect", "container", "inspect"]),
        ("network_created", ["preflight", "network_inspect", "container", "inspect"]),
        ("container_created", ["preflight", "inspect"]),
    ],
)
def test_retry_resumes_same_allocation(factory, settings, resume_state, expected_calls) -> None:
    adapter = FakeAdapter()
    service = RedroidProvisioningService(factory, adapter, settings)
    provision_request = request(settings)
    attempt = service.get_or_create_request(f"resume-{resume_state}", provision_request)
    attempt = service.reserve(attempt.id)
    values: dict[str, object] = {}
    if resume_state in {"data_created", "network_created", "container_created"}:
        values["data_directory_created"] = True
    if resume_state in {"network_created", "container_created"}:
        values.update(network_created=True, docker_network_id="network-id")
    if resume_state == "container_created":
        values.update(container_created=True, docker_container_id="container-id")
    service._record_stage(attempt.id, resume_state, **values)
    completed = service.provision(f"resume-{resume_state}", provision_request)
    assert completed.state == "completed"
    assert completed.device_number == attempt.device_number
    assert adapter.calls == expected_calls


def test_retry_after_completed_does_not_repeat_external_work(factory, settings) -> None:
    adapter = FakeAdapter()
    service = RedroidProvisioningService(factory, adapter, settings)
    provision_request = request(settings)
    first = service.provision("completed-retry", provision_request)
    adapter.calls.clear()
    second = service.provision("completed-retry", provision_request)
    assert second.id == first.id
    assert second.device_number == first.device_number
    assert adapter.calls == []


def test_inconsistent_recovery_preserves_resources(factory, settings) -> None:
    adapter = FakeAdapter(fail_at="inspect")
    service = RedroidProvisioningService(factory, adapter, settings)
    provision_request = request(settings)
    attempt = service.get_or_create_request("inconsistent", provision_request)
    attempt = service.reserve(attempt.id)
    service._record_stage(
        attempt.id,
        "container_created",
        data_directory_created=True,
        network_created=True,
        container_created=True,
        docker_network_id="network-id",
        docker_container_id="container-id",
    )
    with pytest.raises(ProvisioningFailedError):
        service.provision("inconsistent", provision_request)
    result = service.get(attempt.id)
    assert result.state == "inconsistent"
    assert not any(call.startswith("remove_") for call in adapter.calls)


def allocation(settings: RedroidProvisioningSettings, path: Path, provisioning_id: str = "attempt") -> ProvisioningAllocation:
    return ProvisioningAllocation(provisioning_id, "token", 3, "redroid-device-03", 5557, "localhost:5557", path, "redroid-device-03-net", settings.image_reference, settings.installation_id)


def test_filesystem_cleanup_requires_matching_marker_and_empty_directory(settings) -> None:
    adapter = RedroidProvisioningAdapter(settings)
    item = allocation(settings, settings.data_root.resolve() / "device-03-data")
    assert adapter.create_owned_data_directory(item) is True
    (item.data_path / "foreign").write_text("preserve", encoding="utf-8")
    with pytest.raises(ProvisioningOwnershipError, match="unexpected"):
        adapter.remove_owned_data_directory(item)
    assert item.data_path.exists()


def test_filesystem_rejects_symlink_and_path_traversal(settings, tmp_path: Path) -> None:
    adapter = RedroidProvisioningAdapter(settings)
    outside = tmp_path / "outside"; outside.mkdir()
    link = settings.data_root / "device-03-data"; link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProvisioningOwnershipError, match="symlink"):
        adapter.create_owned_data_directory(allocation(settings, link))
    with pytest.raises(ProvisioningOwnershipError, match="outside"):
        adapter.create_owned_data_directory(allocation(settings, outside))


def test_foreign_container_is_preserved_on_rollback(settings, monkeypatch) -> None:
    adapter = RedroidProvisioningAdapter(settings)
    item = allocation(settings, settings.data_root.resolve() / "device-03-data")
    foreign = {"Id": "container-id", "Config": {"Labels": {}}, "State": {"Status": "created", "StartedAt": "0001-01-01T00:00:00Z"}}
    monkeypatch.setattr(adapter, "inspect_container", lambda _: foreign)
    run = SimpleNamespace()
    monkeypatch.setattr(adapter, "_run", lambda *args, **kwargs: run)
    with pytest.raises(ProvisioningOwnershipError, match="labels"):
        adapter.remove_owned_container(item, "container-id")


def test_adapter_rejects_arbitrary_docker_resource_names(settings, monkeypatch) -> None:
    adapter = RedroidProvisioningAdapter(settings)
    item = allocation(settings, settings.data_root.resolve() / "device-03-data")
    unsafe = ProvisioningAllocation(
        **{**item.__dict__, "container_name": "client-supplied-name"}
    )
    monkeypatch.setattr(
        adapter,
        "_run",
        lambda *args, **kwargs: pytest.fail("Docker must not be called"),
    )
    with pytest.raises(ProvisioningOwnershipError, match="trusted"):
        adapter.create_container(unsafe)


def test_verify_rejects_started_container(settings, monkeypatch) -> None:
    adapter = RedroidProvisioningAdapter(settings)
    item = allocation(settings, settings.data_root.resolve() / "device-03-data")
    inspected = {
        "Id": "container-id",
        "Config": {"Image": item.image_reference, "Labels": item.labels("container")},
        "State": {"Status": "running", "Running": True},
        "HostConfig": {}, "Mounts": [], "NetworkSettings": {"Networks": {}},
    }
    monkeypatch.setattr(adapter, "inspect_container", lambda _: inspected)
    with pytest.raises(ProvisioningVerificationError, match="created state"):
        adapter.verify_container(item, "container-id")
