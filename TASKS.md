# Tasks

## Status values
- TODO
- IN_PROGRESS
- REVIEW
- DONE
- BLOCKED

---

## TIK-001
Status: TODO
Owner: Codex
Type: Backend

Title:
Create backend project skeleton

Scope:
- backend/

Requirements:
- initialize FastAPI
- create health endpoint
- add basic project structure
- add test for health endpoint

Acceptance criteria:
- backend starts successfully
- GET /health returns 200
- tests pass

---

## TIK-002
Status: TODO
Owner: Antigravity
Type: Frontend

Title:
Create frontend project skeleton

Scope:
- frontend/

Requirements:
- initialize Next.js with TypeScript
- create basic dashboard layout
- create placeholder home page

Acceptance criteria:
- npm run build passes
- development server starts

---

## TIK-003
Status: TODO
Owner: Codex
Type: Backend

Title:
Create account database model

Scope:
- backend/
- docs/

Requirements:
- add Account model
- fields:
  - id
  - name
  - username
  - platform
  - status
  - notes
  - created_at
  - updated_at
- add database configuration
- use SQLAlchemy
- use SQLite for local development initially
- document schema in docs/database.md

Acceptance criteria:
- database initializes successfully
- Account table can be created
- model tests pass

---

## TIK-004
Status: TODO
Owner: Codex
Type: Backend

Title:
Create Account CRUD API

Dependencies:
- TIK-003

Scope:
- backend/
- docs/API_CONTRACT.md

Requirements:
- GET /accounts
- GET /accounts/{id}
- POST /accounts
- PATCH /accounts/{id}
- DELETE /accounts/{id}
- validation with Pydantic
- pagination for list endpoint
- status filtering
- proper 404 responses

Acceptance criteria:
- all endpoints work
- API tests pass
- API contract is documented

---

## TIK-005
Status: TODO
Owner: Antigravity
Type: Frontend

Title:
Build Account Management dashboard

Dependencies:
- TIK-004

Scope:
- frontend/

Requirements:
- accounts table
- columns:
  - name
  - username
  - platform
  - status
  - updated_at
- search input
- status filter
- pagination UI
- create account button
- loading state
- empty state
- error state
- responsive layout

Acceptance criteria:
- npm run build passes
- lint passes
- dashboard works with mock API data

---

## TIK-006
Status: TODO
Owner: Antigravity
Type: Frontend Integration

Dependencies:
- TIK-004
- TIK-005

Scope:
- frontend/

Requirements:
- replace mock account data with backend API
- GET /accounts integration
- create account form
- update account
- delete account
- handle API errors

Acceptance criteria:
- frontend communicates successfully with backend
- CRUD flow works through UI
- npm run build passes

---

## TIK-007
Status: TODO
Owner: Codex
Type: Integration

Dependencies:
- TIK-004
- TIK-006

Scope:
- backend/
- tests/

Requirements:
- integration tests for account CRUD
- test pagination
- test status filtering
- test invalid input
- test missing account

Acceptance criteria:
- all integration tests pass

---

## TIK-008
Status: TODO
Owner: Codex
Type: Backend / Database

Title:
Add Alembic database migrations

Dependencies:
- TIK-003
- TIK-004
- TIK-007

Scope:
- backend/
- docs/

Requirements:
- add Alembic
- configure it to use the existing SQLAlchemy metadata
- create an initial migration for the accounts table
- document local migration commands
- development database must be creatable using migrations
- do not modify frontend/

Acceptance criteria:
- `alembic upgrade head` creates the accounts table
- `alembic current` reports the latest revision
- existing backend tests still pass

---

## TIK-009
Status: TODO
Owner: Codex
Type: Backend / Database

Title:
Add Device and Runtime management foundation

Dependencies:
- TIK-008

Scope:
- backend/
- docs/

Requirements:
- add Device model
- add Runtime model
- define relationship:
  - one Device can have multiple Runtime records
  - one Account may optionally be assigned to one Runtime
- add fields for Device:
  - id
  - name
  - device_type
  - platform
  - os_version
  - status
  - notes
  - created_at
  - updated_at
- add fields for Runtime:
  - id
  - device_id
  - name
  - runtime_type
  - status
  - last_seen_at
  - created_at
  - updated_at
- add optional runtime_id to Account
- create Alembic migration
- add CRUD API for Device
- add CRUD API for Runtime
- add tests
- update docs/database.md
- update docs/API_CONTRACT.md
- do not modify frontend/

