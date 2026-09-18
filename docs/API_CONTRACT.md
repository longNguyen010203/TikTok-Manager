# API Contract

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
  "runtime_type": "emulator",
  "status": "running",
  "last_seen_at": "2026-09-18T10:00:00Z",
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`device_id` is a positive integer referencing an existing Device. `name` is a
non-empty string with a maximum length of 255. `runtime_type` and `status` are
non-empty strings with a maximum length of 50. `last_seen_at` is an ISO 8601
datetime string or `null`.

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
  `last_seen_at` is optional and defaults to `null`.
- Success: `201 Created` with the created Runtime object.

Error cases:

- `404 Not Found` with `{"detail": "Device not found"}` when `device_id`
  references a missing Device.
- `422 Unprocessable Entity` for a missing, unknown, or invalid field.

## Update runtime

- Method: `PATCH`
- Path: `/runtimes/{id}`
- Request body: any subset of `device_id`, `name`, `runtime_type`, `status`, and
  `last_seen_at`.
- Success: `200 OK` with the updated Runtime object.

An empty object is accepted as a no-op. `last_seen_at` may be set to `null`; the
other fields may not be `null`.

Error cases:

- `404 Not Found` with `{"detail": "Runtime not found"}` when the Runtime ID
  does not exist.
- `404 Not Found` with `{"detail": "Device not found"}` when `device_id`
  references a missing Device.
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
- `422 Unprocessable Entity` when `id` is not an integer.

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
