# Database

## Development database
SQLite, configured by default as `sqlite:///./tiktok_manager.db` relative to the
backend process working directory. Set `DATABASE_URL` to override the connection
URL.

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
- runtime_type: string (maximum 50 characters, required)
- status: string (maximum 50 characters, required)
- last_seen_at: nullable UTC datetime
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

## Relationships

- One Device has zero or more Runtime records. Deleting a Device cascades to its
  Runtime records.
- One Runtime belongs to exactly one Device.
- One Runtime may have zero or more Account records assigned to it.
- One Account may reference one Runtime through nullable `runtime_id`. Deleting
  that Runtime preserves the Account and sets `runtime_id` to null.
