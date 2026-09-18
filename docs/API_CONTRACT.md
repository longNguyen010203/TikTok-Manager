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
- Account timestamps are ISO 8601 datetime strings.

## Account object

```json
{
  "id": 1,
  "name": "Primary Account",
  "username": "creator",
  "platform": "tiktok",
  "status": "active",
  "notes": "Optional notes",
  "created_at": "2026-09-18T10:00:00",
  "updated_at": "2026-09-18T10:00:00"
}
```

`name` and `username` are non-empty strings with a maximum length of 255.
`platform` and `status` are non-empty strings with a maximum length of 50.
`notes` is a string or `null`. Leading and trailing whitespace is removed from
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
  "notes": null
}
```

`name`, `username`, `platform`, and `status` are required. `notes` is optional
and defaults to `null`.

- Success: `201 Created` with the created Account object.

Error cases:

- `422 Unprocessable Entity` for a missing or invalid field.

## Update account

- Method: `PATCH`
- Path: `/accounts/{id}`
- Request body: any subset of `name`, `username`, `platform`, `status`, and
  `notes`.
- Success: `200 OK` with the updated Account object.

An empty object is accepted as a no-op. `notes` may be set to `null`; the other
fields may not be `null`.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` for an invalid field or ID.

## Delete account

- Method: `DELETE`
- Path: `/accounts/{id}`
- Request body: none.
- Success: `204 No Content` with an empty body.

Error cases:

- `404 Not Found` with `{"detail": "Account not found"}` when the ID does not
  exist.
- `422 Unprocessable Entity` when `id` is not an integer.