Acceptance criteria:
- migrations apply successfully
- device CRUD works
- runtime CRUD works
- account can reference a runtime
- deleting an assigned runtime is handled safely
- full backend test suite passes

---

## TIK-010
Status: TODO
Owner: Antigravity
Type: Frontend

Title:
Build Device and Runtime Management UI

Dependencies:
- TIK-009

Scope:
- frontend/

Phases:
1. Device dashboard
2. Runtime dashboard
3. Account ↔ Runtime assignment UI

Acceptance criteria:
- Device CRUD works from UI
- Runtime CRUD works from UI
- Account runtime assignment works from UI
- build and lint pass

---

## TIK-011
Status: TODO
Owner: Codex
Type: Backend / Job System

Title:
Add Job execution foundation

Dependencies:
- TIK-009
- TIK-010

Scope:
- backend/
- docs/

Phases:
1. Job model + migration
2. Job CRUD API
3. Job claiming + lifecycle
4. Retry + logs + failure handling
5. Full verification

Acceptance criteria:
- jobs can be created and persisted
- jobs can target an account/runtime
- job lifecycle is tracked
- retries and failures are represented safely
- full backend test suite passes

---

## TIK-012
Status: TODO
Owner: Antigravity
Type: Frontend / Job Queue

Title:
Build Job Queue dashboard

Dependencies:
- TIK-011

Scope:
- frontend/

Phases:
1. Job list + filters + pagination
2. Job detail + logs
3. Retry + cancel actions
4. Final verification

Acceptance criteria:
- jobs can be viewed and filtered
- job details and logs are visible
- failed jobs can be retried
- eligible jobs can be cancelled
- build and lint pass

---

## TIK-013
Status: TODO
Owner: Codex
Type: Backend / Worker System

Title:
Add Worker Execution Layer

Dependencies:
- TIK-011
- TIK-012

Scope:
- backend/
- workers/
- docs/

Phases:
1. Worker skeleton + polling loop
2. Job handler registry
3. Success/failure reporting
4. Retry/backoff integration
5. Final verification

Acceptance criteria:
- worker can poll and claim jobs
- jobs are dispatched to handlers
- success/failure updates lifecycle correctly
- logs are written
- retry rules are respected
- worker shuts down cleanly

---

## TIK-014
Status: DONE
Owner: Codex
Type: Backend / Device Runtime

Title:
Integrate Redroid Device Runtime

Dependencies:
- TIK-009
- TIK-013

Scope:
- backend/
- docs/

Phases:
1. Redroid Runtime Adapter
2. Runtime Configuration
3. Device Lifecycle API
4. Real Redroid Integration Test
5. Final verification

Acceptance criteria:
- Redroid container status can be inspected
- Redroid containers can be started, stopped, and restartedgit merge main
- Android boot readiness can be detected
- ADB readiness can be verified
- Runtime records can store Redroid connection/configuration data
- Device lifecycle endpoints control real Redroid runtimes
- stop does not delete persistent device data
- real redroid-device-01 integration test passes
- backend tests pass

---

## TIK-015
Status: DONE
Owner: Antigravity
Type: Frontend / Device Management

Title:
Add Real Device Lifecycle Controls

Dependencies:
- TIK-010
- TIK-014

Scope:
- frontend/

Phases:
1. Real device status + refresh
2. Start / stop / restart controls
3. Runtime information + UX polish
4. Final verification

Acceptance criteria:
- real device lifecycle status is visible
- container state is visible
- Android boot state is visible
- ADB state is visible
- device readiness is clearly shown
- device status can be refreshed manually
- devices can be started from the UI
- devices can be stopped from the UI
- devices can be restarted from the UI
- lifecycle action loading and error states are handled
- existing search, filter, and pagination continue to work
- frontend build and lint pass

---

## TIK-016
Status: DONE
Owner: Codex + Antigravity
Type: Device Host Lifecycle / Screen Control

Title:
Add Device Screen Control and Manager Host Lifecycle

Dependencies:
- TIK-014
- TIK-015

Scope:
- backend/
- frontend/
- docs/

Phases:
1. Screen Control Backend
2. Manager Startup / Shutdown Lifecycle
3. Screen Control Frontend
4. Real Integration Test
5. Final Verification

