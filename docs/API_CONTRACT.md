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
