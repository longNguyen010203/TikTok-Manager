"""Tests for lifecycle recovery state."""

from worker.recovery import LifecycleRecoveryStore, PendingLifecycleReport


def test_recovery_store_protects_against_duplicate_job_reports() -> None:
    store = LifecycleRecoveryStore()
    first = PendingLifecycleReport(
        {"id": 7}, "succeed", {"message": "first"}
    )
    duplicate = PendingLifecycleReport(
        {"id": 7}, "fail", "should not replace first"
    )

    assert store.add(first) is True
    assert store.add(duplicate) is False
    assert len(store) == 1
    assert store.next() is first

    store.complete(7)

    assert len(store) == 0
    assert store.next() is None
