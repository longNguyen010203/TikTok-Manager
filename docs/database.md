# Database

## Development database
SQLite, configured by default as `sqlite:///./tiktok_manager.db` relative to the
backend process working directory. Set `DATABASE_URL` to override the connection
URL.

## Operational host database

Real host operations must not use the relative development URL because each Git
worktree resolves it to a different SQLite file. The verified local host runtime
uses this explicit database outside every worktree:

```text
sqlite:////home/longnguyen/.local/share/tiktok-manager/tiktok_manager.db
```

Set that exact `DATABASE_URL` before starting the backend for real Docker/device
operations. The database and its backups are operational state and must never be
committed to Git. The pre-Device-03 backup is stored under
`/home/longnguyen/.local/share/tiktok-manager/backups/`.

Database schema changes are managed by Alembic. Application import does not
create database files or tables automatically. `app.database.init_db()` remains
available for isolated tests, while local and deployed databases should use the
migration workflow below.

## Migration workflow

Run migration commands from the `backend/` directory. Alembic uses
`sqlite:///./tiktok_manager.db` by default and honors the same `DATABASE_URL`
environment variable as the application.

Install the backend and apply every pending migration:

```powershell
python -m pip install -e ".[test]"
alembic upgrade head
```

Inspect the database's current revision and the available migration history:

```powershell
alembic current
alembic history
```

After changing SQLAlchemy models, generate a candidate migration and review the
generated operations before applying it:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Revert the most recently applied revision when needed:

```powershell
alembic downgrade -1
```

To migrate another database, set its URL for the current PowerShell session:

```powershell
$env:DATABASE_URL = "sqlite:///./another.db"
alembic upgrade head
```

## Planned production database
PostgreSQL

## Account

Fields:

- id: integer primary key
- name: string (maximum 255 characters, required)
- username: string (maximum 255 characters, required)
- platform: string (maximum 50 characters, required)
- status: string (maximum 50 characters, required)
- notes: nullable text
- runtime_id: nullable foreign key to `runtimes.id`; deleting the referenced
  runtime sets this field to null
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

The SQL table name is `accounts`. Platform and status remain strings so their
allowed values can be defined alongside API validation in a later task.

## Device

The SQL table name is `devices`.

Fields:

- id: integer primary key
- name: string (maximum 255 characters, required)
- device_type: string (maximum 50 characters, required)
- platform: string (maximum 50 characters, required)
- os_version: string (maximum 100 characters, required)
- status: string (maximum 50 characters, required)
- notes: nullable text
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

## Runtime

The SQL table name is `runtimes`.

Fields:

- id: integer primary key
- device_id: required foreign key to `devices.id`
- name: string (maximum 255 characters, required)
- runtime_type: string (maximum 50 characters, required); use `redroid` for a
  Redroid-backed runtime
- docker_container_name: nullable, unique string (maximum 255 characters); local
  Docker container identifier used by the Redroid runtime adapter
- adb_serial: nullable, unique string (maximum 255 characters); ADB target
  serial, such as `localhost:5555`
- status: string (maximum 50 characters, required)
- last_seen_at: nullable UTC datetime
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

Multiple null values are allowed for both Redroid identifiers so non-Redroid
and not-yet-configured Runtime records remain backward-compatible.

## RuntimeNetworkConfig

The SQL table name is `runtime_network_configs`. It contains at most one
current desired network configuration for each Runtime. Deleting the Runtime
cascades to this row. An absent row means that TikTok Manager has never managed
network configuration for that Runtime; legacy Runtime rows are not backfilled.

Fields include `mode`, nullable proxy host and port, nullable username and
password secret references, nullable host/device bridge ports, a positive
`desired_revision`, and timestamps. Modes are `direct` and `http_proxy`.
`direct` requires every proxy and bridge field to be null. `http_proxy`
requires proxy host/port and both bridge ports. Proxy and bridge ports are
limited to 1-65535. `runtime_id` and non-null `bridge_host_port` values are
unique.

Only allowlisted secret references are stored. Resolved proxy usernames and
passwords are never stored in these tables.

## RuntimeNetworkConfigRevision

The SQL table name is `runtime_network_config_revisions`. Each row is an
immutable application-level snapshot of the desired fields at one positive
revision. `(runtime_id, revision)` is unique, and Runtime deletion cascades to
its revision history. The same mode and port constraints as the current config
apply to every snapshot.

## RuntimeNetworkState

The SQL table name is `runtime_network_states`. `runtime_id` is both its primary
key and a cascading foreign key to `runtimes.id`, giving each managed Runtime
at most one observed-state row.

