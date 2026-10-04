"""Safety and recovery tests for managed Redroid deprovisioning."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import init_db
from app.models import (
    Account, ContentAsset, ContentAssetVersion, ContentBlob, ContentDelivery,
    Device, Job, RedroidProvisioning, Runtime,
)
from app.services.redroid_provisioning import (
    DeprovisioningFailedError,
    ProvisioningRequest,
    RedroidProvisioningService,
)
from app.services.redroid_provisioning_adapter import (
    OccupiedResources,
    ProvisioningAllocation,
    ProvisioningOwnershipError,
)
from app.services.redroid_provisioning_config import RedroidProvisioningSettings


class DeprovisionAdapter:
    def __init__(self, *, running: bool = True, fail_at: str | None = None) -> None:
        self.running = running
        self.fail_at = fail_at
        self.container_present = True
        self.network_present = True
        self.data_present = True
        self.calls: list[str] = []

    def _fail(self, stage: str) -> None:
        self.calls.append(stage)
        if self.fail_at == stage:
            raise ProvisioningOwnershipError(f"{stage} ownership failed")

    # Provisioning foundation used to create a realistic completed attempt.
    def preflight(self) -> None: pass
    def occupied_resources(self) -> OccupiedResources:
        return OccupiedResources(frozenset(), frozenset(), frozenset(), frozenset())
    def port_is_available(self, port: int) -> bool: return True
    def create_owned_data_directory(self, allocation: ProvisioningAllocation) -> bool: return True
    def create_network(self, allocation: ProvisioningAllocation) -> str: return "network-id"
    def verify_network(self, allocation: ProvisioningAllocation, network_id: str) -> None: pass
    def create_container(self, allocation: ProvisioningAllocation) -> str: return "container-id"
    def verify_container(self, allocation: ProvisioningAllocation, container_id: str) -> None: pass

    # Deprovisioning safety primitives.
    def verify_owned_data_directory(self, allocation: ProvisioningAllocation) -> None:
        self._fail("data_verify")
        if not self.data_present:
            raise ProvisioningOwnershipError("data missing")

    def require_owned_container_for_removal(self, allocation, container_id):
        self._fail("container_verify")
        if not self.container_present or container_id != "container-id":
            raise ProvisioningOwnershipError("container mismatch")
        return {
            "Id": "container-id",
            "Name": "/redroid-device-01",
            "State": {"Running": self.running},
            "Config": {"Labels": allocation.labels("container")},
        }

    def require_owned_network_for_removal(self, allocation, network_id):
        self._fail("network_verify")
        if not self.network_present or network_id != "network-id":
            raise ProvisioningOwnershipError("network mismatch")
        return {"Id": "network-id", "Name": allocation.network_name}

    def require_removed_container_absent(self, allocation) -> None:
        self._fail("container_absence")
        if self.container_present:
            raise ProvisioningOwnershipError("foreign container occupies name")

    def require_removed_network_absent(self, allocation) -> None:
        self._fail("network_absence")
        if self.network_present:
            raise ProvisioningOwnershipError("foreign network occupies name")

    def remove_verified_container(self, allocation, container_id) -> bool:
        self._fail("container_remove")
        if self.running:
            raise ProvisioningOwnershipError("container running")
        self.container_present = False
        return True

    def remove_verified_network(self, allocation, network_id) -> bool:
        self._fail("network_remove")
        self.network_present = False
        return True

    def remove_owned_network(self, allocation, network_id) -> bool: return True

    # Provision rollback protocol (unused in these successful setup calls).
    def owned_container_id(self, allocation): return None
    def owned_network_id(self, allocation): return None
    def remove_owned_container(self, allocation, container_id): return True
    def remove_owned_data_directory(self, allocation): return True


class FakeScreenManager:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.closed: list[tuple[int, int, str]] = []

    def close(self, device_id: int, runtime_id: int, adb_serial: str) -> object:
        if self.fail:
            raise RuntimeError("screen close failed")
        self.closed.append((device_id, runtime_id, adb_serial))
        return object()


class FakeRuntimeAdapter:
    def __init__(self, docker: DeprovisionAdapter, *, fail: bool = False) -> None:
        self.docker = docker
        self.fail = fail
        self.stopped: list[str] = []

    def stop_container(self, container_name: str) -> str:
        if self.fail:
            raise RuntimeError("stop failed")
        self.stopped.append(container_name)
        self.docker.running = False
        return container_name


class FakeNetworkCleaner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.cleaned: list[int] = []

    def cleanup_before_delete(self, runtime_id: int) -> None:
        if self.fail:
            raise RuntimeError("ambiguous network ownership")
        self.cleaned.append(runtime_id)


@pytest.fixture
def deprovision_context(tmp_path: Path):
    engine = create_engine(
        URL.create("sqlite", database=str(tmp_path / "deprovision.db")),
        connect_args={"check_same_thread": False},
    )
    init_db(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    root = tmp_path / "redroid-data"
    root.mkdir()
    settings = RedroidProvisioningSettings(
        installation_id="deprovision-test",
        image_reference="redroid/redroid@sha256:" + "a" * 64,
        data_root=root,
    )
    yield factory, settings
    engine.dispose()


def completed_service(
    deprovision_context,
    *,
    running=True,
    fail_at=None,
    screen_fail=False,
    stop_fail=False,
    network_fail=False,
):
    factory, settings = deprovision_context
    adapter = DeprovisionAdapter(running=running, fail_at=fail_at)
    screen = FakeScreenManager(fail=screen_fail)
    runtime = FakeRuntimeAdapter(adapter, fail=stop_fail)
    network = FakeNetworkCleaner(fail=network_fail)
    service = RedroidProvisioningService(
        factory,
        adapter,
        settings,
        screen_manager=screen,
        runtime_adapter=runtime,
        network_cleaner=network,
    )
    attempt = service.provision(
        "deprovision-key",
        ProvisioningRequest(name="Managed Device", profile=settings.supported_profile),
    )
    return service, attempt, adapter, screen, runtime


@pytest.mark.parametrize("running", [True, False])
def test_deprovision_removes_owned_resources_and_preserves_data(
    deprovision_context, running
) -> None:
    factory, _ = deprovision_context
    service, attempt, adapter, screen, runtime = completed_service(
        deprovision_context, running=running
    )
    device_id, runtime_id = attempt.device_id, attempt.runtime_id
    with factory() as session:
        account = Account(
            name="Preserved Account",
            username=f"preserved-{running}",
            platform="tiktok",
            status="active",
            runtime_id=runtime_id,
        )
        job = Job(job_type="deprovision-test", runtime_id=runtime_id)
        blob = ContentBlob(
            storage_key=("a" if running else "b") * 32,
            sha256=("c" if running else "d") * 64,
            size_bytes=1,
            detected_mime_type="image/png",
            status="active",
        )
        asset = ContentAsset(
            asset_type="image", display_name="Historical delivery", source="upload",
            status="ready",
        )
        version = ContentAssetVersion(
            version_number=1, blob=blob, original_filename="history.png",
            detected_mime_type="image/png", canonical_extension=".png",
            processing_status="ready",
        )
        asset.versions.append(version)
        session.add_all([account, job, asset])
        session.flush()
        asset.current_version_id = version.id
        delivery_job = Job(job_type="content.deliver", runtime_id=runtime_id)
        session.add(delivery_job)
        session.flush()
        delivery = ContentDelivery(
            content_asset_id=asset.id, content_asset_version_id=version.id,
            runtime_id=runtime_id, runtime_id_snapshot=runtime_id,
            job_id=delivery_job.id, status="succeeded", import_media=False,
            remote_filename="history-d1.png",
            remote_path="/sdcard/Download/TikTokManager/history-d1.png",
        )
        session.add(delivery)
        session.commit()
        account_id, job_id, delivery_id = account.id, job.id, delivery.id

    result = service.deprovision(attempt.id)

    assert result.state == "deprovisioned"
    assert result.container_removed and result.network_removed and result.data_preserved
    assert (result.historical_device_id, result.historical_runtime_id) == (
        device_id, runtime_id
    )
    assert result.device_id is None and result.runtime_id is None
    assert adapter.data_present is True
    assert screen.closed == [(device_id, runtime_id, "localhost:5555")]
    assert service.network_cleaner.cleaned == [runtime_id]
    assert runtime.stopped == (["container-id"] if running else [])
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Device)) == 0
        assert session.scalar(select(func.count()).select_from(Runtime)) == 0
        assert session.get(RedroidProvisioning, attempt.id) is not None
        assert session.get(Account, account_id).runtime_id is None
        assert session.get(Job, job_id).runtime_id is None
        historical_delivery = session.get(ContentDelivery, delivery_id)
        assert historical_delivery.runtime_id is None
        assert historical_delivery.runtime_id_snapshot == runtime_id


def test_repeated_deprovision_is_idempotent(deprovision_context) -> None:
    service, attempt, adapter, screen, _ = completed_service(deprovision_context)
    first = service.deprovision(attempt.id)
    call_count = len(adapter.calls)
    close_count = len(screen.closed)
    second = service.deprovision(attempt.id)
    assert second.state == first.state == "deprovisioned"
    assert len(adapter.calls) == call_count
    assert len(screen.closed) == close_count

    provisioning_retry = service.provision(
        "deprovision-key",
        ProvisioningRequest(
            name="Managed Device", profile=service.settings.supported_profile
        ),
    )
    assert provisioning_retry.state == "deprovisioned"
    assert len(adapter.calls) == call_count


@pytest.mark.parametrize(
    "failure",
    ["data_verify", "container_verify", "network_verify", "container_remove", "network_remove"],
)
def test_deprovision_failure_is_durable_and_preserves_data(
    deprovision_context, failure
) -> None:
    service, attempt, adapter, _, _ = completed_service(
        deprovision_context, fail_at=failure
    )
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    failed = service.get(attempt.id)
    assert failed.state == "deprovision_failed"
    assert failed.error_code == "ProvisioningOwnershipError"
    assert adapter.data_present is True
    if failure in {"data_verify", "container_verify", "network_verify"}:
        assert adapter.container_present and adapter.network_present


@pytest.mark.parametrize("dependency", ["screen", "stop"])
def test_screen_or_stop_failure_prevents_removal(deprovision_context, dependency) -> None:
    service, attempt, adapter, _, _ = completed_service(
        deprovision_context,
        screen_fail=dependency == "screen",
        stop_fail=dependency == "stop",
    )
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    assert adapter.container_present and adapter.network_present and adapter.data_present


def test_network_cleanup_failure_prevents_deprovision_removal(
    deprovision_context,
) -> None:
    service, attempt, adapter, _, _ = completed_service(
        deprovision_context, network_fail=True
    )
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    assert adapter.container_present and adapter.network_present and adapter.data_present


def test_partial_failure_can_resume_without_reallocating(deprovision_context) -> None:
    service, attempt, adapter, _, _ = completed_service(
        deprovision_context, fail_at="network_remove"
    )
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    partial = service.get(attempt.id)
    assert partial.container_removed is True
    assert partial.network_removed is False
    adapter.fail_at = None
    result = service.deprovision(attempt.id)
    assert result.state == "deprovisioned"
    assert result.device_number == 1

    # The durable reservation remains, so the next attempt receives number 2.
    next_attempt = service.get_or_create_request(
        "next-key",
        ProvisioningRequest(name="Next", profile=service.settings.supported_profile),
    )
    reserved = service.reserve(next_attempt.id)
    assert reserved.device_number == 2


def test_foreign_resource_at_removed_name_blocks_retry(deprovision_context) -> None:
    service, attempt, adapter, _, _ = completed_service(
        deprovision_context, fail_at="network_remove"
    )
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    adapter.fail_at = None
    adapter.container_present = True  # A foreign replacement now owns the old name.
    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)
    assert adapter.network_present is True


def test_database_cleanup_failure_retains_recoverable_mapping(
    deprovision_context, monkeypatch
) -> None:
    factory, _ = deprovision_context
    service, attempt, adapter, _, _ = completed_service(deprovision_context)
    monkeypatch.setattr(
        service,
        "_complete_deprovision",
        lambda *_: (_ for _ in ()).throw(RuntimeError("database cleanup failed")),
    )

    with pytest.raises(DeprovisioningFailedError):
        service.deprovision(attempt.id)

    failed = service.get(attempt.id)
    assert failed.state == "deprovision_failed"
    assert failed.container_removed and failed.network_removed
    assert failed.device_id is not None and failed.runtime_id is not None
    assert adapter.data_present is True
    with factory() as session:
        assert session.get(Device, failed.device_id) is not None
        assert session.get(Runtime, failed.runtime_id) is not None
