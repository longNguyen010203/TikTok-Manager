# Workflow operations runbook

TikTok Manager workflows are durable orchestration records. Jobs remain the
execution unit, and SQLite is the source of truth. Do not edit workflow, step,
Job, delivery, lease, or lock rows by hand.

## Service status and restart

Normal Ubuntu login starts the backend, worker, workflow orchestrator, and
maintenance timers through the user systemd manager. No recurring terminal
command is required.

```bash
systemctl --user status tiktok-manager-backend.service
systemctl --user status tiktok-manager-worker.service
systemctl --user status tiktok-manager-workflow-orchestrator.service
systemctl --user status tiktok-manager-artifact-cleanup.timer
systemctl --user status tiktok-manager-content-cleanup.timer
```

Restart one service at a time when diagnosing a problem. The backend should be
healthy before restarting the worker or orchestrator.

```bash
systemctl --user restart tiktok-manager-backend.service
systemctl --user restart tiktok-manager-worker.service
systemctl --user restart tiktok-manager-workflow-orchestrator.service
```

Inspect bounded, sanitized service logs with:

```bash
journalctl --user -u tiktok-manager-backend.service --since "15 minutes ago"
journalctl --user -u tiktok-manager-worker.service --since "15 minutes ago"
journalctl --user -u tiktok-manager-workflow-orchestrator.service --since "15 minutes ago"
```

## Stuck-workflow diagnostics

1. Open Workflow detail and inspect its ordered steps and event timeline.
2. Follow the linked Job and inspect its structured timeline and safe error
   code. A pending/running/retrying Job remains authoritative for its step.
3. Check backend, worker, and orchestrator status. Restarting a service is
   safe; do not create a replacement Job or Delivery manually.
4. For `RUNTIME_BUSY`, allow the current Runtime operation and normal Job retry
   policy to finish. For `RUNTIME_STOPPED` or `RUNTIME_SCREEN_ACTIVE`, correct
   the explicit condition before requesting a retry.
5. A wait uses its persisted `resume_at`; service restarts do not reset it.
   Approval steps require an explicit operator decision.

Retry only a failed Workflow when the UI offers Retry. The backend rejects
exhausted, non-retryable, or uncertain work rather than replaying it. Cancel
through the Workflow UI/API: cancellation prevents successors and cooperates
with the linked Job until terminal truth is known. Do not kill ADB, worker, or
bridge processes to cancel one Workflow.

Deprovision never redirects pinned work. Active Runtime work can block unsafe
deprovision; pending/retrying work is cancelled or fails durably, and the
immutable Runtime snapshot remains in history. Resolve or cancel active work
before retrying managed deprovision.

## Backup and managed files

The canonical database is
`~/.local/share/tiktok-manager/tiktok_manager.db`. Back it up with services
quiesced or with a SQLite-safe online backup. Encrypted proxy credentials also
require the matching `~/.config/tiktok-manager/credentials.key` backup.

Do not manually delete the database, credential key, application config,
artifact/content storage, Runtime data directories, systemd bridge state, or
lock files. Lock files are harmless persistent inode names; ownership is the
live `flock`, which the OS releases on process death. Use supported cleanup,
deprovision, archive/delete, retry, and cancel operations instead.
