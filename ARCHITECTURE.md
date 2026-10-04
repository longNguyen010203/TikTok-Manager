# Architecture

## Goal
Build a scalable management platform for legitimate TikTok account/content operations.

## Main components

### Frontend
Location: `frontend/`

Responsibilities:
- dashboard
- account views
- content views
- analytics UI
- job status UI
- API consumption

Primary agent:
- Antigravity

### Backend
Location: `backend/`

Responsibilities:
- REST API
- authentication
- business logic
- validation
- database access

Primary agent:
- Codex

### Workers
Location: `workers/`

Responsibilities:
- background jobs
- scheduled tasks
- media processing
- analytics jobs

Primary agent:
- Codex

### Shared documentation
Location: `docs/`

Contains:
- API contracts
- database schema
- technical decisions

## Initial stack

Frontend:
- Next.js
- TypeScript

Backend:
- FastAPI
- Python

Manager host lifecycle:
- Ubuntu boot initializes Redroid's Binder kernel support through the root-owned
  `redroid-binder.service` oneshot unit. The service does not start Docker,
  TikTok Manager, or Redroid containers.
- Backend startup only verifies that `binder_linux`, binderfs, and the Binder
  endpoints are ready. It never attempts privileged Binder repair.
- The durable application configuration controls whether managed Redroid
  containers are stopped when the API shuts down. The installed local service
  defaults to leaving them running so a backend restart does not interrupt
  Android devices. `STOP_MANAGED_DEVICES_ON_SHUTDOWN` remains an explicit
  development/diagnostic override.
- Shutdown still closes tracked scrcpy sessions. It never stops the Docker
  daemon.
- Shutdown never deletes containers, persistent `/data`, Device records, or
  Runtime records.
- Each managed Redroid lifecycle target uses one Device record with exactly one
  Runtime record. Container name, ADB endpoint, persistent `/data` directory,
  and Docker network are unique per target.
- Redroid containers use private Binder mounts. Host Binder device nodes must
  not be bind-mounted into multiple containers.
- Reproducible Redroid definitions and provisioning steps are documented in
  `deploy/redroid-devices.compose.yml` and
  `docs/REDROID_DEVICE_PROVISIONING.md`.

Database:
- SQLite at the canonical per-user operational path for the current local
  application runtime
- PostgreSQL remains the planned multi-host deployment database

Queue/cache:
- Redis

CI:
- GitHub Actions
