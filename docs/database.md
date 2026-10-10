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
- name: required synchronized compatibility alias for `display_name`
- display_name: nullable only for migration compatibility; all API-created rows set it
- username, email, phone: nullable identity/contact fields
- platform: required compatibility field (new API writes default to `tiktok`)
- status: server-validated lifecycle status
- registration_state: `unknown`, `pending`, `registered`, or `failed`
- registration_completed_at: nullable UTC timestamp of the latest successful
  manual completion; cleared when registration fails or is reopened
- health_status: `unknown`, `healthy`, `warning`, or `unhealthy`
- status_reason, niche: nullable bounded business metadata
- notes: nullable text
- archived_at: nullable soft-archive timestamp
- follower_count, following_count, likes_count, video_count: nullable,
  non-negative metric snapshots
- metrics_updated_at: nullable metric observation timestamp
- runtime_id: nullable foreign key to `runtimes.id`; deleting the referenced
  runtime sets this field to null
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

`account_tags` stores normalized, unique `(account_id, tag)` values and cascades
on Account deletion. `account_secrets` stores one Fernet ciphertext per
allowlisted `(account_id, secret_type)`, using `fernet-v1`. The application key
is outside SQLite at the configured mode-`0600` credential-key path. Secret
plaintext is request-memory-only and has no read API. Startup validates that
the configured key can decrypt existing account-secret rows.

Migration `20261007_0035` extends the existing canonical table rather than
creating a parallel registry. It makes handles nullable, backfills
`display_name = name`, defaults existing registration state to `unknown`, and
preserves all Account IDs and Runtime/Job/Workflow/Publishing references.
Migration `20261010_0048` adds nullable `registration_completed_at` without
backfilling or changing existing registration state. `registration_ready` is
derived at serialization time and therefore is not a database column.

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
version. Deterministic invalid media becomes `invalid`. `content_variants`
stores generated derivatives. Revision `20261005_0017` adds the version's
nullable unique `thumbnail_job_id` and thumbnail events. The initial thumbnail
variant pins its source version, profile fingerprint, deduplicated ContentBlob,
processing state, safe metadata, and safe error.

`content_asset_tags` stores normalized lowercase tags with a composite unique
key. `content_events` is append-only business history for uploaded, queued,
processing-started, ready, invalid, metadata-updated, archived, restored,
deleted, version-added, thumbnail-queued/ready/failed, and delivery events.
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
reports uncertain filesystem entries without deleting them. Daily cleanup
physically removes only proven-unreferenced orphan blobs after a grace period.
Soft-deleted, archived, current, and historical versions remain references and
retain their bytes.

## Relationships

## Workflow orchestration

Migration `20261005_0018` adds `workflows`, `workflow_steps`,
`workflow_step_job_runs`, and `workflow_events`. A Workflow pins its template
version, explicit Runtime snapshot, and exact ready content version. Its
parameters are the validated server-template parameters, not an executable Job
payload. Nullable live foreign keys preserve snapshots/history when applicable.

WorkflowStep rows are immutable template materialization ordered by a unique
`(workflow_id, step_index)` and `step_key`. V1 is sequential: each row may point
to its immediately preceding dependency. At most one step can reference a Job,
and `workflow_step_job_runs` provides a unique durable mapping between one
logical step attempt and one Job. Job worker retries remain on that Job;
WorkflowStep attempts are a separate operator-level concept.

WorkflowEvent is append-only bounded business history. It stores safe IDs,
statuses, and error codes only—never Job payloads, claim tokens, commands,
filesystem paths, credentials, or subprocess output.

Migration `20261005_0019` expands that bounded event vocabulary with
`waiting`. A wait step uses the existing durable `resume_at` and
`waiting_reason` columns; no timer table or in-memory timer state is added. The
deadline is written once when the step enters waiting and is not recalculated
during recovery.

## Managed Android packages

Migration `20261005_0020` adds a `purpose` discriminator to ContentAsset.
Existing rows are `library`; internal APK assets are
`managed_app_package`. Package assets reuse the same immutable ContentBlob and
ContentAssetVersion storage but are excluded from the ordinary content list,
workflow content binding, and `content.deliver`.

`managed_apps` stores the unique operator-owned app key, immutable expected
Android package, display name, active/disabled/archived status, required/
optional/disabled installation policy, and nullable explicitly activated
version pointer. The current-version foreign key protects history; application
validation additionally requires that it belong to the same app and be ready.

