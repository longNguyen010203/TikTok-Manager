# API Contract

## Device automation Jobs

TIK-020 Phase 3 connects allowlisted `device.*` Jobs to backend-only Android
automation primitives. Workers use a claim-token-protected execution endpoint
and never execute ADB. Public types are `device.screenshot`,
`device.package_state`, `device.launch_app`, `device.stop_app`,
`device.push_file`, `device.pull_file`, and `device.import_media`. Input-control
and arbitrary shell Jobs are not exposed.

Every primitive resolves `runtime_id` from the database immediately before
execution and uses only that Runtime's stored ADB serial. Automation callers
cannot provide an ADB serial, Docker container, arbitrary host path, arbitrary
Android destination, raw ADB command, or shell fragment.

Automation failures contain a stable `code`, `retryable` value, and
`safe_message`. Raw ADB stdout/stderr is never included in an API-facing error.
The stable codes are `RUNTIME_NOT_FOUND`, `RUNTIME_STOPPED`,
`RUNTIME_DEPROVISIONING`, `RUNTIME_BUSY`, `RUNTIME_SCREEN_ACTIVE`,
`DEVICE_NOT_READY`, `ADB_UNAVAILABLE`, `ADB_COMMAND_FAILED`,
`AUTOMATION_TIMEOUT`, `PACKAGE_NOT_FOUND`, `INVALID_AUTOMATION_PAYLOAD`,
`FILE_TRANSFER_FAILED`, `MEDIA_IMPORT_FAILED`, `ARTIFACT_NOT_FOUND`,
`ARTIFACT_POLICY_VIOLATION`, and `AUTOMATION_CANCELLED`.

Screenshots and pulled files become `JobArtifact` records. Service results may
contain an artifact ID, safe display filename, MIME type, size, and SHA-256,
but never file bytes or a host storage path.

## Runtime network configuration

`GET /runtimes/{id}/network` returns safe desired and observed state. An
unmanaged Runtime is represented as `managed=false`, `mode=direct`, revision
zero, and disabled status. Responses expose only username/password configured
booleans; secret values, secret references, bridge ownership tokens, and raw
process metadata are never returned.

`PUT /runtimes/{id}/network` stores desired state only. Its body contains
`mode`, `expected_revision`, and, for `http_proxy`, `proxy_host`, `proxy_port`,
and optional plaintext `username` and `password` write-only fields. Supplying
both replaces the encrypted stored credentials. Omitting both retains existing
credentials. `credential_action="clear"` removes authentication, while
`credential_action="replace"` requires both fields; empty strings are invalid.
Legacy allowlisted environment references remain accepted temporarily but
cannot be combined with stored-credential operations. Bridge ports are
allocated by the server. A stopped Runtime remains pending and no ADB or bridge
action is performed. A stale expected revision returns `409 Conflict`.

Plaintext credential fields exist only in request memory. Validation and API
error bodies never echo rejected input. No network response returns plaintext,
ciphertext, a secret reference, or the master key—only the two configured
booleans.

`POST /runtimes/{id}/network/apply` applies the current desired revision.
Direct mode clears Android proxy keys, removes the exact Runtime reverse rule,
and stops only the bridge with the recorded owner token. HTTP proxy mode checks
Runtime/ADB readiness, resolves secrets, verifies the supervised bridge,
installs the exact reverse mapping, applies the loopback Android proxy, and
reads state back. A revision change during apply returns `409` and never marks
the old revision ready.

`POST /runtimes/{id}/network/clear` creates direct desired state. It reconciles
immediately for a running Runtime and remains pending for a stopped Runtime.
Retries are idempotent. Previous bridge ports remain reserved through observed
ownership state until cleanup succeeds.

`GET /runtimes/{id}/network/status` returns safe Runtime, ADB, Android proxy,
ADB reverse, bridge, and connectivity check summaries. Connectivity may remain
`not_run` when no optional probe is configured; no public-IP or geography check
is performed.

Apply errors use `409` for stopped/locked/revision-conflict state, `422` for
invalid desired input, `502` for ADB or bridge failures, and `503` for missing
secrets. Network failures do not alter Device or Runtime lifecycle status.

Frontend and backend must communicate through APIs defined in this file.

Do not invent endpoints independently.

Each endpoint should define:
- method
- path
- request
- response
- error cases

## Common behavior

- Request and response bodies use JSON unless otherwise stated.
- Validation failures return `422 Unprocessable Entity` using FastAPI's standard
  validation error body.
- Resource timestamps are ISO 8601 datetime strings.

## Account object

```json
{
  "id": 1,
  "name": "Primary Account",
  "display_name": "Primary Account",
  "username": "creator",
  "email": "creator@example.com",
  "phone": null,
  "platform": "tiktok",
  "status": "active",
  "registration_state": "registered",
  "health_status": "healthy",
  "status_reason": null,
  "niche": "travel",
  "notes": "Optional notes",
  "tags": ["priority"],
  "runtime_id": null,
  "device_id": null,
  "follower_count": null,
  "following_count": null,
  "likes_count": null,
  "video_count": null,
  "metrics_updated_at": null,
  "secret_present": true,
  "secret_types": ["account_password"],
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00",
  "archived_at": null
}
```

`display_name` is canonical; `name` is a synchronized compatibility alias.
`username` may be null until discovered. Usernames are lowercased and a leading
`@` is removed; emails are lowercased. `device_id` is derived from the assigned
Runtime and is never independently assigned. Metrics are nullable non-negative
integers. Secret values are never returned: only presence and allowlisted types
(`account_password`, `email_password`, `recovery_credential`) are exposed.

## List accounts

- Method: `GET`
- Path: `/accounts`
- Query parameters:
  - `page`: integer greater than or equal to 1; defaults to 1.
  - `page_size`: integer from 1 through 100; defaults to 20.
  - `status`: optional non-empty string; filters by exact status match.
  - `query`: matches name, handle, email, or niche.
  - `niche`, `tag`, `runtime_id`, `device_id`: optional exact filters.
  - `include_archived`: defaults to false.
- Request body: none.
- Success: `200 OK`.

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

Accounts are ordered by `created_at DESC, id DESC`. Filtering and counting occur
before pagination.

Error cases:

- `422 Unprocessable Entity` for invalid pagination or filter values.

## Get account

- Method: `GET`
- Path: `/accounts/{id}`
- Request body: none.
- Success: `200 OK` with an Account object.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.

## Create account

- Method: `POST`
- Path: `/accounts`
- Request body:

```json
{
  "display_name": "Primary Account",
  "username": "creator",
  "email": "creator@example.com",
  "status": "active",
  "registration_state": "registered",
  "niche": "travel",
  "tags": ["priority"],
  "notes": null,
  "runtime_id": null
}
```

`display_name` is required, although the legacy `name` alias remains accepted.
Username, contact fields, Runtime assignment, bounded health state, business
metadata, tags, and metrics are optional. Platform defaults to `tiktok`, status
to `active`, and registration and health states to `unknown`.

