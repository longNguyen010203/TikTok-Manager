"""Desired-state, schema, allocation, and isolation tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import init_db
from app.models import (
    Device,
    Runtime,
    RuntimeNetworkConfig,
    RuntimeNetworkConfigRevision,
    RuntimeNetworkState,
)
from app.services.network_config import RuntimeNetworkSettings
from app.services.network_operation_lock import RuntimeNetworkOperationGuard
from app.services.network_validation import NetworkValidationError
from app.services.runtime_network import (
    BridgePortAllocator,
    BridgePortUnavailable,
    DesiredNetworkInput,
    RuntimeNetworkRevisionConflict,
    RuntimeNetworkService,
    add_default_direct_network_config,
)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    result = create_engine(f"sqlite:///{tmp_path / 'network.db'}")

    @event.listens_for(result, "connect")
    def enable_foreign_keys(dbapi_connection, _) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(result)
    yield result
    result.dispose()


def add_runtime(session: Session, suffix: str, *, status: str = "stopped") -> Runtime:
    device = Device(
        name=f"Device {suffix}", device_type="emulator", platform="android",
        os_version="12", status="offline",
    )
    runtime = Runtime(
        name=f"Runtime {suffix}", runtime_type="redroid", status=status,
        docker_container_name=f"redroid-{suffix}", adb_serial=f"localhost:55{suffix}",
    )
    device.runtimes.append(runtime)
    session.add(device)
    session.commit()
    return runtime


def service(
    session: Session,
    tmp_path: Path,
    start: int = 18800,
    end: int = 18810,
    port_probe=None,
) -> RuntimeNetworkService:
    settings = RuntimeNetworkSettings(
        bridge_port_start=start,
        bridge_port_end=end,
        bridge_device_port=18888,
        lock_directory=tmp_path / "locks",
    )
    guard = RuntimeNetworkOperationGuard(settings.lock_directory)
    allocator = BridgePortAllocator(
        settings,
        guard,
        port_probe=port_probe or (lambda _host, _port: True),
    )
    return RuntimeNetworkService(
        session,
        settings=settings,
        guard=guard,
        port_allocator=allocator,
    )


def proxy_input(host: str = "proxy.example.net") -> DesiredNetworkInput:
    return DesiredNetworkInput(
        mode="http_proxy",
        proxy_host=host,
        proxy_port=3128,
        proxy_username_secret_ref="env:TIKTOK_PROXY_TEST_USERNAME",
        proxy_password_secret_ref="env:TIKTOK_PROXY_TEST_PASSWORD",
    )


def test_absent_config_is_unmanaged(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "01")
        view = service(session, tmp_path).read_desired(runtime.id)
        assert view.managed is False
        assert view.mode == "direct"
        assert view.desired_revision == 0


def test_direct_and_http_proxy_database_constraints(engine: Engine) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session, "02")
        session.add(
            RuntimeNetworkConfig(
                runtime_id=runtime.id,
                mode="direct",
                proxy_host="should-not-exist.example",
                desired_revision=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            RuntimeNetworkConfig(
                runtime_id=runtime.id,
                mode="http_proxy",
                proxy_host="proxy.example",
                proxy_port=70000,
                bridge_host_port=8801,
                bridge_device_port=8888,
                desired_revision=1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_one_config_per_runtime_and_revision_unique(engine: Engine) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session, "03")
        session.add_all(
            [
                RuntimeNetworkConfig(runtime_id=runtime.id, mode="direct", desired_revision=1),
                RuntimeNetworkConfig(runtime_id=runtime.id, mode="direct", desired_revision=2),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add_all(
            [
                RuntimeNetworkConfigRevision(runtime_id=runtime.id, revision=1, mode="direct"),
                RuntimeNetworkConfigRevision(runtime_id=runtime.id, revision=1, mode="direct"),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_revision_monotonicity_and_optimistic_conflict(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "04")
        network = service(session, tmp_path)
        first = network.create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)
        second = network.create_or_update_desired(runtime.id, proxy_input("proxy2.example.net"), expected_revision=1)
        assert (first.desired_revision, second.desired_revision) == (1, 2)
        revisions = session.scalars(
            select(RuntimeNetworkConfigRevision.revision)
            .where(RuntimeNetworkConfigRevision.runtime_id == runtime.id)
            .order_by(RuntimeNetworkConfigRevision.revision)
        ).all()
        assert revisions == [1, 2]
        with pytest.raises(RuntimeNetworkRevisionConflict):
            network.create_or_update_desired(runtime.id, proxy_input(), expected_revision=1)


@pytest.mark.parametrize(
    "desired",
    [
        DesiredNetworkInput(mode="direct", proxy_host="proxy.example"),
        DesiredNetworkInput(mode="http_proxy", proxy_host=None, proxy_port=3128),
        DesiredNetworkInput(mode="http_proxy", proxy_host="https://proxy.example", proxy_port=3128),
        DesiredNetworkInput(mode="http_proxy", proxy_host="proxy.example", proxy_port=0),
    ],
)
def test_desired_validation(engine: Engine, tmp_path: Path, desired: DesiredNetworkInput) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session, "05")
        with pytest.raises(NetworkValidationError):
            service(session, tmp_path).create_or_update_desired(runtime.id, desired, expected_revision=0)


def test_stopped_runtime_http_update_is_pending_without_external_calls(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "06", status="stopped")
        view = service(session, tmp_path).create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)
        state = session.get(RuntimeNetworkState, runtime.id)
        assert view.mode == "http_proxy"
        assert state is not None
        assert state.status == "pending"
        assert state.applied_revision is None
        assert state.bridge_status == "stopped"


def test_observed_state_update_checks_revision_and_sanitizes_error(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "13")
        network = service(session, tmp_path)
        network.create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)
        state = network.update_observed_state(
            runtime.id,
            desired_revision=1,
            status="failed",
            observed_mode="http_proxy",
            bridge_status="unhealthy",
            error_code="UPSTREAM_UNREACHABLE",
            error_message=(
                "failed https://fake-user:fake-password@proxy.example "
                "using env:TIKTOK_PROXY_TEST_PASSWORD"
            ),
            verified=True,
        )
        assert "fake-password" not in (state.error_message or "")
        assert "TIKTOK_PROXY_TEST_PASSWORD" not in (state.error_message or "")
        assert state.last_verified_at is not None
        with pytest.raises(RuntimeNetworkRevisionConflict):
            network.update_observed_state(
                runtime.id,
                desired_revision=2,
                status="ready",
            )


def test_bridge_ports_are_unique_and_runtime_updates_are_isolated(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime_a = add_runtime(session, "07")
        runtime_b = add_runtime(session, "08")
        network = service(session, tmp_path, start=18820, end=18822)
        a1 = network.create_or_update_desired(runtime_a.id, proxy_input("a.example"), expected_revision=0)
        b1 = network.create_or_update_desired(runtime_b.id, proxy_input("b.example"), expected_revision=0)
        a2 = network.create_or_update_desired(runtime_a.id, proxy_input("a2.example"), expected_revision=1)
        assert a1.bridge_host_port != b1.bridge_host_port
        assert a2.bridge_host_port == a1.bridge_host_port
        unchanged_b = network.read_desired(runtime_b.id)
        assert unchanged_b.proxy_host == "b.example"
        assert unchanged_b.desired_revision == 1


def test_occupied_host_port_is_never_selected(engine: Engine, tmp_path: Path) -> None:
    with Session(engine) as session:
        runtime = add_runtime(session, "09")
        with pytest.raises(BridgePortUnavailable):
            service(
                session,
                tmp_path,
                start=18830,
                end=18830,
                port_probe=lambda _host, _port: False,
            ).create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)


def test_direct_transition_reserves_port_until_cleanup_completes(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "10")
        other = add_runtime(session, "14")
        network = service(session, tmp_path, start=18840, end=18841)
        proxy = network.create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)
        pending = network.switch_to_direct(runtime.id, expected_revision=1, cleanup_complete=False)
        state = session.get(RuntimeNetworkState, runtime.id)
        assert proxy.bridge_host_port is not None
        assert pending.bridge_host_port is None
        assert state is not None and state.status == "pending"
        other_proxy = network.create_or_update_desired(other.id, proxy_input(), expected_revision=0)
        assert other_proxy.bridge_host_port != proxy.bridge_host_port

        direct = network.switch_to_direct(runtime.id, expected_revision=2, cleanup_complete=True)
        assert direct.bridge_host_port is None
        assert state.status == "disabled"
        assert state.applied_revision == 3
        assert network.has_revision_mismatch(runtime.id) is False


def test_default_direct_helper_is_uncommitted_provisioning_foundation(engine: Engine) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "11")
        config = add_default_direct_network_config(session, runtime)
        session.commit()
        assert config.mode == "direct"
        assert session.get(RuntimeNetworkState, runtime.id).status == "disabled"


def test_runtime_delete_cascades_all_network_rows(engine: Engine, tmp_path: Path) -> None:
    with Session(engine, expire_on_commit=False) as session:
        runtime = add_runtime(session, "12")
        service(session, tmp_path).create_or_update_desired(runtime.id, proxy_input(), expected_revision=0)
        runtime_id = runtime.id
        session.delete(runtime)
        session.commit()
        assert session.scalar(select(func.count()).select_from(RuntimeNetworkConfig)) == 0
        assert session.scalar(select(func.count()).select_from(RuntimeNetworkConfigRevision)) == 0
        assert session.get(RuntimeNetworkState, runtime_id) is None
