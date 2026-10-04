# TikTok Manager local runtime

## One-time installation

From the repository root, run:

```bash
./scripts/install-tiktok-manager.sh
```

The installer creates or reuses the backend virtual environment, creates the
durable configuration, backs up and integrity-checks an existing operational
database, applies Alembic migrations, creates/validates the credential master
key, installs a user systemd unit, and enables it immediately and for future
user sessions.

After installation, normal use requires no shell exports or recurring setup:
open the application in the browser, create/start a device, enter proxy host,
port, username, and password, then Save and Apply.

## Durable local state

- Operational database:
  `~/.local/share/tiktok-manager/tiktok_manager.db`
- Application configuration:
  `~/.config/tiktok-manager/config.toml`
- Credential master key:
  `~/.config/tiktok-manager/credentials.key` (mode `0600`)
- Database backups:
  `~/.local/share/tiktok-manager/backups/`
- Managed automation artifacts:
  `~/.local/share/tiktok-manager/artifacts/`

The TOML file stores only non-secret host settings: canonical database path,
installation identity, Redroid image/data/profile/ADB allocation, bridge port
range and private runtime directories. Proxy credentials are encrypted in the
database; their master key remains outside it.

The optional `[automation]` section contains the non-secret artifact root and
maximum artifact size. Existing installations without that section use safe
defaults. Normal use does not require artifact-related environment exports.

Back up `credentials.key` separately with access controls equivalent to the
database backup. A database backup containing encrypted proxy credentials can
only be decrypted with the matching installation key; losing the key makes
those stored credentials unrecoverable.

Repo-local SQLite files are development artifacts, and tests use temporary
databases. The production user service rejects a repository-local SQLite
database and fails clearly if the canonical database is missing or incompatible.

## Service operation

The unit is `tiktok-manager-backend.service`. It runs the project virtualenv,
binds only `127.0.0.1:8000`, restarts on failure, and inherits the native user
systemd bus used by supervised proxy bridges. It neither starts nor stops the
Docker daemon, and backend restarts leave managed Android containers running.

Useful diagnostics:

```bash
systemctl --user status tiktok-manager-backend.service
journalctl --user -u tiktok-manager-backend.service
```

Startup logs report the database mode, resolved SQLite path, and Alembic
revision. They never report proxy credentials or the master key.