Acceptance criteria:
- a Redroid device screen can be opened with scrcpy from TikTok Manager
- duplicate screen sessions are handled safely
- closing scrcpy does not stop the device
- TikTok Manager startup verifies Docker availability
- Redroid containers are not automatically started on manager startup
- graceful TikTok Manager shutdown stops managed Redroid containers
- stopping the manager never deletes persistent device data
- frontend exposes Open Screen / View Device
- existing lifecycle controls continue to work
- backend tests, frontend lint, and frontend build pass

---

## TIK-017
Status: DONE
Owner: Codex
Type: Backend / Multi-Device Runtime

Title:
Validate Multi-Device Redroid Isolation

Dependencies:
- TIK-014
- TIK-015
- TIK-016

Scope:
- backend/
- scripts/
- docs/

Phases:
1. Multi-device provisioning design
2. Device 02 provisioning
3. Lifecycle and screen isolation
4. Storage, media, and network isolation
5. Manager lifecycle with multiple devices
6. Final verification

Acceptance criteria:
- Two Redroid containers can coexist and run independently.
- Each device has a unique Docker container name.
- Each device has a unique ADB endpoint.
- Each device has its own persistent /data directory.
- Starting, stopping, or restarting one device does not affect the other.
- Screen sessions are independent.
- Device storage and media do not cross between devices.
- Device network configuration can be isolated independently.
- Manager startup reconciles both devices correctly.
- Manager shutdown safely stops all managed Redroid devices.
- No persistent device data is deleted.
- Existing single-device behavior remains unchanged.
- Full backend tests pass.

---

## TIK-018
Status: DONE
Owner: Codex + Antigravity
Type: Backend / Device Provisioning

Title:
Automate Managed Redroid Device Provisioning

Dependencies:
- TIK-014
- TIK-016
- TIK-017

Scope:
- backend/
- frontend/
- deploy/
- docs/

Phases:
1. Provisioning architecture and allocation design
2. Backend provisioning service
3. Provisioning API and rollback safety
4. Real Device 03 provisioning test
5. Frontend Create Device flow
6. Delete / deprovision flow
7. Final verification

Acceptance criteria:
- TikTok Manager can create a new managed Redroid device without manual docker commands.
- Container name, ADB port, data path, and network are allocated uniquely.
- Provisioning validates conflicts before creating resources.
- Device and Runtime database records are created consistently.
- Failed provisioning rolls back partial resources safely.
- Persistent data is never deleted without explicit destructive confirmation.
- Provisioned devices use loopback-only ADB.
- Each device gets isolated persistent storage and network configuration.
- Existing Device 01 and Device 02 remain unchanged.
- Frontend can create a managed Redroid device.
- Full backend tests, frontend lint, and frontend build pass.

---

## TIK-019
Status: DONE
Owner: Codex + Antigravity
Type: Backend / Device Networking

Title:
Add Per-Device Network Configuration

Dependencies:
- TIK-014
- TIK-017
- TIK-018

Scope:
- backend/
- frontend/
- docs/

Phases:
1. Network architecture and configuration design
2. Backend network configuration model/service
3. Network API and runtime application
4. Real multi-device network isolation test
5. Frontend network management UI
6. Recovery, health checks, and persistence
7. Final verification

Acceptance criteria:
- Each managed Redroid device can have independent network configuration.
- Network configuration is stored durably and mapped to the correct Runtime.
- Proxy configuration can be applied, inspected, cleared, and verified independently per device.
- Changing Device A network configuration does not affect Device B.
- Secrets are not stored in plaintext logs or exposed unnecessarily through APIs/UI.
- Network configuration survives manager restarts where appropriate.
- Runtime start/restart can safely restore the intended network configuration.
- Failure to apply network settings produces clear recoverable state.
- Existing lifecycle, provisioning, screen, and deprovision flows remain unchanged.
- Full backend tests, frontend lint, TypeScript, and production build pass.

---

## TIK-020
Status: DONE
Owner: Codex + Antigravity
Type: Backend / Worker / Device Automation

Title:
Add Device Automation Execution Layer

Dependencies:
- TIK-011
- TIK-012
- TIK-013
- TIK-014
- TIK-019

Scope:
- backend/
- workers/
- frontend/
- docs/

Phases:
1. Device automation architecture
2. Backend automation primitives
3. Job execution integration
4. Real Redroid execution validation
5. Frontend job creation and monitoring
6. Failure, retry, cancellation, and recovery
7. Final verification

