# Database

## Development database
SQLite, configured by default as `sqlite:///./tiktok_manager.db` relative to the
backend process working directory. Set `DATABASE_URL` to override the connection
URL.

Tables are initialized explicitly by calling `app.database.init_db()`. Schema
creation is idempotent; application import does not create database files or
tables automatically.

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
- created_at: UTC datetime, set when the row is created
- updated_at: UTC datetime, set when the row is created and updated by the ORM

The SQL table name is `accounts`. Platform and status remain strings so their
allowed values can be defined alongside API validation in a later task.
