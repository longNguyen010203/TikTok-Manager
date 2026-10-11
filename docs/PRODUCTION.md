# Production Operations

TIK-027R Phase 1 prepares production isolation; it does not perform the
cutover. The currently installed user services must not be edited or restarted
until the Phase 2 release window.

## Phase 1 host audit

The installed files inspected under `~/.config/systemd/user` still point the
backend, worker, workflow orchestrator, and cleanup processes at
`~/Desktop/MMO/TikTok-Manager-codex`. The backend binds 8000 and carries the
legacy production flag; the worker pins backend port 8000 but its installed
unit has no environment selector. Default-target/timer symlinks exist. The
execution environment could not connect to the user systemd bus, so live PID
and activation state was not asserted. Phase 1 did not edit these installed
files or invoke `systemctl`.

Before this change, the backend database and most persistent files defaulted
to the unsuffixed per-user roots regardless of development intent, Alembic
inherited that database resolution, the worker defaulted to port 8000, and
backend startup always ran live Docker/Binder/ADB/Runtime/network inspection
and reconciliation. The frontend already supports
`NEXT_PUBLIC_API_BASE_URL`; its example currently names port 8000 and no
frontend file was changed.

## Production contract

| Item | Production value |
| --- | --- |
| Environment | `TIKTOK_MANAGER_ENV=production` |
| Release worktree | `~/Desktop/MMO/TikTok-Manager-prod` at an exact immutable tag |
| Backend | `127.0.0.1:8000` |
| Frontend API | `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` |
| Database | `~/.local/share/tiktok-manager/tiktok_manager.db` |
| Data/artifacts/content/backups | `~/.local/share/tiktok-manager/` |
| Configuration/key | `~/.config/tiktok-manager/` |
| Runtime bridge state | `/run/user/<uid>/tiktok-manager/` |
| Host lock state | `/tmp/tiktok-manager/` |

The legacy `TIKTOK_MANAGER_RUNTIME_MODE=production` remains a compatibility
alias only when `TIKTOK_MANAGER_ENV` is absent. New units must set the new
variable. The pre-TIK-027R worker's explicit loopback port-8000 URL is also
recognized as a narrow compatibility signal when both environment variables
are absent. `DATABASE_URL`, when supplied in production, is accepted only if it
resolves to the canonical production SQLite file.

The Redroid data root already installed on this host may remain the configured
legacy `~/redroid-test` path; it must not be moved during this preparation
phase. Production startup retains the existing Docker/Binder/ADB/runtime and
network reconciliation behavior.

## Prepared systemd units

The proposed units are
`deploy/production/tiktok-manager-backend.service` and
`deploy/production/tiktok-manager-worker.service`. Their `WorkingDirectory`
and `ExecStart` values use only `~/Desktop/MMO/TikTok-Manager-prod`, the backend
binds port 8000, and both processes explicitly select production. They are
repository assets, not active installed units.

Do not copy them into `~/.config/systemd/user`, reload systemd, or restart a
service in Phase 1.

## Release-local Python environment

After the production worktree has been moved to an approved exact tag in the
Phase 2 window:

```bash
cd ~/Desktop/MMO/TikTok-Manager-prod
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip
backend/.venv/bin/pip install --editable backend --editable workers
```

Never point these units at the Codex or development virtual environment.

## Consistent database backup

The helper uses Python's SQLite online backup API, verifies the new database
with `PRAGMA integrity_check`, creates a mode-0600 timestamped file using
exclusive creation, and never overwrites an existing backup:

```bash
cd ~/Desktop/MMO/TikTok-Manager-prod
TIKTOK_MANAGER_ENV=production scripts/release/backup_prod_db.sh
```

Output is the new path under
`~/.local/share/tiktok-manager/backups/`. A `.failed` file may remain for
forensics if backup or verification fails. No migration is performed.

Project-managed file logs do not exist; services log to the systemd user
journal.