- Success: `201 Created` with the created Account object.

Error cases:

- `422 Unprocessable Entity` for a missing or invalid field.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.

## Update account

- Method: `PATCH`
- Path: `/accounts/{id}`
- Request body: any mutable Account field, including registry metadata, tags,
  metrics, and `runtime_id`. Bytes/secrets are not accepted here.
- Success: `200 OK` with the updated Account object.

An empty object is accepted as a no-op. Nullable identity/contact, notes,
business metadata, metrics, and `runtime_id` may be cleared with `null`.
Display name, platform, lifecycle status, registration state, and health state
may not be null.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` for an invalid field or ID.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.

## Assign or unassign an Account Runtime

- `PUT /accounts/{id}/runtime` with `{"runtime_id": 12}` assigns an exact
  existing Runtime.
- `DELETE /accounts/{id}/runtime` clears the assignment.
- Both return the safe Account object, including derived `device_id`.

## Account secrets

- `GET /accounts/{id}/secrets` returns presence metadata only.
- `PUT /accounts/{id}/secrets/{secret_type}` accepts `{"value": "..."}` and
  atomically encrypts/replaces one allowlisted secret.
- `DELETE /accounts/{id}/secrets/{secret_type}` removes it.

No API returns decrypted values, ciphertext, or key material. Validation errors
omit rejected request values. A missing/unsafe/wrong master key fails secret
writes with `503` and causes production startup to fail when encrypted rows
already exist.

## Account registration workflow architecture

`account_registration:v1` is reserved as a server-owned state-driven Workflow
blueprint. Phase 1 does not expose it from `GET /workflow-templates` and does
not accept registration creation requests because signup entry screens/actions
are not yet calibrated. The future request contract will accept IDs only:
Account, Runtime, ManagedApp, ManagedAppVersion, and pinned UI profile. It will
not accept credentials, arbitrary steps, selectors, coordinates, or Job
payloads.

Verification/challenge detection will return a durable operator-required state
with safe type/identifier metadata. Resume will trigger a new observation; it
will not replay the previous UI mutation. Account secrets remain accessible
only to the exact internal typed execution boundary and never appear in the
Workflow API, events, steps, Jobs, or JobLogs.

## Delete/archive account

- Method: `DELETE`
- Path: `/accounts/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body. The Account is soft-archived,
  hidden from ordinary get/list operations, and retained for Job, Workflow, and
  PublishingSession history. It can be restored with a status PATCH.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.

## Runtime object

