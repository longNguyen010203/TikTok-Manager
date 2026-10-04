# API Contract

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
  "username": "creator",
  "platform": "tiktok",
  "status": "active",
  "notes": "Optional notes",
  "runtime_id": null,
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`name` and `username` are non-empty strings with a maximum length of 255.
`platform` and `status` are non-empty strings with a maximum length of 50.
`notes` is a string or `null`. `runtime_id` is a positive integer referencing an
existing Runtime, or `null`. Leading and trailing whitespace is removed from
string fields.

## List accounts

- Method: `GET`
- Path: `/accounts`
- Query parameters:
  - `page`: integer greater than or equal to 1; defaults to 1.
  - `page_size`: integer from 1 through 100; defaults to 20.
  - `status`: optional non-empty string; filters by exact status match.
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

Accounts are ordered by ascending `id`. `total` counts all records matching the
filter before pagination.

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
  "name": "Primary Account",
  "username": "creator",
  "platform": "tiktok",
  "status": "active",
  "notes": null,
  "runtime_id": null
}
```

`name`, `username`, `platform`, and `status` are required. `notes` and
`runtime_id` are optional and default to `null`.

- Success: `201 Created` with the created Account object.

Error cases:

- `422 Unprocessable Entity` for a missing or invalid field.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.

## Update account

- Method: `PATCH`
- Path: `/accounts/{id}`
- Request body: any subset of `name`, `username`, `platform`, `status`, `notes`,
  and `runtime_id`.
- Success: `200 OK` with the updated Account object.

An empty object is accepted as a no-op. `notes` and `runtime_id` may be set to
`null`; the other fields may not be `null`.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` for an invalid field or ID.
- `404 Not Found` with `{"detail": "Runtime not found"}` when `runtime_id`
  references a missing Runtime.

## Delete account

- Method: `DELETE`
- Path: `/accounts/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body.

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
- Request body: none.
- Success: `200 OK` with the claimed Job object.
- No work available: `204 No Content` with an empty body.

Only Jobs with `status=pending` and a `scheduled_at` value that is either null
or not later than the claim time are eligible. The lowest eligible Job ID is
claimed first. Claiming changes the status to `running`, records `started_at`,
and increments `attempt_count`. Row locking with skip-locked behavior is used
on databases that support it so competing workers do not claim the same Job.

## Mark job succeeded

- Method: `POST`
- Path: `/jobs/{id}/succeed`
- Request body: an object with optional `result`, which may contain any JSON
  value or `null`.
- Success: `200 OK` with the updated Job object.

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
- Request body: an object with optional `error_message` string or `null`.
- Success: `200 OK` with the updated Job object.

The Job must be `running`. The action changes its status to `failed`, stores the
supplied error message, and records `completed_at`.

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

The Job must be `pending`, `running`, or `retrying`. The action changes its
status to `cancelled` and records `completed_at`.

Error cases:

- `404 Not Found` with `{"detail": "Job not found"}` when the ID does not
  exist.
- `409 Conflict` when the Job is already in a terminal state.
- `422 Unprocessable Entity` when the ID is not a positive integer.

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
The backend closes its tracked screen, stops a running container, verifies the
recorded Docker IDs and ownership labels, removes the owned container and its
dedicated network, then removes the active Device/Runtime records. The
provisioning record remains as a tombstone with historical Device/Runtime IDs.
The allocated device number is permanently reserved.

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
