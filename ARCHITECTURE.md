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
- `STOP_MANAGED_DEVICES_ON_SHUTDOWN` controls whether managed Redroid
  containers are stopped when the API shuts down.
- The default is `true`. Use this for the normal TikTok Manager runtime so
  managed devices are stopped cleanly.
- Set it to `false` during development with `uvicorn --reload`. Reload shutdown
  still closes tracked scrcpy sessions but leaves Redroid containers running.
- Shutdown never deletes containers, persistent `/data`, Device records, or
  Runtime records.

Database:
- PostgreSQL

Queue/cache:
- Redis

CI:
- GitHub Actions
