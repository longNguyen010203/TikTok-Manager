# Database

## Authoritative operational database

The normal local runtime always resolves its SQLite database from the durable
application configuration. Its canonical path is:

```text
sqlite:////home/longnguyen/.local/share/tiktok-manager/tiktok_manager.db
```

Normal users do not set `DATABASE_URL`. The installer creates
`~/.config/tiktok-manager/config.toml`, and production startup rejects a
worktree-local SQLite path. The database and its backups are operational state
and must never be committed to Git. Startup fails instead of creating a second
empty database when the configured operational database is absent, corrupt, or
at an incompatible Alembic revision.

Files such as `backend/tiktok_manager.db` are development artifacts. Tests use
temporary databases. Developers may explicitly set `DATABASE_URL` for an
isolated development/test process; an explicit override is never required by
the installed application service.

Database schema changes are managed by Alembic. Application import does not
create database files or tables automatically. `app.database.init_db()` remains
available for isolated tests, while local and deployed databases should use the
migration workflow below.

## Migration workflow

Run migration commands from the `backend/` directory. Without an explicit
development override, Alembic resolves the same canonical application database
as the backend. The installer backs up and checks an existing database before
running `alembic upgrade head`.

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

`credential_source` distinguishes `none`, legacy `environment_reference`, and
`stored_encrypted`. Secret values and ciphertext are not stored in this table.

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

## RuntimeNetworkCredential

The `runtime_network_credentials` table contains at most one authenticated-
encryption payload per Runtime. Username and password are encrypted separately
with Fernet (`fernet-v1`), and Runtime deletion cascades to the credential row.
The master key is never stored in SQLite; it lives at
`~/.config/tiktok-manager/credentials.key` with mode `0600`.

Migration `20261004_0010` adds encrypted credential storage and marks existing
allowlisted environment-reference configurations as
`environment_reference`. It does not resolve or expose historical secrets.

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
- error_code: nullable stable safe failure code
- error_retryable: nullable retry classification
- attempt_count: non-negative integer, defaults to 0
- max_attempts: positive integer, defaults to 3
- scheduled_at: nullable UTC datetime
- started_at: nullable UTC datetime
- completed_at: nullable UTC datetime
- claim_token_hash: nullable SHA-256 digest of the transient worker token
- claimed_by, claimed_at, heartbeat_at, lease_expires_at: nullable durable
  lease ownership fields
- cancellation_requested_at: nullable cooperative cancellation time
- execution_started_at, execution_stage: nullable recovery classification
  state
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

Allowed job statuses are `pending`, `running`, `cancelling`, `succeeded`,
`failed`, `retrying`, and `cancelled`. A database check constraint rejects
other values. Migration `20261004_0012` adds claims, leases, cancellation, and
typed failure fields. Raw claim tokens are never persisted.

## JobLog

The SQL table name is `job_logs`. Job logs are append-only records used to
preserve lifecycle and failure history independently of the Job's current
state.

Fields:

- id: integer primary key
- job_id: required foreign key to `jobs.id`
- level: string (maximum 20 characters, required)
- event_type: nullable indexed structured event type
- message: required text
- metadata: nullable JSON containing event-specific details
- created_at: UTC datetime, set when the row is created

Structured metadata never includes claim tokens, credentials, raw ADB output,
arbitrary paths, or artifact bytes.

## JobArtifact

The SQL table name is `job_artifacts`. Migration `20261004_0011` adds durable
metadata for screenshots, managed uploads, and files pulled through the safe
Android automation service. Artifact bytes are not stored in SQLite.

Fields:

- id: integer primary key
- job_id: nullable foreign key to `jobs.id`; deleting a Job cascades to its
  artifact metadata
- kind: bounded artifact category such as `screenshot` or `device_file`
- original_filename: normalized display filename, never a host path
- storage_key: unique generated internal key
- mime_type: validated media/content type
- size_bytes: non-negative stored size
- sha256: hexadecimal SHA-256 digest
- created_at: UTC creation timestamp
- expires_at: optional retention deadline
- cleanup_status: `active`, `expired`, `deleted`, or `failed`

