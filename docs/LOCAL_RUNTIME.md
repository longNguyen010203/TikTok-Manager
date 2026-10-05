# TikTok Manager local runtime

## One-time installation

From the repository root, run:

```bash
./scripts/install-tiktok-manager.sh
```

The installer creates or reuses the backend virtual environment, creates the
durable configuration, backs up and integrity-checks an existing operational
database, applies Alembic migrations, creates/validates the credential master
key, installs the backend and worker user services plus the artifact-cleanup
timer, and enables them immediately and for future user sessions.

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
- Reusable content library:
  `~/.local/share/tiktok-manager/content/`

The TOML file stores only non-secret host settings: canonical database path,
installation identity, Redroid image/data/profile/ADB allocation, bridge port
range and private runtime directories. Proxy credentials are encrypted in the
database; their master key remains outside it.

The optional `[automation]` section contains the non-secret artifact root,
100 MiB per-file limit, 1 GiB total quota, 30-day result retention, 7-day
upload retention, and 6-hour cleanup interval. Existing installations without
those keys use these safe defaults. Normal use does not require
artifact-related environment exports.

The optional `[content]` section contains the non-secret reusable content root,
500 MiB single-upload limit, 20 GiB unique-blob quota, image decode limits,
inspection lock directory, absolute ffprobe path/time/output bounds, absolute
ffmpeg path, thumbnail timeout, daily cleanup interval, and orphan grace.
Missing keys are added with defaults without replacing operator values. Content
storage is independent from automation artifact storage and retention: ready
content is never evicted automatically to satisfy quota.

Content delivery reads verified ContentBlobs directly and does not duplicate
them into JobArtifact storage. It uses the existing worker service and shared
Runtime operation lock and requires no additional host daemon or path setting.

`/usr/bin/ffprobe` from the Ubuntu `ffmpeg` package is the verified default.
The installer checks that the configured path is absolute, regular,
non-symlinked, and executable; it does not silently install OS packages. Images
can be decoded with Pillow, but video/audio inspection reports the retryable
`CONTENT_FFPROBE_UNAVAILABLE` error when the configured executable is missing or
unsafe. The installer separately validates `/usr/bin/ffmpeg`; it is used only
for bounded local video-frame thumbnail generation.

Back up `credentials.key` separately with access controls equivalent to the
database backup. A database backup containing encrypted proxy credentials can
only be decrypted with the matching installation key; losing the key makes
those stored credentials unrecoverable.

Repo-local SQLite files are development artifacts, and tests use temporary
databases. The production user service rejects a repository-local SQLite
database and fails clearly if the canonical database is missing or incompatible.

## Service operation

The backend unit is `tiktok-manager-backend.service`. It runs the project virtualenv,
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

The worker unit is `tiktok-manager-worker.service`. It starts after and wants
the backend unit, connects only to `127.0.0.1:8000`, restarts on failure, and
uses bounded exponential reconnect backoff while the backend is unavailable.
It never stores claim tokens in its unit or environment. Worker restart does
not adopt process-local state: abandoned claims are fenced and recovered by
the backend lease reaper.

Artifact retention is run by
`tiktok-manager-artifact-cleanup.timer` approximately every six hours. The
timer is persistent across user-manager downtime and the cleanup command uses
a nonblocking cross-process lock, so overlapping cleanup cannot occur.
Reusable-content cleanup runs independently through
`tiktok-manager-content-cleanup.timer` approximately every 24 hours and never
age-expires or quota-evicts ready content.

Useful additional diagnostics:

```bash
systemctl --user status tiktok-manager-worker.service
systemctl --user status tiktok-manager-artifact-cleanup.timer
systemctl --user status tiktok-manager-content-cleanup.timer
journalctl --user -u tiktok-manager-worker.service
journalctl --user -u tiktok-manager-artifact-cleanup.service
journalctl --user -u tiktok-manager-content-cleanup.service
```

Artifact files are operational cache/output data rather than database backup
contents. Back up the artifact directory separately if historical screenshots
or pulled files must survive retention cleanup. Job and JobLog metadata is not
automatically deleted when artifact bytes expire.

Content blobs are also operational data outside SQLite. A database backup does
not contain library media, so back up the content root together with the
database when the reusable library must be restored. The content database rows
and blob directory must be treated as one backup set.