Acceptance criteria:
- Jobs can target an exact Runtime.
- Worker can execute safe Android automation primitives through the Runtime ADB serial.
- Runtime readiness is checked before execution.
- Network readiness is respected when a job requires network access.
- Jobs cannot accidentally control another Runtime.
- Media/file transfer and screenshot primitives work on real Redroid.
- Android package launch/stop/state operations work.
- Job logs record structured execution steps.
- Timeout, retry, cancellation, and failure states are handled safely.
- Device lifecycle state is not corrupted by automation failures.
- Existing provisioning, screen, networking, and lifecycle flows remain unaffected.
- Backend tests, frontend build, and live disposable-device verification pass.

---

## TIK-021
Status: DONE
Owner: Codex + Antigravity
Type: Backend / Content Pipeline / Frontend

Title:
Add Media and Content Pipeline

Dependencies:
- TIK-018
- TIK-020

Scope:
- backend/
- workers/
- frontend/
- docs/

Phases:
1. Content pipeline architecture
2. Content asset backend foundation
3. Media processing and preparation
4. Device delivery integration
5. Content library frontend
6. End-to-end workflow and retention
7. Final verification

Acceptance criteria:
- Media assets can be uploaded and stored durably.
- Assets have validated metadata, hashes, MIME type, dimensions/duration where applicable.
- Duplicate content is detected safely.
- Content can be organized independently from Jobs.
- Jobs can reference Content Assets without arbitrary host paths.
- Content can be prepared and delivered to an exact Runtime.
- Device delivery uses the existing TIK-020 automation layer.
- Imported media can be verified on a disposable Redroid device.
- Content usage/history is tracked.
- Artifact and content retention responsibilities are clearly separated.
- Existing Jobs, device automation, networking, provisioning, and lifecycle remain unaffected.
- Backend tests, frontend build, and live disposable-device verification pass.

---

## TIK-022
Status: DONE
Owner: Codex + Antigravity
Type: Backend / Worker / Workflow / Frontend

Title:
Add Workflow Execution Orchestration

Dependencies:
- TIK-020
- TIK-021

Scope:
- backend/
- workers/
- frontend/
- docs/

Phases:
1. Workflow architecture
2. Workflow backend foundation
3. Workflow execution engine
4. Runtime/content integration
5. Workflow frontend
6. Recovery, cancellation, and production validation
7. Final verification

Acceptance criteria:
- Multi-step workflows can be defined and executed.
- Workflow steps execute in deterministic dependency order.
- Existing Jobs remain the unit of execution.
- Workflow execution does not bypass Job claim/lease/retry/cancellation rules.
- Steps can target exact Runtime, Account, and ContentAsset/version where required.
- Failed steps do not silently advance the workflow.
- Retry can occur at step level without replaying completed steps.
- Workflow state survives backend and worker restarts.
- Workflows can pause for manual approval and resume safely.
- Cancellation propagates safely to active/pending workflow steps.
- Workflow history and step-level audit trail are durable.
- Existing device automation and content pipelines remain unaffected.
- Frontend can create, monitor, pause/resume, cancel, and inspect workflows.
- Backend, worker, frontend build, and live disposable-runtime verification pass.

---

## TIK-023
Status: IN PROGRESS
Owner: Codex + Antigravity
Type: Backend / Provisioning / Publishing Foundation / Frontend

Title:
Add Publishing Foundation and Managed App Installation

Dependencies:
- TIK-018
- TIK-020
- TIK-021
- TIK-022

Scope:
- backend/
- workers/
- frontend/
- docs/

Phases:
1. Publishing and managed-app architecture
2. Managed app package backend foundation
3. Runtime app installation and provisioning integration
4. Publishing workflow backend integration
5. Publishing and app-management frontend
6. Live device validation and production hardening
7. Final verification

Acceptance criteria:
- Required Android apps can be managed as versioned packages.
- APK files are stored and validated as managed content, never arbitrary host paths.
- A newly provisioned Redroid Runtime can automatically install configured required apps.
- App installation targets the exact Runtime only.
- Installed package/version is verified after installation.
- Provisioning reports app-install state separately from core Runtime readiness.
- Failed app installation does not corrupt Runtime lifecycle state.
- Publishing workflows can bind exact Account, Runtime, and ContentAssetVersion.
- Publishing workflows verify required app availability before continuing.
- Publishing foundation can deliver media and launch/verify the target app.
- Manual approval is available before future publish actions.
- Existing provisioning, networking, automation, content, and workflow behavior remains intact.
- Backend, worker, frontend, and disposable-device validation pass.