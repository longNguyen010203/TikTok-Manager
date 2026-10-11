# Release and Rollback Process

No command in this document is authorized for TIK-027R Phase 1. Execute the
workflow only in an approved Phase 2 maintenance window.

## Release flow

1. Merge `codex/backend` and `agy/frontend` into `develop`; never deploy either
   agent branch.
2. Run backend tests, worker tests, Python compilation, frontend lint/typecheck,
   and `git diff --check` on `develop`.
3. Complete manual validation on development ports and state.
4. Record release approval, merge `develop` to `main`, and create a new
   immutable annotated release tag. Never move `v0.1.0-mvp`.
5. Put `~/Desktop/MMO/TikTok-Manager-prod` at the exact approved tag in detached
   HEAD state and require a clean tree. Run `scripts/release/check_release.sh`.
6. Create `backend/.venv` inside that production worktree and install backend
   and worker dependencies there.
7. Set `TIKTOK_MANAGER_ENV=production` and run
   `scripts/release/backup_prod_db.sh`. Record the printed backup path and
   verify it is separate from the active database.
8. Stop only the relevant production services in the approved window.
9. Review the exact Alembic upgrade path, then run the separately approved
   production migration from the tagged production worktree. No helper in this
   change performs an implicit migration.
10. Install the reviewed production unit definitions, reload the user manager,
    and start/restart backend then worker. Frontend cutover remains a separate
    reviewed action.
11. Run `TIKTOK_MANAGER_ENV=production scripts/release/health_check.sh`, inspect
    user-journal logs, and execute API/worker/frontend smoke tests.

## Application-only rollback

If the database schema remains compatible: stop affected services, return the
production worktree to the previous known-good exact tag, recreate/install its
worktree-local dependencies if needed, install that tag's unit definitions,
restart backend and worker, then run health and smoke checks.

## Schema-affecting rollback

Do not blindly run `alembic downgrade`. If the new schema is not backward
compatible, stop every service that can access production state, preserve the
failed database for diagnosis, restore the recorded pre-release backup to the
canonical database path using an explicitly reviewed offline operation, return
the production worktree to the previous known-good exact tag, restart services,
and verify health plus domain smoke tests. Restoration must occur only while
the backend, worker, orchestrator, and maintenance writers are stopped.

## Phase 2 cutover checklist

- [ ] Confirm release approval, maintenance window, and rollback owner.
- [ ] Confirm `develop` validation and manual acceptance are complete.
- [ ] Merge `develop` to `main`; create a new immutable annotated tag.
- [ ] Confirm `v0.1.0-mvp` is unchanged.
- [ ] Stop production writers only in the approved window.
- [ ] Set the production worktree to the approved exact tag; verify detached,
      clean state with `check_release.sh`.
- [ ] Create `TikTok-Manager-prod/backend/.venv`; install tagged backend and
      worker dependencies without referencing an agent virtualenv.
- [ ] Capture current installed unit definitions and service status.
- [ ] Run the SQLite backup helper; record path, permissions, size, and
      successful integrity result.
- [ ] Review migration current/head revisions and SQL/operations.
- [ ] Run only the approved production migration with
      `TIKTOK_MANAGER_ENV=production`; verify the canonical DB path first.
- [ ] Install the reviewed production backend and worker units from the tag;
      daemon-reload.
- [ ] Verify all production `ExecStart`/`WorkingDirectory` paths contain only
      `TikTok-Manager-prod`, port 8000, and explicit production environment.
- [ ] Start backend, run health check, and inspect logs.
- [ ] Start worker; confirm registration/heartbeat and production queue access.
- [ ] Start remaining approved production units and frontend; verify frontend
      API base URL is port 8000.
- [ ] Run Device/Runtime/Account, topology, content, job, and worker smoke tests.
- [ ] Confirm development port 8001 and development DB/state remain independent.
- [ ] If any gate fails, execute the appropriate documented rollback and retain
      the failed release state for diagnosis.
