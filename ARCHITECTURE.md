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
- Android automation resolves an explicit Runtime ID to its database-owned ADB
  serial and container name immediately before every operation. Callers cannot
  provide either host identifier.
- Runtime mutations use one host-local, cross-process `flock` identity per
  Runtime. Lifecycle, screen, network, and automation operations therefore
  fail safely instead of controlling the same Android Runtime concurrently.
- Automation artifacts are stored beneath the private per-user application
  data directory. Results expose generated artifact IDs and safe metadata,
  never arbitrary host paths or raw screenshot bytes.
- Artifact writes and scheduled retention cleanup share a cross-process lock.
  A total-byte quota prevents unbounded growth; artifact bytes may expire while
  immutable Job and JobLog history remains available.
- Reusable library media is modeled separately from JobArtifact execution
  input/output. Logical ContentAssets own immutable versions, while
  SHA-256-addressed ContentBlobs provide physical deduplication beneath the
  private per-user content root. Content has its own quota and is never evicted
  by JobArtifact retention or quota cleanup.
- Content upload admission performs bounded signature, filename, extension,
  and MIME checks without executing uploaded bytes. It atomically creates a
  runtime-free internal `content.inspect` Job. Workers call the backend
  inspection boundary, which serializes each immutable version with a private
  cross-process lock, authoritatively decodes images with Pillow or probes
  local video/audio with a constrained ffprobe process, and atomically selects
  only a validated ready current version. Processing is idempotent and
  lease/cancellation/retry fenced; it never uses a Runtime lock or ADB.
- Failed replacement inspection leaves the previous ready current version in
  service. Processing recovery can recreate a missing or retryably failed
  inspection Job from the durable version pointer.
- Ready visual versions reconcile to an internal `content.thumbnail` Job.
  Pillow or constrained trusted ffmpeg creates one bounded card profile as a
  deduplicated ContentBlob. Variant failure does not invalidate the source.
- Content delivery pins one ready immutable version and exact Runtime before
  creating an internal `content.deliver` Job. The backend verifies the private
  ContentBlob and passes a typed managed-file source to AndroidAutomationService;
  workers receive IDs only. Delivery shares the Runtime operation lock and can
  write only below `/sdcard/Download/TikTokManager/`.
- Daily content maintenance reclaims only stale generated staging and
  grace-aged proven-unreferenced blobs. Content has no age expiry; ready and
  historically referenced bytes are not quota-evicted.
- Workflow orchestration is a durable control plane above Jobs, never a second
  execution queue. Server-owned versioned templates materialize immutable,
  sequential WorkflowStep rows; the orchestrator observes linked Job outcomes
  and advances one step at a time under a per-Workflow cross-process lock.
  Runtime and ready ContentAssetVersion bindings are pinned when a Workflow is
  created, and no recovery path silently retargets either binding.
- The workflow orchestrator is an independent user service. It creates Jobs
  only through typed service adapters, never claims Jobs, runs ADB, or accepts
  caller-defined steps/payloads. Durable approval and pause/cancel boundaries
  survive backend, worker, and orchestrator restarts.
- Sequential reconciliation reloads each candidate under its exact Workflow
  lock, treats the linked Job row as execution truth, and commits at most one
  newly eligible step. Durable `workflow.wait` steps persist one UTC deadline
  and are revisited by bounded polling without a timer thread or Job. Pause
  never interrupts an active Job; cancellation waits for terminal truth and
  never advances a successor.
- Orchestrator infrastructure failures use bounded exponential backoff, and
  reconciliation transactions remain short: no SQLite write lock spans Job
  execution or external Android work. Application SQLite connections enforce
  foreign keys on connect. Managed provisioning assigns Device/Runtime IDs
  above live and historical provisioning IDs so immutable Runtime snapshots
  are never retargeted by SQLite primary-key reuse.
- General transcoding and application UI automation remain later operations.
- Device Jobs use a typed registry and a lease-protected backend execution
  boundary. Workers receive complete execution context but never execute ADB;
  every heartbeat and terminal mutation is fenced by a hashed claim token and
  attempt number.
- The installed user-level automation worker starts after the backend, uses
  bounded reconnect backoff, and relies only on durable backend claims and
  leases for crash recovery.
- Deprovision rejects a Runtime with active automation and cancels queued
  `device.*` Jobs for that exact Runtime without redirecting them.
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