Statuses are `disabled`, `pending`, `applying`, `ready`, `degraded`, and
`failed`. The row records desired and nullable applied revisions, observed
mode and Android proxy endpoint, reverse-rule presence, bridge state and
ownership/process metadata, apply/verify/probe timestamps, and sanitized error
details. Observed modes are `unknown`, `direct`, and `http_proxy`; bridge states
are `unknown`, `stopped`, `starting`, `running`, and `unhealthy`.

Migration `20261003_0009` creates all three tables. It creates no default rows
and therefore does not adopt or alter legacy devices.

When a stopped Runtime changes from HTTP proxy to direct mode, its current
config has no bridge port, but prior HTTP revision ports remain reserved while
observed state retains a bridge owner token. Successful cleanup clears the
token and makes the historical port eligible for later allocation.

## RedroidProvisioning

The SQL table name is `redroid_provisionings`. It is a durable allocation and
recovery manifest for Redroid resources created by TikTok Manager. Legacy
Redroid Runtime rows are not implicitly owned by this table.

The record stores a unique idempotency key, request fingerprint, ownership
token, installation ID, provisioning state, device number, container name and
ID, ADB host port and serial, persistent data path, network name and ID,
immutable image reference, nullable resulting Device/Runtime IDs, explicit
resource-created flags, immutable historical Device/Runtime IDs after
deprovisioning, container/network removal flags, a data-preserved flag, nullable
error details, and timestamps.

Device number, container name, ADB port, ADB serial, data path, network name,
ownership token, idempotency key, Device ID, and Runtime ID are unique. Device
and Runtime references use `ON DELETE SET NULL` so provisioning history remains
available if application records are removed.

Provisioning states are `requested`, `preflighting`, `reserved`,
`data_created`, `network_created`, `container_created`, `inspected`,
`completed`, `rolling_back`, `rolled_back`, `failed`, `rollback_failed`, and
`inconsistent`. Managed removal adds `deprovisioning`, `deprovisioned`, and
`deprovision_failed`. A deprovisioned record is retained as a tombstone, and its
unique `device_number` reservation is never released.

## Job

The SQL table name is `jobs`. A job is a durable unit of work and may target an
Account, a Runtime, both, or neither.

Fields:

- id: integer primary key
- job_type: string (maximum 100 characters, required)
- status: string (maximum 50 characters, required, defaults to `pending`)
- account_id: nullable foreign key to `accounts.id`; deleting the referenced
  account sets this field to null
- runtime_id: nullable foreign key to `runtimes.id`; deleting the referenced
  runtime sets this field to null
- payload: nullable JSON request data
- result: nullable JSON result data
- error_message: nullable text
- attempt_count: non-negative integer, defaults to 0
- max_attempts: positive integer, defaults to 3
- scheduled_at: nullable UTC datetime
- started_at: nullable UTC datetime
- completed_at: nullable UTC datetime
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

Allowed initial job statuses are `pending`, `running`, `succeeded`, `failed`,
`retrying`, and `cancelled`. A database check constraint rejects other values.

## JobLog

The SQL table name is `job_logs`. Job logs are append-only records used to
preserve lifecycle and failure history independently of the Job's current
state.

Fields:

- id: integer primary key
- job_id: required foreign key to `jobs.id`
- level: string (maximum 20 characters, required)
- message: required text
- metadata: nullable JSON containing event-specific details
- created_at: UTC datetime, set when the row is created

## Relationships

- One Device has zero or more Runtime records. Deleting a Device cascades to its
  Runtime records.
- One Runtime belongs to exactly one Device.
- One Runtime has zero or one current RuntimeNetworkConfig, zero or one
  RuntimeNetworkState, and zero or more RuntimeNetworkConfigRevision rows.
  Deleting the Runtime cascades to all of these network rows.
- Although the general schema permits several Runtime records per Device, a
  managed Redroid Device must have exactly one Runtime. Device lifecycle and
  screen operations reject zero or multiple Runtime assignments.
- One Runtime may have zero or more Account records assigned to it.
- One Account may reference one Runtime through nullable `runtime_id`. Deleting
  that Runtime preserves the Account and sets `runtime_id` to null.
- One Account may be targeted by zero or more Jobs. Deleting the Account
  preserves its Jobs and sets their `account_id` to null.
- One Runtime may be targeted by zero or more Jobs. Deleting the Runtime
  preserves its Jobs and sets their `runtime_id` to null.
- One Job has zero or more JobLog records. Deleting the Job cascades to all of
  its logs.
