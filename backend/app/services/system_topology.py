"""Fresh normalized Device -> Runtime -> Account Dashboard projection."""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, AccountSecret, Device, Runtime
from app.models.timestamps import utc_now
from app.schemas.dashboard import (
    AccountNodeMetadata,
    AccountTopologyNode,
    DashboardTopology,
    DeviceNodeMetadata,
    DeviceTopologyNode,
    RuntimeNodeMetadata,
    RuntimeTopologyNode,
    TopologyEdge,
    TopologySummary,
)
from app.services.account_registration_lifecycle import registration_ready


ATTENTION_REGISTRATION_STATES = frozenset({"failed"})
ATTENTION_HEALTH_STATUSES = frozenset({"warning", "unhealthy"})
ATTENTION_ACCOUNT_STATUSES = frozenset(
    {"restricted", "suspended", "disabled", "archived"}
)


def build_system_topology(session: Session) -> DashboardTopology:
    """Read the canonical entities in bounded queries and build a stable graph."""
    devices = list(session.scalars(select(Device).order_by(Device.id)))
    runtimes = list(session.scalars(select(Runtime).order_by(Runtime.id)))
    accounts = list(
        session.scalars(
            select(Account)
            .where(Account.archived_at.is_(None))
            .order_by(Account.id)
        )
    )

    account_ids = [account.id for account in accounts]
    secret_account_ids: set[int] = set()
    if account_ids:
        secret_account_ids = set(
            session.scalars(
                select(AccountSecret.account_id)
                .where(AccountSecret.account_id.in_(account_ids))
                .distinct()
            )
        )

    runtime_ids = {runtime.id for runtime in runtimes}
    runtime_device_ids = {runtime.id: runtime.device_id for runtime in runtimes}
    runtime_counts = Counter(runtime.device_id for runtime in runtimes)
    account_counts = Counter(
        account.runtime_id
        for account in accounts
        if account.runtime_id in runtime_ids
    )
    readiness = {
        account.id: registration_ready(
            account, runtime_exists=account.runtime_id in runtime_ids
        )
        for account in accounts
    }

    nodes = [
        DeviceTopologyNode(
            id=f"device:{device.id}",
            type="device",
            entity_id=device.id,
            label=device.name,
            status=device.status,
            metadata=DeviceNodeMetadata(
                name=device.name,
                status=device.status,
                platform=device.platform,
                device_type=device.device_type,
                os_version=device.os_version,
                runtime_count=runtime_counts[device.id],
            ),
        )
        for device in devices
    ]
    nodes.extend(
        RuntimeTopologyNode(
            id=f"runtime:{runtime.id}",
            type="runtime",
            entity_id=runtime.id,
            label=runtime.name,
            status=runtime.status,
            metadata=RuntimeNodeMetadata(
                name=runtime.name,
                status=runtime.status,
                runtime_type=runtime.runtime_type,
                device_id=runtime.device_id,
                assigned_account_count=account_counts[runtime.id],
                last_seen_at=runtime.last_seen_at,
            ),
        )
        for runtime in runtimes
    )
    nodes.extend(
        AccountTopologyNode(
            id=f"account:{account.id}",
            type="account",
            entity_id=account.id,
            label=account.display_name or account.name,
            status=account.status,
            metadata=AccountNodeMetadata(
                display_name=account.display_name or account.name,
                status=account.status,
                registration_state=account.registration_state,
                registration_ready=readiness[account.id],
                registration_completed_at=account.registration_completed_at,
                health_status=account.health_status,
                username=account.username,
                runtime_id=account.runtime_id,
                device_id=(
                    runtime_device_ids.get(account.runtime_id)
                    if account.runtime_id is not None
                    else None
                ),
                secret_present=account.id in secret_account_ids,
            ),
        )
        for account in accounts
    )

    edges = [
        TopologyEdge(
            id=f"device:{runtime.device_id}->runtime:{runtime.id}",
            source=f"device:{runtime.device_id}",
            target=f"runtime:{runtime.id}",
            type="hosts",
        )
        for runtime in runtimes
    ]
    edges.extend(
        TopologyEdge(
            id=f"runtime:{account.runtime_id}->account:{account.id}",
            source=f"runtime:{account.runtime_id}",
            target=f"account:{account.id}",
            type="assigned",
        )
        for account in accounts
        if account.runtime_id in runtime_ids
    )

    ready_accounts = sum(readiness.values())
    attention_accounts = sum(_account_needs_attention(account) for account in accounts)
    return DashboardTopology(
        generated_at=utc_now(),
        summary=TopologySummary(
            devices=len(devices),
            runtimes=len(runtimes),
            accounts=len(accounts),
            ready_accounts=ready_accounts,
            not_ready_accounts=len(accounts) - ready_accounts,
            attention_accounts=attention_accounts,
        ),
        nodes=nodes,
        edges=edges,
    )


def _account_needs_attention(account: Account) -> bool:
    return (
        account.registration_state in ATTENTION_REGISTRATION_STATES
        or account.health_status in ATTENTION_HEALTH_STATUSES
        or account.status in ATTENTION_ACCOUNT_STATUSES
    )
