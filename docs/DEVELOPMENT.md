# Development Environment

Development is explicitly isolated from production.

| Item | Development value |
| --- | --- |
| Environment | `TIKTOK_MANAGER_ENV=development` |
| Integration source | a worktree on `develop` (agent branches merge into it) |
| Backend | `127.0.0.1:8001` |
| Frontend API | `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001` |
| Database | `~/.local/share/tiktok-manager-dev/tiktok_manager.db` |
| Data/artifacts/content/Redroid data | `~/.local/share/tiktok-manager-dev/` |
| Configuration/key | `~/.config/tiktok-manager-dev/` |
| Runtime bridge state | `/run/user/<uid>/tiktok-manager-dev/` |
| Host locks | `/tmp/tiktok-manager-dev/` |
| ADB allocation base | 6554 |
| Redroid/network prefix | `redroid-development-device` |
| Bridge allocation | 9800–9899 |

An unset environment defaults to development as a fail-safe. Development and
production reject each other's database and mutable roots. Development accepts
only its canonical SQLite database, including Alembic. The worker defaults to
port 8001 and rejects port 8000 when configured as development.

Backend startup in development performs the database readiness check but does
not run Docker, Binder, ADB, scrcpy, Runtime, or network startup reconciliation.
Explicit operator calls to development Runtime APIs remain possible; their
records, ADB port range, container/network prefix, bind data, and locks are
development-namespaced. Do not import production Runtime rows into development.

## Initialize and run

Create a worktree-local environment and a clean schema through migrations:

```bash
cd /path/to/develop-worktree
python3 -m venv backend/.venv
backend/.venv/bin/pip install --editable backend --editable workers
cd backend
TIKTOK_MANAGER_ENV=development .venv/bin/alembic upgrade head
TIKTOK_MANAGER_ENV=development .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Run the worker separately:

```bash
cd /path/to/develop-worktree/workers
TIKTOK_MANAGER_ENV=development WORKER_BACKEND_URL=http://127.0.0.1:8001 ../backend/.venv/bin/python -m worker
```

The optional templates under `deploy/development/` contain a
`@DEVELOPMENT_ROOT@` placeholder. Render copies into the user unit directory
only after selecting the actual `develop` worktree. They are intentionally not
enabled automatically.

Frontend source is unchanged. Set the existing frontend environment contract
to `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001`; production remains 8000.

Tests set `TIKTOK_MANAGER_ENV=test` before application imports. Test state lives
under a process-specific temporary root, accepts explicit isolated SQLite test
databases, and rejects the production database.

## Mutable-state inventory

- SQLAlchemy and Alembic use the environment's canonical SQLite file.
- Screenshots and other JobArtifacts use the environment artifact root.
- ContentAsset blobs, thumbnails, inspection staging, and ContentDelivery host
  staging use the environment content/artifact roots. The delivery destination
  `/sdcard/Download/TikTokManager/` is device-local and is reached only through
  an explicitly selected development Runtime.
- Redroid bind data, ADB ports, container/network names, proxy bridge state,
  content/workflow/runtime locks, configuration, and credential keys are
  environment-namespaced.
- The worker has no direct database connection or private artifact path. It
  claims jobs only through its environment-pinned backend URL.
- Temporary test databases and mutable state use a process-specific directory
  under the system temporary directory. No production database is copied.
- Service logs remain in the user journal; there is no project-managed log
  directory to isolate.
- ffmpeg, ffprobe, aapt2, apksigner, application source, and the pinned Redroid
  image reference are immutable/shared inputs rather than mutable state.