`managed_app_versions` pins one package-purpose ContentAssetVersion and digest.
Its lifecycle is `uploaded`, `inspecting`, `ready`, `invalid`, or `retired`.
Only normalized version/package/SDK/signer metadata and safe errors are stored.
`(managed_app_id, sha256)` and the content-version and inspection-Job pointers
are unique. `managed_app_events` is bounded append-only history; it contains
safe IDs, state, and error codes rather than tool output or host paths.

Migration `20261006_0022` adds explicit `inspection_level` and
`basic_approved_at`. Existing successfully inspected ready/retired versions are
backfilled as `verified`; new uploads remain `basic` until tool verification or
explicit operator basic approval. Approval records an append-only event and
never fabricates discovered package, version, or signer fields.

Migration `20261005_0021` adds `runtime_app_installations` and
`runtime_app_installation_runs`. One nullable-live `(runtime_id,
managed_app_id)` row stores an exact desired version and normalized observed
package/version/signer state. Its immutable `runtime_id_snapshot` survives
deprovisioning; the live Runtime FK becomes null and status becomes `removed`.
Status is independent from Runtime lifecycle: `pending`, `installing`,
`installed`, `failed`, `outdated`, or `removed`.

Each server-created `app.install` or `app.verify` Job has one immutable run row
pinning the desired version used by that attempt. The nullable latest-Job
pointer supports convergence and crash recovery while run history is retained.

Migration `20261006_0023` adds nullable pinned ManagedApp and
ManagedAppVersion foreign keys to Workflow and creates `publishing_sessions`.
One PublishingSession belongs to exactly one Workflow and preserves immutable
Account/Runtime snapshots plus exact content/app version bindings. Its status
is a domain projection; Workflow and linked Jobs remain execution truth.

Application SQLite connections enable `PRAGMA foreign_keys=ON` whenever a
connection is opened. Managed Runtime deprovision also clears nullable live
Workflow and ContentDelivery Runtime pointers in its authoritative database
transaction, while immutable Runtime snapshots preserve historical identity.

Migration `20261006_0024` adds `tiktok_ui_profiles`. Rows contain immutable,
normalized profile identity, exact Android package/version compatibility,
repository resource key, fingerprint, locale assumption, and
testing/active/retired status. Selector and screen definitions remain
versioned repository resources; no client CRUD or executable definitions are
stored in SQLite. The seeded `com.ss.android.ugc.trill` 44.4.3 profile is in
testing state and intentionally has no fabricated selectors pending live
calibration.

Migration `20261006_0025` appends testing profile version 2 for the observed
TikTok 44.4.3 HOME hierarchy. Version 1 is not modified, so existing Jobs stay
pinned to its original resource and fingerprint. New Jobs select and persist
the highest compatible non-retired profile ID.

Migration `20261006_0026` appends testing profile version 3 for the observed
TikTok 44.4.3 CAMERA_CREATE hierarchy and its exact semantic gallery-entry
control. Earlier profile generations remain immutable, and Jobs continue to
pin one profile ID before execution.

Migration `20261006_0027` appends testing profile version 4 for the observed
TikTok 44.4.3 MEDIA_PICKER hierarchy. Its fingerprint pins the picker root,
header, category strip, ViewPager, and media GridView definitions while
preserving profile v3 for historical Jobs.

Migration `20261007_0028` appends testing profile version 5 for the observed
TikTok 44.4.3 post-selection `EDIT_MEDIA` hierarchy. The immutable row pins the
repository definition and fingerprint; stable scene, bottom-action, Next, and
tool-list structure is calibrated while dynamic preview nodes remain excluded.
Earlier Jobs retain their exact previously pinned profile generation.

Migration `20261007_0036` appends testing profile version 12 for the observed
fresh-install `TERMS_CONSENT` hierarchy on Runtime 18. The profile recognizes
the terms scene, content, title, and consent control from exact resource IDs;
the consent control remains non-actionable. Profiles v1-v11 remain immutable.

Migration `20261007_0037` appends testing profile version 13 for Runtime 18's
observed post-terms `ONBOARDING_INTERESTS` screen. It pins exact scene, grid,
title, action-region, Skip, and reinforcing interest-tile definitions. Skip
remains non-actionable and profile v12 remains available to pinned Jobs.