```json
{
  "id": 1,
  "device_id": 1,
  "name": "TikTok Runtime 1",
  "runtime_type": "redroid",
  "docker_container_name": "redroid-device-01",
  "adb_serial": "localhost:5555",
  "status": "running",
  "last_seen_at": "2026-09-18T10:00:00Z",
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`device_id` is a positive integer referencing an existing Device. `name` is a
non-empty string with a maximum length of 255. `runtime_type` and `status` are
non-empty strings with a maximum length of 50; `redroid` identifies a
Redroid-backed runtime. `docker_container_name` and `adb_serial` are non-empty
strings with a maximum length of 255, or `null`. Each non-null Docker container
name and ADB serial must be unique across Runtime records. `last_seen_at` is an
ISO 8601 datetime string or `null`.

## List runtimes

- Method: `GET`
- Path: `/runtimes`
- Query parameters:
  - `page`: integer greater than or equal to 1; defaults to 1.
  - `page_size`: integer from 1 through 100; defaults to 20.
- Request body: none.
- Success: `200 OK` with `items`, `total`, `page`, and `page_size` fields.

Runtimes are ordered by ascending `id`. `total` counts all runtimes before
pagination.

Error cases:

- `422 Unprocessable Entity` for invalid pagination values.

## Get runtime

- Method: `GET`
- Path: `/runtimes/{id}`
- Request body: none.
- Success: `200 OK` with a Runtime object.

Error cases:

- `404 Not Found` with `{"detail": "Runtime not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.

## Create runtime

- Method: `POST`
- Path: `/runtimes`
- Request body: `device_id`, `name`, `runtime_type`, and `status` are required.
  `docker_container_name`, `adb_serial`, and `last_seen_at` are optional and
  default to `null`.
- Success: `201 Created` with the created Runtime object.

Error cases:

- `404 Not Found` with `{"detail": "Device not found"}` when `device_id`
  references a missing Device.
- `409 Conflict` when a non-null `docker_container_name` or `adb_serial` is
  already assigned to another Runtime.
- `422 Unprocessable Entity` for a missing, unknown, or invalid field.

## Update runtime

- Method: `PATCH`
- Path: `/runtimes/{id}`
- Request body: any subset of `device_id`, `name`, `runtime_type`,
  `docker_container_name`, `adb_serial`, `status`, and `last_seen_at`.
- Success: `200 OK` with the updated Runtime object.

An empty object is accepted as a no-op. `docker_container_name`, `adb_serial`,
and `last_seen_at` may be set to `null`; the other fields may not be `null`.

Error cases:

- `404 Not Found` with `{"detail": "Runtime not found"}` when the Runtime ID
  does not exist.
- `404 Not Found` with `{"detail": "Device not found"}` when `device_id`
  references a missing Device.
- `409 Conflict` when a non-null `docker_container_name` or `adb_serial` is
  already assigned to another Runtime.
- `422 Unprocessable Entity` for an invalid field or ID.

## Delete runtime

- Method: `DELETE`
- Path: `/runtimes/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body.

Deleting a runtime preserves assigned Accounts and sets their `runtime_id`
values to `null`.

Error cases:

- `404 Not Found` with `{"detail": "Runtime not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.

## Job object

```json
{
  "id": 1,
  "job_type": "publish_video",
  "status": "pending",
  "account_id": 1,
  "runtime_id": 1,
  "payload": {"video_id": 42},
  "result": null,
  "error_message": null,
  "attempt_count": 0,
  "max_attempts": 3,
  "scheduled_at": "2026-09-19T10:00:00Z",
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`job_type` is a non-empty string with a maximum length of 100. `status` is one
of `pending`, `running`, `succeeded`, `failed`, `retrying`, or `cancelled`.
`account_id` and `runtime_id` are positive integer references or `null`.
`payload` and `result` accept any JSON value or `null`. `error_message` is a
string or `null`. `attempt_count` is non-negative and `max_attempts` is
positive. Job datetime fields accept ISO 8601 datetime strings or `null`.

Lifecycle actions append persistent logs in the same transaction as the state
change. Automatic messages are `Job claimed`, `Job succeeded`, `Job failed`,
`Job retry scheduled`, and `Job cancelled`. Failure logs retain the failure
message in metadata even when retrying clears `error_message` on the Job.

## List jobs

- Method: `GET`
- Path: `/jobs`
- Query parameters:
  - `page`: integer greater than or equal to 1; defaults to 1.
  - `page_size`: integer from 1 through 100; defaults to 20.
  - `status`: optional Job status; filters by exact match.
  - `job_type`: optional non-empty string up to 100 characters; filters by
    exact match.
  - `account_id`: optional positive integer; filters by exact match.
  - `runtime_id`: optional positive integer; filters by exact match.
- Request body: none.
- Success: `200 OK`.

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

Jobs are ordered by ascending `id`. Filters are combined using AND. `total`
counts all matching Jobs before pagination. A positive account or runtime
filter that has no matches returns an empty collection rather than an error.

Error cases:

- `422 Unprocessable Entity` for invalid pagination or filter values.

## Get job

- Method: `GET`
- Path: `/jobs/{id}`
- Request body: none.
- Success: `200 OK` with a Job object.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not a positive integer.

## List job logs

- Method: `GET`
- Path: `/jobs/{id}/logs`
- Request body: none.
- Success: `200 OK` with an array of Job log objects ordered by ascending log
  ID.

```json
[
  {
    "id": 1,
    "job_id": 1,
    "level": "error",
    "message": "Job failed",
    "metadata": {"error_message": "Upload failed"},
    "created_at": "2026-09-18T10:05:00Z"
  }
]
```

`level` is a non-empty log level string, `message` describes the event, and
`metadata` contains event-specific JSON or is `null`.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the Job ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not a positive integer.

## Create job

- Method: `POST`
- Path: `/jobs`
- Request body: `job_type` is required. All other mutable Job fields are
  optional. `status` defaults to `pending`, `attempt_count` to 0, and
  `max_attempts` to 3. Optional targets and datetime fields default to `null`.
- Success: `201 Created` with the created Job object.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when `account_id`
  references a missing Account.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.
- `422 Unprocessable Entity` for a missing, unknown, or invalid field.

## Update job

- Method: `PATCH`
- Path: `/jobs/{id}`
- Request body: any subset of `job_type`, `status`, `account_id`, `runtime_id`,
  `payload`, `result`, `error_message`, `attempt_count`, `max_attempts`,
  `scheduled_at`, `started_at`, and `completed_at`.
- Success: `200 OK` with the updated Job object.

An empty object is accepted as a no-op. Target IDs, JSON values,
`error_message`, and lifecycle datetimes may be set to `null`. `job_type`,
`status`, `attempt_count`, and `max_attempts` may not be `null`.

Changing `status` through this general-purpose endpoint is not allowed. Clients
must use the claim, succeed, fail, retry, or cancel lifecycle actions. Supplying
the job's current status is accepted as a no-op.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the Job ID does not
  exist.
- `404 Not Found` with `{"detail": "Account not found"}` when `account_id`
  references a missing Account.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.
- `422 Unprocessable Entity` for an invalid field or ID.
- `409 Conflict` when attempting to change `status` directly.

## Delete job

- Method: `DELETE`
- Path: `/jobs/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not a positive integer.

## Claim next job

- Method: `POST`
- Path: `/jobs/claim`
- Request body: optional `{ "claimed_by": "worker-id" }`.
- Success: `200 OK` with the claimed Job object plus transient `claim_token`,
  `claimed_by`, and `lease_expires_at` worker fields.
- No work available: `204 No Content` with an empty body.

Only Jobs with `status=pending` and a `scheduled_at` value that is either null
or not later than the claim time are eligible. The lowest eligible Job ID is
claimed first. Claiming creates a random token, persists only its hash, changes
status to `running`, creates a lease, records `started_at`, and increments
`attempt_count`. Row locking with skip-locked behavior is used
on databases that support it so competing workers do not claim the same Job.

## Mark job succeeded

- Method: `POST`
- Path: `/jobs/{id}/succeed`
- Request body: an object with optional `result`, which may contain any JSON
  value or `null`.
- Success: `200 OK` with the updated Job object.

Worker mutation headers `X-Job-Claim-Token` and `X-Job-Attempt` are required.

The Job must be `running`. The action changes its status to `succeeded`, stores
the supplied result, and records `completed_at`.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `409 Conflict` when the Job is not `running`.
- `422 Unprocessable Entity` for an invalid ID or request body.

## Mark job failed

- Method: `POST`
- Path: `/jobs/{id}/fail`
- Request body: an object with optional safe `error_message`, `error_code`, and
  required/default-false `retryable` classification.
- Success: `200 OK` with the updated Job object.

The claim and lease must be current. Retryable registered errors are returned
to `pending` with a delay when attempts remain; other errors become `failed`.
Unknown exceptions are not assumed retryable.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `409 Conflict` when the Job is not `running`.
- `422 Unprocessable Entity` for an invalid ID or request body.

## Retry failed job

- Method: `POST`
- Path: `/jobs/{id}/retry`
- Request body: optional. An object containing optional `scheduled_at`, an ISO
  8601 datetime string or `null`.
- Success: `200 OK` with the requeued Job object.

The Job must be `failed` and must have `attempt_count < max_attempts`. The
action transitions the Job through `retrying` and back to `pending`. It does
not increment `attempt_count`; the count is incremented only when the next
claim succeeds.

Omitting `scheduled_at`, sending `null`, or omitting the request body makes the
Job immediately eligible for claiming. A future value delays eligibility until
that time. Retrying clears the previous `started_at`, `completed_at`, `result`,
and `error_message`, while preserving the request payload, targets, retry
limits, and current attempt count.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `409 Conflict` when the Job is not `failed`.
- `409 Conflict` when `attempt_count` has reached `max_attempts`.
- `422 Unprocessable Entity` for an invalid ID or request body.

## Cancel job

- Method: `POST`
- Path: `/jobs/{id}/cancel`
- Request body: none.
- Success: `200 OK` with the updated Job object.

Pending/retrying Jobs become `cancelled` immediately. Running Jobs become
`cancelling`; the worker cooperatively stops its exact owned ADB child and then
acknowledges through `POST /jobs/{id}/cancel/acknowledge` using its claim.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `409 Conflict` when the Job is already in a terminal state.
- `422 Unprocessable Entity` when the ID is not a positive integer.

## Worker heartbeat and device execution

- `POST /jobs/{id}/heartbeat` extends only the matching, unexpired token and
  attempt lease and reports whether cancellation was requested.
- `POST /jobs/{id}/execute` revalidates the current claim, registered Job type,
  payload, exact Runtime, cancellation, readiness, network policy, and shared
  Runtime lock before dispatching to `AndroidAutomationService`.
- Stale or expired claims receive `409 Conflict` and cannot overwrite a newer
  attempt.

## Artifact upload and download

- `POST /artifacts` accepts bounded multipart content with validated filename,
  MIME, and content signature. It returns safe metadata only, including
  `state`, `created_at`, and `expires_at`. Quota exhaustion returns HTTP 507
  with stable code `ARTIFACT_STORAGE_FULL`.
- `GET /artifacts/{artifact_id}` returns metadata with state `available`,
  `expired`, or `deleted`. It never returns the storage key or host path.
- `GET /jobs/{job_id}/artifacts/{artifact_id}` requires exact association and
  never accepts a storage path or returns a storage key. Expired/deleted bytes
  return `410 Gone`; the Job and artifact metadata remain queryable.

## Content library

Reusable content is separate from JobArtifact execution data. No content
endpoint accepts a host path or storage key, and responses expose neither.

- `POST /content` accepts one multipart `file` plus required `display_name` and
  optional `notes` and repeated `tags`. It streams into private staging with a
  500 MiB default limit, detects an allowlisted media signature, checks filename
  extension and declared MIME as hints, deduplicates the physical blob by
  SHA-256, and creates an independent logical asset/version. Accepted uploads
  return `202 Accepted`, asset status `processing`, version processing status
  `processing`, no current version, and an atomically created internal
  `content.inspect` Job. Duplicate bytes may therefore produce multiple asset
  IDs and inspection Jobs but only one physical blob. Quota exhaustion returns
  HTTP 507 with `CONTENT_STORAGE_FULL`.
- `GET /content` supports `query`, `asset_type`, `status`, `tag`, `source`,
  `page`, and `page_size`. The default selection omits archived/deleted assets
  and orders by `created_at DESC, id DESC` before pagination.
- `GET /content/{id}` returns safe logical metadata, normalized tags, current
  version metadata when available, and immutable version history. It never
  returns a host path or blob storage key.
- `PATCH /content/{id}` changes only display name, notes, tags, and archive or
  restore state. It never replaces bytes.
- `DELETE /content/{id}` soft-deletes and records history. It does not purge a
  physical blob and refuses protected active delivery state.
- `GET /content/{id}/versions` returns safe immutable version metadata.
- `POST /content/{id}/versions` admits an immutable same-type replacement and
  returns `202`. The previous ready current version remains downloadable while
  the replacement is processing and remains selected if inspection fails.
- `GET /content/{id}/download` resolves the current version server-side and
  streams it with a sanitized filename, known MIME, and `nosniff`. Processing or
  invalid assets without a ready current version return `409` with
  `CONTENT_NOT_READY`. Deleted content returns `410`.
- `GET /content/{id}/thumbnail` returns the current ready version's bounded
  JPEG thumbnail with `nosniff`. Missing, processing, or failed thumbnails
  return `404 CONTENT_THUMBNAIL_UNAVAILABLE`; storage keys and paths are never
  exposed.
- `POST /content/{id}/deliver` accepts an exact `runtime_id`, optional ready
  `version_id`, optional display filename, `import_media`, `allow_repeat`, and
  optional `idempotency_key`. It returns the durable Delivery and internal Job
  status with HTTP 202.
- `GET /content/{id}/deliveries` lists newest-first with optional status and
  Runtime filters plus pagination. `GET /content-deliveries/{id}` returns one
  delivery. Responses expose safe Android remote identity and optional
  MediaStore URI, never blob keys or host paths.

`content.inspect` is server-created only, has no Runtime or Account target, and
is not a public Device Automation action. It reuses Job claims, leases,
heartbeats, idempotent retry, stale-worker fencing, and cooperative cancellation.
Its payload contains only asset/version IDs, which the backend revalidates
against the durable version-to-Job pointer before resolving managed storage.
Safe inspection results contain normalized dimensions, duration, codecs,
container, rates, channel/audio state, rotation/orientation, frame count, and
animation state where applicable. They never contain paths, commands, raw
ffprobe JSON/stderr, or uploaded bytes.

`content.thumbnail` is server-created only and has no Runtime target. It pins
an exact ready visual version and generated variant ID, and reuses claims,
leases, retries, cancellation, and stale-worker fencing. Thumbnail failure does
not change source readiness. It is not accepted by public `POST /jobs` or shown
in the Device Automation selector.

`content.deliver` is also server-created only, but requires one exact Runtime.
Its payload contains only `content_delivery_id`; the pinned version, verified
blob, generated destination, and database-owned ADB serial are resolved again
inside the backend. Explicit keys return the same Delivery/Job. Without a key,
`allow_repeat=false` avoids an existing active/successful duplicate, while
`allow_repeat=true` creates a distinct generated filename. Delivery shares the
Runtime operation lock and never changes lifecycle truth.

Initial signatures are PNG, JPEG, WebP, MP4, MOV, WebM, MP3, M4A/AAC, WAV, and
Ogg audio. Empty, oversized, executable, archive, unsupported, obvious malformed,
and inconsistent MIME/extension uploads are rejected. Full media decoding is
authoritative before readiness. General transcoding, promotion, and
application-specific posting remain outside this phase.

## Device object

```json
{
  "id": 1,
  "name": "Android Device 1",
  "device_type": "physical",
  "platform": "android",
  "os_version": "15",
  "status": "online",
  "notes": "Optional notes",
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`name` is a non-empty string with a maximum length of 255. `device_type`,
`platform`, and `status` are non-empty strings with a maximum length of 50.
`os_version` is a non-empty string with a maximum length of 100. `notes` is a
string or `null`. Leading and trailing whitespace is removed from string fields.

## List devices

- Method: `GET`
- Path: `/devices`
- Query parameters:
  - `page`: integer greater than or equal to 1; defaults to 1.
  - `page_size`: integer from 1 through 100; defaults to 20.
- Request body: none.
- Success: `200 OK` with `items`, `total`, `page`, and `page_size` fields.

Devices are ordered by ascending `id`. `total` counts all devices before
pagination.

Error cases:

- `422 Unprocessable Entity` for invalid pagination values.

## Get device

- Method: `GET`
- Path: `/devices/{id}`
- Request body: none.
- Success: `200 OK` with a Device object.

Error cases:

- `404 Not Found` with `{"detail": "Device not found"}` when the ID does not
  exist.
- `409 Conflict` when the Device belongs to a managed Redroid provisioning.
  Call `POST /redroid-provisionings/{provisioning_id}/deprovision` instead.
- `422 Unprocessable Entity` when `id` is not an integer.

## Device lifecycle status object

```json
{
  "device_id": 1,
  "runtime_id": 1,
  "docker_container_name": "redroid-device-01",
  "adb_serial": "localhost:5555",
  "container_status": "running",
  "boot_completed": true,
  "adb_state": "device",
  "ready": true,
  "runtime_status": "running",
  "device_status": "online"
}
```

`container_status`, `boot_completed`, and `adb_state` report state observed from
local Docker and ADB. `ready` is true only when Docker reports `running`, Android
reports boot complete, and ADB reports `device`. `runtime_status` and
`device_status` are the values persisted after reconciliation.

Lifecycle endpoints require exactly one Runtime belonging to the Device. That
Runtime must have `runtime_type=redroid` and non-null `docker_container_name` and
`adb_serial` values.

Common lifecycle errors:

- `404 Not Found` with `{"detail": "Device not found"}` for a missing Device.
- `409 Conflict` when there is no Runtime, more than one Runtime, a non-Redroid
  Runtime, or incomplete Redroid configuration.
- `502 Bad Gateway` when Docker/ADB execution fails or ADB does not become ready.
- `504 Gateway Timeout` when Android does not boot before the adapter timeout.
- `422 Unprocessable Entity` when `id` is not an integer.

## Get Device lifecycle status

- Method: `GET`
- Path: `/devices/{id}/status`
- Request body: none.
- Success: `200 OK` with a Device lifecycle status object.

The backend inspects the container, checks Android boot state when the container
is running, checks ADB state, and persists the reconciled Runtime and Device
statuses before returning.

## Start Device

- Method: `POST`
- Path: `/devices/{id}/start`
- Request body: none.
- Success: `200 OK` with a Device lifecycle status object.

The backend starts the existing container, waits for Android boot completion,
connects ADB when it is not already ready, verifies ADB state, and persists the
ready state. It does not create or replace the container.

## Stop Device

- Method: `POST`
- Path: `/devices/{id}/stop`
- Request body: none.
- Success: `200 OK` with a Device lifecycle status object.

The backend stops the existing container, observes its resulting Docker and ADB
state, and reconciles database statuses. It does not delete the container or its
persistent data.

## Restart Device

- Method: `POST`
- Path: `/devices/{id}/restart`
- Request body: none.
- Success: `200 OK` with a Device lifecycle status object.

The backend restarts the existing container, waits for Android boot completion,
reconnects ADB when needed, verifies ADB state, and persists the ready state.

## Device screen status object

```json
{
  "device_id": 1,
  "runtime_id": 1,
  "adb_serial": "localhost:5555",
  "status": "open",
  "process_id": 4321
}
```

`status` is `open` when the backend has a live tracked scrcpy process for the
Device and `closed` otherwise. `process_id` is the scrcpy process ID while open
and `null` while closed. Screen endpoints require the same single, fully
configured Redroid Runtime as Device lifecycle endpoints.

Common screen-control errors:

- `404 Not Found` with `{"detail": "Device not found"}` for a missing Device.
- `409 Conflict` when there is no Runtime, more than one Runtime, a non-Redroid
  Runtime, or incomplete Redroid configuration.
- `502 Bad Gateway` when scrcpy cannot be launched or terminated.
- `422 Unprocessable Entity` when `id` is not an integer.

## Open Device screen

- Method: `POST`
- Path: `/devices/{id}/screen/open`
- Request body: none.
- Success: `200 OK` with a Device screen status object.

The backend launches `scrcpy --serial <adb_serial>` as a non-blocking child
process. If that Device already has a live tracked scrcpy process, the existing
session is returned and no duplicate process is launched.

## Close Device screen

- Method: `POST`
- Path: `/devices/{id}/screen/close`
- Request body: none.
- Success: `200 OK` with a closed Device screen status object.

Closing is idempotent. It terminates only the tracked scrcpy process and does
not stop or otherwise modify the Redroid container or Device lifecycle state.

## Get Device screen status

- Method: `GET`
- Path: `/devices/{id}/screen/status`
- Request body: none.
- Success: `200 OK` with a Device screen status object.

The backend checks the tracked child process. A process that has already exited
is removed from tracking and reported as closed.

## Create device

- Method: `POST`
- Path: `/devices`
- Request body: `name`, `device_type`, `platform`, `os_version`, and `status`
  are required. `notes` is optional and defaults to `null`.
- Success: `201 Created` with the created Device object.

Error cases:

- `422 Unprocessable Entity` for a missing, unknown, or invalid field.

## Update device

- Method: `PATCH`
- Path: `/devices/{id}`
- Request body: any subset of `name`, `device_type`, `platform`, `os_version`,
  `status`, and `notes`.
- Success: `200 OK` with the updated Device object.

An empty object is accepted as a no-op. `notes` may be set to `null`; the other
fields may not be `null`.

Error cases:

- `404 Not Found` with `{"detail": "Device not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` for an invalid field or ID.

## Delete device

- Method: `DELETE`
- Path: `/devices/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body.

Deleting a device also deletes its Runtime records. Accounts assigned to those
runtimes are preserved and their `runtime_id` values are set to `null`.

Error cases:

- `404 Not Found` with `{"detail": "Device not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.

## Managed Redroid provisioning status object

```json
{
  "provisioning_id": "2e2bc741-61e8-4e2f-bc38-d9c5cc42d949",
  "state": "completed",
  "device_number": 3,
  "container_name": "redroid-device-03",
  "adb_serial": "localhost:5557",
  "data_path": "/home/longnguyen/redroid-test/device-03-data",
  "network_name": "redroid-device-03-net",
  "image_reference": "redroid/redroid@sha256:a6c464bbedcf1dcb67dbf91f329fbb19bee5b50631f0ca6bda6ed7c41b0e64e2",
  "device_id": 5,
  "runtime_id": 5,
  "data_directory_created": true,
  "network_created": true,
  "container_created": true,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-10-02T16:00:00",
  "updated_at": "2026-10-02T16:00:01"
}
```

Provisioning errors returned by these endpoints are sanitized. Docker command
output, host paths other than the allocated data path, and Python stack traces
are not exposed.

## Provision managed Redroid device

- Method: `POST`
- Path: `/redroid-provisionings`
- Required header: `Idempotency-Key`, 1–255 characters matching
  `[A-Za-z0-9][A-Za-z0-9._:-]*`.
- Request body:

```json
{
  "name": "Redroid Device 03",
  "notes": null,
  "profile": "android-12-redroid"
}
```

The backend derives the device number, Docker names, ADB port and serial, data
path, network, image, labels, and container options. Supplying any of those as
additional request fields returns `422 Unprocessable Entity`.

- Completed synchronously: `201 Created` with a provisioning status object.
- Existing attempt still active or locked by another request: `202 Accepted`
  with the same durable provisioning status object.
- Same idempotency key and request: returns the existing attempt without
  allocating a second resource tuple.

Error cases:

- `409 Conflict` for an idempotency-key fingerprint mismatch, allocation or
  resource conflict, or inconsistent recovery state.
- `422 Unprocessable Entity` for a missing/invalid header, request, or profile.
- `503 Service Unavailable` when provisioning configuration or host preflight
  is unavailable.
- `500 Internal Server Error` for an unexpected durable failure. When an
  attempt exists, the sanitized detail includes its provisioning ID.

This is a host-administration endpoint. It must remain accessible only from a
trusted/local deployment until administrator authentication and authorization
are implemented.

## Get managed Redroid provisioning status

- Method: `GET`
- Path: `/redroid-provisionings/{provisioning_id}`
- Request body: none.
- Success: `200 OK` with the durable provisioning status object.

Error cases:

- `404 Not Found` with `{"detail": "Provisioning attempt not found"}` when the
  ID is unknown.

## Workflow orchestration

V1 accepts only server-owned, versioned templates. Clients cannot provide a
step list, Job type/payload, ADB serial, command, host path, or Android path.
The initial template is `content_delivery_review:v1`; it pins the explicit
Runtime and exact ready ContentAssetVersion at creation, creates a typed
`content.deliver` Job, and then waits durably for operator approval.
`content_delivery_wait_review:v1` inserts a bounded `workflow.wait` between
delivery and approval. `wait_duration_seconds` is 1–86,400 seconds; the server
persists one UTC `resume_at`, creates no wait Job, and advances only when that
stored deadline is due.

- `GET /workflow-templates` lists safe template metadata and parameter schema.
- `POST /workflows` creates a draft from `template_key`, optional version,
  name/description, explicit `runtime_id`, `content_asset_id`, optional exact
  version/account, validated parameters, and optional idempotency key.
- `GET /workflows` lists newest first with status, template, Runtime, account,
  content-asset, and pagination filters.
- `GET /workflows/{id}` returns bindings and ordered step state.
- `POST /workflows/{id}/start|pause|resume|cancel|retry` performs a validated
  durable state transition. Pause is boundary-only and never suspends a Job.
- `POST /workflows/{id}/steps/{step_id}/approve|reject` records a bounded actor
  and optional comment for the exact current approval step.
- `GET /workflows/{id}/events` returns chronological bounded safe history.

Delivery step results are bounded projections: delivery and Job IDs, pinned
Runtime/version IDs, delivery status, remote filename, MediaStore URI, and
digest when available. They exclude Job payloads, host/storage paths, storage
keys, claim tokens, ADB commands, and raw logs. Events are ordered by
`created_at`, then ID.

An identical idempotency key and request fingerprint returns the existing
Workflow; the same key with different input returns `409`. `WORKFLOW_BUSY`
means another process owns that Workflow's transition lock. Approval rejection
uses `WORKFLOW_APPROVAL_REJECTED`. Responses and events omit internal Job
payloads, claim ownership, paths, commands, and subprocess output.

## Managed Android packages

Managed-app endpoints accept definitions and APK bytes only. Clients cannot
provide discovered package/version/signer metadata, a storage key, host path,
tool command, Runtime, ADB serial, or installation flags.

- `GET /managed-apps` lists newest first with backend pagination.
- `POST /managed-apps` accepts only `key`, `display_name`,
  `android_package_name`, and `install_policy`. Repeating the exact definition
  is idempotent; conflicting reuse returns `409`.
- `GET /managed-apps/{id}` and `PATCH /managed-apps/{id}` return/update safe
  metadata. PATCH supports display name, status, and installation policy;
  key/package identity is not mutable.
- `POST /managed-apps/{id}/versions` accepts one multipart APK plus optional
  display metadata. It returns `202`; identical bytes for the same app reuse
  the existing version. Split APK/APKS/AAB uploads are unsupported.
- `GET /managed-apps/{id}/versions` and
  `GET /managed-apps/{id}/versions/{version_id}` expose normalized inspection
  state and never expose a path, storage key, or raw tool output.
- `POST /managed-apps/{id}/versions/{version_id}/approve-basic` explicitly
  accepts an admission-checked immutable APK for mandatory post-install package
  verification. It does not assert package metadata or signer identity.
- `POST /managed-apps/{id}/versions/{version_id}/activate` accepts only a ready,
  verified package-matching version or an explicitly approved basic version.
  Repeating the same activation is idempotent and no Runtime installation is
  triggered.
- `POST /managed-apps/{id}/versions/{version_id}/retire` preserves history and
  rejects the active or currently inspecting version.

Upload creates the internal runtime-free `app.inspect` Job. Public `POST /jobs`
rejects that type. Deterministic package/signature/malformed errors are
non-retryable; missing or timed-out tooling is a sanitized retryable
infrastructure failure. The normal Content Library does not list or download
managed package assets, and generic media delivery rejects them.

Version responses expose `inspection_level` (`basic` or `verified`),
`package_verification` (`post_install` or `pre_and_post_install`), and basic
approval state. Basic approval is never presented as signer verification.

Runtime installation endpoints accept only managed IDs. They never accept an
APK path, package name, ADB serial, or install flags:

- `GET /runtimes/{id}/apps` returns durable desired/observed installation state.
- `POST /runtimes/{id}/apps/{app_id}/install` accepts an optional ready
  `managed_app_version_id`; otherwise it pins the current version. A stopped
  Runtime records pending intent and creates no Job.
- `POST /runtimes/{id}/apps/{app_id}/verify` creates an internal `app.verify`
  Job only for a running Runtime.
- `GET /runtimes/{id}/publishing-readiness` reports independent booleans for
  Android/ADB readiness, required-app convergence, and their conjunction. It
  does not imply login or platform acceptance.

`app.install` and `app.verify` are server-created only, exact-Runtime Jobs.
Stable failures include `APP_NOT_INSTALLED`, `APP_VERSION_MISMATCH`,
`APP_PACKAGE_MISMATCH`, `APP_BASIC_UPDATE_REQUIRES_VERIFIED`,
`APP_SIGNATURE_MISMATCH`, `APP_INSTALL_FAILED`, `APP_VERIFY_FAILED`,
`APP_PACKAGE_DISABLED`, `APP_DOWNGRADE_BLOCKED`, `APP_VERSION_NOT_READY`,
`APP_BLOB_MISSING`, `APP_BLOB_INVALID`, and `APP_RUNTIME_UNAVAILABLE`.

## Publishing preparation

- `publishing_prepare_review:v1` requires `account_id`, `runtime_id`,
  `content_asset_version_id`, `managed_app_id`, and
  `managed_app_version_id`.
- `POST /workflows` accepts those exact bindings but no custom steps, package
  name, Job payload, or Android/host path.
- Internal `publishing.verify_runtime`, `publishing.verify_app`, and
  `publishing.verify_app_state` Jobs are server-created only. The template
  reuses pinned `content.deliver` and safe `device.launch_app` before approval.
- `GET /publishing-sessions` and `GET /publishing-sessions/{id}` expose safe
  preparation history. Approval does not represent a publish action.

## TikTok UI detection foundation

`tiktok.detect_screen` is a server-created internal Job and is rejected by
generic `POST /jobs`. Its payload contains only exact `runtime_id`,
`managed_app_id`, and server-pinned `ui_profile_id`. Execution revalidates the
installed managed app/profile, acquires the exact Runtime lock, enforces the
screen conflict policy, and observes a bounded UIAutomator hierarchy. It never
launches the application.

`POST /runtimes/{runtime_id}/tiktok/detect-screen` accepts only
`{"managed_app_id": N}` and returns `202` with the server-created Job. It does
not accept a profile, package, selector, coordinate, command, or ADB serial.

The safe result contains only screen, foreground package, profile identity and
fingerprint, node count, display category, and `changed=false`. Raw XML, node
text, screenshots, ADB output, selectors, and paths are never returned. There
is no public endpoint for raw UI primitives or caller-defined selectors.
Uncalibrated login/signup/challenge activities are returned as `UNKNOWN` and
do not authorize navigation or account automation. Testing profile v12
recognizes the observed fresh-install `TERMS_CONSENT` screen, but its
`Agree and continue` control is observational only and no mutation endpoint is
exposed. Unsupported screens remain non-actionable.

Testing profile v13 additionally recognizes the observed post-terms
`ONBOARDING_INTERESTS` screen. Testing profile v14 preserves that classifier
and authorizes only the observed unique `Skip` control; interest tiles and the
disabled `Next (0)` control remain non-actionable.

`POST /runtimes/{runtime_id}/tiktok/skip-interests` accepts only
`{"managed_app_id": N}` and creates the server-owned, one-attempt
`tiktok.skip_interests` Job. The action requires two matching fresh semantic
observations, an overlay-free `ONBOARDING_INTERESTS` state, and the unique
profile-owned Skip selector while holding the exact Runtime lock. It never
selects an interest or activates Next. HOME is the calibrated idempotent
successor: invoking the action there returns `changed=false` without a tap.
After dispatch, an unrecognized successor is reported as calibration-required
and is never replayed automatically.

`POST /runtimes/{runtime_id}/tiktok/open-profile` accepts only
`{"managed_app_id": N}` and creates the server-owned, one-attempt
`tiktok.open_profile` Job. It requires overlay-free HOME, two matching fresh
semantic observations, and the unique profile-owned bottom Profile tab. It
accepts no selector, coordinate, package, or navigation command. The calibrated
destination is session-dependent: a logged-in session reaches `PROFILE`, while
a logged-out session reaches `SIGNUP_METHOD`. The endpoint name is retained for
compatibility and means activate Profile tab, not guarantee a PROFILE screen.
Invoking it while already at either calibrated destination returns
`changed=false` and `tap_dispatched=false`; an unknown destination fails closed
as `TIKTOK_UI_STATE_UNCERTAIN` and is never replayed automatically.

Testing profile v17 recognizes the observed logged-out `SIGNUP_METHOD` surface
from distinct scene/content/phone roots plus title, phone-input, and email-method
signals. Continue, Log in, and Close are reinforcing observations only. No
registration method or field mutation is exposed by this contract.

`POST /runtimes/{runtime_id}/tiktok/choose-email-signup` accepts only
`{"managed_app_id": N}` and creates a one-attempt server-owned Job. From
`SIGNUP_METHOD`, it resolves only the unique observed `Continue with Email`
semantic child, requires two matching observations under the exact Runtime
lock, and dispatches one tap. It accepts no email, password, phone value,
provider, selector, coordinate, package, key event, or ADB command. The only
calibrated successor is `EMAIL_ENTRY`; invoking it there is a zero-tap
idempotent success. It never enters or submits credentials.

`POST /runtimes/{runtime_id}/tiktok/set-registration-email` accepts only
`{"managed_app_id": N, "account_id": N}`. The Account must exist, be assigned
to the exact Runtime, and contain a canonically normalized email. The Job
payload persists IDs only; execution resolves the email from the Account row
inside the typed boundary. Results expose account ID, email length,
verification, and Continue-enabled state but never the email value. Job logs
may contain length and SHA-256 only. The action focuses the single profile-owned
EditText, replaces and verifies it, and does not activate Continue, phone,
Login, save-login, or any other control.

`POST /runtimes/{runtime_id}/tiktok/continue-registration-email` accepts only
`{"managed_app_id": N, "account_id": N}`. The Account and Runtime binding
rules are identical to email entry. The one-attempt Job resolves the canonical
email server-side, verifies exact equality in the calibrated field, requires
the unique profile-owned Continue button to be enabled across two identical
fresh observations, and dispatches exactly one tap. It accepts and persists no
email, password, secret, selector, coordinate, or input command. A resulting
email-link/code screen is returned as `VERIFICATION_REQUIRED`; invoking the
action there is a zero-tap idempotent result. The operator must complete that
checkpoint manually. Stable pre-dispatch failures include
`TIKTOK_REGISTRATION_EMAIL_MISMATCH` and
`TIKTOK_REGISTRATION_CONTINUE_DISABLED`.

Testing profile v2 recognizes the calibrated English-locale HOME screen for
`com.ss.android.ugc.trill` 44.4.3 from multiple observed navigation signals.
`POST /runtimes/{runtime_id}/tiktok/open-create` accepts only
`{"managed_app_id": N}` and creates the server-owned `tiktok.open_create`
Job. The Job requires calibrated HOME, resolves the unique profile-owned
Create selector, and holds the exact Runtime lock through its postcondition.
No selector, package, coordinate, or tap input is accepted. An already
calibrated media picker is idempotent with `changed=false`.

Testing profile v3 additionally recognizes the observed `CAMERA_CREATE` screen
from multiple exact camera UI signals. `open_create` succeeds when it reaches
CAMERA_CREATE and returns `changed=false` when invoked there again.

`POST /runtimes/{runtime_id}/tiktok/open-media-picker` also accepts only
`{"managed_app_id": N}`. It creates the internal
`tiktok.open_media_picker` Job, requires CAMERA_CREATE, resolves the unique
server-owned gallery entry, and accepts no selector, path, coordinate, package,
or ADB input. It does not select media. Until an observed MEDIA_PICKER profile
is calibrated, a dispatched transition whose postcondition cannot be proven is
reported conservatively rather than retried blindly. Testing profile v4 now
recognizes the observed picker from exact root, header, Recents, tab-strip,
ViewPager, and GridView signals. The empty-state message is optional, so the
same definition applies after media is delivered. Calling this endpoint while
already on MEDIA_PICKER succeeds with `changed=false` and dispatches no tap.

Android permission-controller dialogs are classified separately from TikTok
screens. `TIKTOK_PERMISSION_REQUIRED` is a non-retryable operator boundary;
safe logs may include overlay kind, permission kind, action, and whether this
Job dispatched its action. The backend never selects a permission response.
The observed photos/media prompt uses
`permission_allow_button`/`permission_deny_button` and is handled by the same
operator boundary. Unknown overlays remain `TIKTOK_UI_STATE_UNCERTAIN`.

`POST /runtimes/{runtime_id}/tiktok/select-media` accepts exactly:

```json
{"managed_app_id": 1, "content_delivery_id": 69}
```

It creates the internal one-attempt `tiktok.select_media` Job. The delivery
must have succeeded with MediaStore import on the exact Runtime and must still
pin a ready library ContentAssetVersion. The request cannot supply a filename,
MediaStore ID, selector, coordinate, package, path, or ADB input.

The internal `MediaIdentityResolver` may resolve an otherwise
unlabelled tile only when the exact delivery is the sole eligible typed
MediaStore record, the picker has exactly one candidate tile, and its observed
duration matches the authoritative MediaStore duration. Any additional
eligible record or evidence mismatch fails closed. The hierarchy, screen,
inventory, and candidate are revalidated immediately before the one internal
tap. The Job is never automatically replayed after dispatch. The first proven
departure from MEDIA_PICKER is reported as `screen_after=UNKNOWN` with
`calibration_required=true`; no endpoint exposes the inventory or accepts a
caller-selected tile.

Testing profile v5 calibrates the observed successor as `EDIT_MEDIA` from
multiple stable scene, bottom-action, Next-action, and tool-list signals.
Successful selection therefore returns `screen_after=EDIT_MEDIA`,
`changed=true`, and `tap_dispatched=true`. Calling the same typed action while
already on EDIT_MEDIA is a non-mutating idempotent observation with
`changed=false` and `tap_dispatched=false`; it never taps the picker again.
This endpoint does not activate Next or enter the caption/post flow.

`POST /runtimes/{runtime_id}/tiktok/open-caption` accepts only
`{"managed_app_id": N}`. It creates a server-owned `tiktok.open_caption` Job
with `max_attempts=1`; callers cannot provide selectors, coordinates, text, or
ADB input. The action requires EDIT_MEDIA, revalidates an unchanged hierarchy
and the unique profile-owned `editor_next_action`, then taps once. An
uncalibrated successor is returned truthfully with `calibration_required=true`
rather than replayed. Testing profile v7 classifies the observed successor as
READY_TO_PUBLISH. Re-entry there is non-mutating. The endpoint never activates
Drafts/Post and never enters caption text.

`POST /runtimes/{runtime_id}/tiktok/set-caption` accepts exactly
`{"managed_app_id": N, "caption": "..."}` and creates a one-attempt
`tiktok.set_caption` Job. The normalized caption is limited to 150 characters
after Unicode NFKC, deterministic whitespace collapse, edge trimming, and
control-character rejection; ordinary multilingual letters, hashtags, emoji,
and punctuation remain valid. Empty is allowed. The current typed ADB text
provider supports a verified ASCII transport subset and rejects unsupported
transport input before focusing or changing the field. Results expose
screen before/after, changed, caption length, verification, and whether the
keyboard appeared, but never echo caption text. The exact `gbc` EditText must
resolve uniquely on READY_TO_PUBLISH. Exact equality is verified after entry;
an already-equal caption is a zero-mutation success. No selector, coordinate,
package, keyevent, ADB command, or final submission control is accepted.

`POST /runtimes/{runtime_id}/tiktok/set-post-options` accepts exactly
`{"managed_app_id": N, "privacy": "everyone" | "only_you" | null}` and
creates a one-attempt `tiktok.set_post_options` Job. `null` is a safe
calibration/observation request. From READY_TO_PUBLISH the action may open only
the profile-owned privacy entry; from POST_SETTINGS it observes directly. It
revalidates the foreground, screen, hierarchy fingerprint, and unique target
before any tap, then verifies the selected checked state. The observed
`Friends` choice is intentionally not supported because its accessibility
description contains dynamic account-specific text. No arbitrary option,
selector, coordinate, Drafts, Post, or final submission action is accepted.

`POST /runtimes/{runtime_id}/tiktok/prepare-publish` accepts exactly
`managed_app_id`, `content_delivery_id`, `expected_caption`, and
`expected_privacy` (`everyone` or `only_you`). It creates the internal,
read-only `tiktok.prepare_publish` Job. The backend revalidates the exact
succeeded imported delivery and pinned ContentAssetVersion, verifies its exact
MediaStore ID/name/size/MIME/duration, and then verifies caption, privacy
summary, and unique observational Drafts/Post controls across two unchanged
READY_TO_PUBLISH snapshots. Results never echo caption text and report
`prepared=true`, individual verification booleans, and `changed=false`. The
action accepts no selectors, coordinates, paths, package names, MediaStore IDs,
ADB input, or submission instruction.

## Deprovision a managed Redroid device

- Method: `POST`
- Path: `/redroid-provisionings/{provisioning_id}/deprovision`
- Request body: none.
- Success: `200 OK` with a durable deprovisioning status object.
- Concurrent execution: `202 Accepted` with the current durable status. Retry
  the same path; the provisioning ID is the idempotency identity.

```json
{
  "provisioning_id": "2e2bc741-61e8-4e2f-bc38-d9c5cc42d949",
  "state": "deprovisioned",
  "container_removed": true,
  "network_removed": true,
  "data_preserved": true,
  "data_path": "/home/longnguyen/redroid-test/device-03-data",
  "device_id": 5,
  "runtime_id": 5,
  "error_code": null,
  "error_message": null,
  "created_at": "2026-10-02T16:00:00",
  "updated_at": "2026-10-03T16:00:00"
}
```

Only a completed `redroid_provisionings` record can authorize this operation.
The backend first acquires the shared Runtime operation lock. Active automation
or another Runtime mutation returns `409 Conflict` and is not interrupted.
Pending/retrying `device.*`, `content.deliver`, `app.install`, and `app.verify`
Jobs for that exact Runtime
are cancelled with a durable `runtime_deprovisioned` event; no Job or Delivery
is redirected. Active delivery/automation blocks deprovision. The backend then
closes its tracked screen, stops a running container, verifies the recorded
Docker IDs and ownership labels, removes the owned container and its dedicated
network, and removes the active Device/Runtime records. Historical Jobs and
JobLogs remain, with the Runtime foreign key cleared. The provisioning record
remains as a tombstone with historical Device/Runtime IDs; ContentDelivery
clears its nullable Runtime pointer while preserving `runtime_id_snapshot`.
Workflow history follows the same rule. A pending Workflow pinned to the
removed Runtime fails durably with `WORKFLOW_RUNTIME_UNAVAILABLE` and is never
retargeted.
RuntimeAppInstallation history also clears its nullable live Runtime pointer,
retains `runtime_id_snapshot`, and records `removed`.
The allocated
device number is permanently reserved.

The persistent data directory and its ownership marker are preserved. There is
no API for destructive data removal.

Error cases:

- `404 Not Found` when the provisioning ID is unknown.
- `409 Conflict` when the record is ineligible, ownership or DB mapping is
  ambiguous, an owned network remains attached, or a recoverable deprovision
  step fails. A durable failure returns the deprovisioning status object in
  `deprovision_failed` state; an ineligible record returns a conventional error
  detail.
- `500 Internal Server Error` when deprovisioning dependencies are unavailable
  or an unexpected failure cannot be classified.

Messages are sanitized and never include raw Docker output. This endpoint is a
host-administration capability and must not be exposed publicly without
administrator authentication and authorization.