Files live under the configured private artifact root, which defaults to
`~/.local/share/tiktok-manager/artifacts/`. The directory is mode `0700` and
artifact files are mode `0600`. Storage keys are generated by the backend;
neither callers nor API results supply or expose raw host filesystem paths.
Migration `20261004_0013` adds the explicit `expired` state. Cleanup preserves
the metadata row and Job relationship after deleting bytes, so historical Job
results remain inspectable. Historical Jobs and JobLogs are not automatically
deleted. Active queued, retrying, running, or cancelling Jobs protect their
artifacts from cleanup.

Uploads default to seven-day retention; screenshots and pulled results default
to thirty days. A one-GiB total active-byte quota may evict the oldest eligible
completed/unattached artifacts sooner. If protected artifacts consume the
quota, new storage fails safely with `ARTIFACT_STORAGE_FULL`.

## Content library

Migration `20261004_0014` adds reusable content independently from
`job_artifacts`. It does not migrate, copy, or change historical JobArtifacts.

`content_blobs` describes immutable physical files. `storage_key` is a
generated 32-character hexadecimal identifier and is never accepted from or
returned to an API caller. `sha256` is a unique lowercase 64-character digest;
identical bytes reuse one blob even when several logical assets have different
names, notes, or tags. Positive size, bounded detected MIME type, status, and
verification timestamps support quota and reconciliation. Blob status is
`active`, `orphaned`, `missing`, or `deleted`.

`content_assets` is the long-lived logical library object. It stores type,
display name, notes, source, lifecycle status, an application-validated
nullable current-version pointer, and archive/delete timestamps. Status is
`processing`, `ready`, `invalid`, `archived`, or `deleted`. Bytes are never
updated in place.

`content_asset_versions` stores immutable version membership, the blob foreign
key, original safe filename, detected MIME/canonical extension, processing
state, future media metadata fields, bounded metadata JSON, and safe processing
errors. `(content_asset_id, version_number)` is unique. Migration
`20261004_0015` adds a unique nullable `inspection_job_id` foreign key to the
current internal Job and expands the event constraint for processing history.
Admission creates a version as `processing`; successful authoritative
inspection changes it to `ready` and atomically selects an appropriate current
version. Deterministic invalid media becomes `invalid`. `content_variants` reserves the
same blob-backed model for thumbnails or prepared derivatives but Phase 2 does
not generate them.

`content_asset_tags` stores normalized lowercase tags with a composite unique
key. `content_events` is append-only business history for uploaded, queued,
processing-started, ready, invalid, metadata-updated, archived, restored,
deleted, and version-added events.
`content_deliveries` pins an immutable ready version and Runtime snapshot to an
internal delivery Job. Revision `20261004_0016` adds MediaStore intent,
started/completed timestamps, scoped nullable idempotency, required safe remote
identifiers, and delivery history events. States are `pending`, `delivering`,
`succeeded`, `failed`, and `cancelled`. Runtime deletion clears `runtime_id` but
preserves `runtime_id_snapshot`; deliveries never retarget to a newer version or
different Runtime.

Physical files live under `~/.local/share/tiktok-manager/content/blobs/` with a
private staging directory and cross-process maintenance lock. Directories are
mode `0700`, files are mode `0600`, and generated storage identities, canonical
containment, no-follow opens, streamed hashing, fsync, and atomic rename protect
the storage boundary. The default quota is 500 MiB per upload and 20 GiB of
unique active/orphaned physical blob bytes. Ready content is not automatically
evicted. Reconciliation deletes only proven-owned abandoned generated staging
files, marks proven missing DB blobs, marks unreferenced rows orphaned, and
reports uncertain filesystem entries without deleting them.

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
- One Job has zero or more JobArtifact records. A pre-ingested artifact may
  temporarily have no Job association. Deleting an associated Job cascades to
  its artifact metadata; file cleanup is handled by the artifact service.
- One ContentAsset has one or more immutable ContentAssetVersion rows and zero
  or more normalized tags, events, variants, and delivery records. Multiple
  asset versions or assets may reference one deduplicated ContentBlob. Blob
  deletion is restricted while referenced; asset deletion is soft in Phase 2.
