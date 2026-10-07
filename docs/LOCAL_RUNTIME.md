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

The optional `[workflow]` section contains the private per-Workflow lock
directory, bounded orchestrator polling interval, and reconciliation batch
size. Existing installations receive defaults without replacing operator
values. It contains no credentials, claim tokens, or executable definitions.

The optional `[managed_apps]` section contains the APK admission limit,
absolute aapt2/apksigner paths, bounded inspection timeout/output sizes, and
ZIP entry/expanded-size/compression-ratio limits. Defaults are added without
overwriting existing operator settings. The installer checks configured tool
paths and reports missing/unsafe tools but does not download or install Android
SDK tooling. Package uploads remain safely stored and recoverable while
inspection reports `APK_INSPECTOR_UNAVAILABLE` until both trusted tools exist.
An admission-checked APK can instead be explicitly operator-approved at basic
assurance; it then relies on mandatory Android package/path/enabled verification
after install and makes no signer claim. Once a ManagedAppVersion is installable,
Runtime install/verify uses only ADB and the integrity-checked managed blob; it
does not invoke aapt2/apksigner. No SDK tooling or APK is downloaded automatically.
The install boundary creates only a temporary private `.apk` hard link below
the managed content staging directory; this satisfies ADB's local filename
requirement without duplicating large APK bytes or exposing a host path.

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

The workflow unit is `tiktok-manager-workflow-orchestrator.service`. It starts
after and wants the backend, uses the same project virtual environment and
canonical configuration/database, and restarts on failure. It only reconciles
durable Workflow/Step state and materializes typed Jobs; the worker remains the
only Job claimant/executor. There is no dependency between worker and
orchestrator, so the units have no ordering cycle.

Polling defaults to two seconds. Failed top-level passes use bounded
exponential backoff capped at 30 seconds; a successful pass resets the delay.
SIGTERM sets a graceful stop boundary. Wait deadlines, linked Jobs, approval,
pause, and cancellation state are durable across service restarts.

Publishing preparation uses the same backend, worker, and workflow
orchestrator; no additional service is required. Its verification steps are
typed internal Jobs, and PublishingSession is a projection of durable Workflow
truth. Service restarts never recalculate or substitute its pinned
Account/Runtime/content/app bindings.

Every SQLite connection created by the application installs
`PRAGMA foreign_keys=ON`, including backend and standalone orchestrator
processes. Workflow reconciliation commits only short database transitions;
it never holds a SQLite write transaction while a Job, Android operation, or
other external process is running. Managed provisioning also allocates Device
and Runtime IDs above durable historical provisioning IDs so a deleted
Runtime's snapshot identity is not reused.

Android UI parsing limits are durable non-secret `[android_ui]` configuration:
`max_xml_bytes`, `max_nodes`, `max_depth`, `max_text_length`, and
`max_attribute_length`. Bootstrap adds safe defaults without overwriting
operator settings. UIAutomator data is processed in memory and is not
persisted. Phase 3 calibration uses a disposable Runtime and the testing
44.4.3 profile; no additional daemon is required.

The first Phase 3 calibration Runtime opened TikTok 44.4.3 on its login/signup
activity rather than HOME. Normal runtime setup does not attempt login,
signup, challenge handling, or account switching. UI mutation actions remain
disabled until an operator supplies a lawfully prepared disposable Runtime
whose initial state is HOME; the backend will not navigate past the unsupported
state automatically.

Runtime 17 later provided an operator-prepared HOME state for the same app
version. Testing profile v2 now contains its observed semantic HOME signals
with no coordinate fallback. This only enables HOME detection; it does not
expose a UI mutation endpoint.

Runtime 17 also calibrated the guarded editor boundary. `tiktok.open_caption`
is a one-attempt Job and may only be created through the narrow Runtime API.
Its single observed Next dispatch reached `READY_TO_PUBLISH`; it did not type a
caption or activate Drafts/Post. UI profiles v6/v7 remain `testing` and exact
to Trill 44.4.3 / 440403 at the calibrated portrait display.

Caption entry uses profile v8 and `POST
/runtimes/{runtime_id}/tiktok/set-caption`. It is one-attempt, holds the shared
Runtime lock, and verifies exact field text before returning. Only caption
length/hash enter structured logs. This action does not press Drafts/Post or
change post settings.

Privacy calibration uses immutable testing profiles v9/v10 and `POST
/runtimes/{runtime_id}/tiktok/set-post-options`. Profile v9 authorizes only the
observed READY_TO_PUBLISH privacy entry. Profile v10 recognizes the observed
POST_SETTINGS bottom sheet and its checked-state controls. Only `everyone` and
`only_you` are server-owned values; `privacy=null` observes/calibrates without
selecting a value. The action is one-attempt, holds the Runtime lock, and never
targets Drafts/Post.

Final pre-publish verification uses `POST
/runtimes/{runtime_id}/tiktok/prepare-publish`. It is read-only but still holds
the exact Runtime lock so the observed hierarchy and MediaStore identity cannot
race another Runtime mutation. It verifies two unchanged READY_TO_PUBLISH
snapshots and never taps, focuses, types, navigates Back, or activates Drafts or
Post.

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
systemctl --user status tiktok-manager-workflow-orchestrator.service
systemctl --user status tiktok-manager-artifact-cleanup.timer
systemctl --user status tiktok-manager-content-cleanup.timer
journalctl --user -u tiktok-manager-worker.service
journalctl --user -u tiktok-manager-workflow-orchestrator.service
journalctl --user -u tiktok-manager-artifact-cleanup.service
journalctl --user -u tiktok-manager-content-cleanup.service
```

For workflow-specific diagnosis, safe retry/cancellation guidance,
deprovision interaction, and backup rules, see
[`TIK-022_WORKFLOW_RUNBOOK.md`](TIK-022_WORKFLOW_RUNBOOK.md).

Artifact files are operational cache/output data rather than database backup
contents. Back up the artifact directory separately if historical screenshots
or pulled files must survive retention cleanup. Job and JobLog metadata is not
automatically deleted when artifact bytes expire.

Content blobs are also operational data outside SQLite. A database backup does
not contain library media, so back up the content root together with the
database when the reusable library must be restored. The content database rows
and blob directory must be treated as one backup set.