Migration `20261007_0038` appends testing profile version 14. It preserves the
v13 screen definition and authorizes only the exact observed Skip control for
the typed `tiktok.skip_interests` transition. Interest tiles and Next remain
non-actionable; older profile generations remain immutable for pinned Jobs.

Migration `20261007_0039` appends testing profile version 15 and authorizes
only the exact observed HOME Profile tab for `tiktok.open_profile`.

Migration `20261007_0040` appends testing profile version 16 for Runtime 17's
logged-in PROFILE hierarchy. Stable scene/content/header/menu signals classify
PROFILE independently from HOME; display name, handle, and metrics remain
reinforcing or dynamic rather than immutable identity data.

Migration `20261007_0041` appends testing profile version 17 for Runtime 18's
observed logged-out `SIGNUP_METHOD` hierarchy. Stable scene/content/phone
containers, title, phone input, and email-method signals classify the state;
Continue, Log in, and Close remain non-actionable reinforcing observations.
The profile retains v15's exact Profile-tab selector, so one typed action may
truthfully converge to either PROFILE or SIGNUP_METHOD without changing older
pinned profile generations.

Migration `20261007_0042` appends testing profile version 18 and authorizes
only the observed `Continue with Email` semantic child for the typed,
one-attempt email-method transition. Phone, generic Continue, Log in, Close,
and Report controls remain non-actionable.

Migration `20261007_0043` preserves the first immutable EMAIL_ENTRY
calibration. Its initial live check exposed that UIAutomator reports the empty
email label as node text rather than content-description. Migration
`20261007_0044` therefore appends corrected testing profile version 20 instead
of rewriting v19. Version 20 classifies EMAIL_ENTRY using exact root, scene,
header, title, form, and email-input signals.

Migration `20261007_0045` appends testing profile version 21. It authorizes the
single observed email EditText by calibrated class/ancestor structure so the
screen remains resolvable after its dynamic text changes. No schema or Account
data changes are made; Account email remains canonical source data while
registration Jobs store only Account/Runtime/profile identifiers.

Migration `20261007_0046` appends testing profile version 22 and authorizes
only the observed `email_continue` button for the typed, one-attempt Continue
boundary. Migration `20261007_0047` appends testing profile version 23 for the
observed email-link/code checkpoint. The classifier uses stable container,
title, message-node, code-container, and Resend identities; dynamic text that
contains the Account email is neither stored in the profile nor exposed by
the action result. Both migrations add profile metadata only.

Migration `20261007_0029` appends testing profile version 6. It preserves v5
and changes only the observed editor Next selector to action-authorized for the
one-attempt `tiktok.open_caption` boundary.

Migration `20261007_0030` appends testing profile version 7 for the observed
92-node `READY_TO_PUBLISH` screen. The immutable definition pins caption,
options, bottom-action, Drafts, and Post signals; final submission controls are
observational and non-actionable.

Migration `20261007_0031` appends testing profile version 8. It preserves v7
and authorizes only the observed `caption_input` EditText for the typed
one-attempt caption action; Drafts and Post remain non-actionable.

Migration `20261007_0032` appends testing profile version 9. It preserves v8
and authorizes only the observed READY_TO_PUBLISH privacy entry for a
one-attempt calibration boundary.

Migration `20261007_0033` appends testing profile version 10. It preserves v9
and records the observed POST_SETTINGS privacy bottom sheet, including only
the exact Everyone and Only you choice mappings as actionable. The dynamic
Friends choice remains intentionally unsupported, and Drafts/Post remain
non-actionable.

Migration `20261007_0034` appends testing profile version 11. It preserves v10
and records the observed privacy-sheet auto-close behavior plus the exact
READY_TO_PUBLISH summaries for Everyone and Only you. These summaries are
verification signals only; Drafts/Post remain non-actionable.

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
- One ManagedApp owns zero or more immutable ManagedAppVersion rows and one
  optional active ready-version pointer. Each ManagedAppVersion references one
  package-purpose ContentAssetVersion, so that reference protects its blob from
  orphan cleanup.
- One live Runtime has at most one RuntimeAppInstallation per ManagedApp. One
  installation has zero or more immutable RuntimeAppInstallationRun rows.
