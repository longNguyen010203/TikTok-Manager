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

Database:
- PostgreSQL

Queue/cache:
- Redis

CI:
- GitHub Actions