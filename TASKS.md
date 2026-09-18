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