# TIK-020 Android Automation Foundation

## Scope

Phase 2 provides service-only, generic Android primitives for exact Redroid
Runtimes. It does not expose public automation endpoints, register worker job
handlers, or implement account/platform workflows.

## Runtime ownership and locking

`RuntimeTargetResolver` reloads the Runtime immediately before execution and
derives the Device ID, ADB serial, and Docker container exclusively from the
database. Missing, non-Redroid, incomplete, stopped, deprovisioning, busy, and
screen-controlled Runtimes fail with sanitized stable errors. Automation never
starts a stopped Runtime.

`RuntimeOperationGuard` uses a mode-private, owner-validated lock directory and
`flock` files named `runtime-<id>.lock`. Files are opened with `O_NOFOLLOW`.
It supports nonblocking and bounded-wait acquisition and releases locks on
context exit or process death. The previous network guard is a compatibility
wrapper over the same implementation and lock identity. Lifecycle and screen
mutations also use this shared identity.

The deprovision foundation exposes a conservative busy probe. Any current
Runtime operation prevents later deprovision orchestration from assuming that
automation resources are idle; it never interrupts the lock owner.

## ADB boundary

`AdbExecutor` exposes typed methods only. Every subprocess command is an
argument array beginning with `adb -s <stored-runtime-serial>`, uses
`shell=False`, has a bounded timeout and bounded output, and returns sanitized
failures. There is no raw command or shell-string entry point and no
`adb kill-server` operation. A cancellation hook is present for Phase 3's
cooperative Job cancellation work.

Package names, coordinates, swipe duration, text, key events, local artifacts,
and remote paths are validated before reaching the executor. Input primitives
exist for service tests but are not public handlers in this phase.

## Readiness and network policy

Automation readiness checks the exact container state, Android boot property,
ADB transport state, provisioning state, Runtime lock, and tracked scrcpy
state. A running-but-temporarily-unready device is polled only for a bounded
period. A stopped device is rejected without being started.

Network readiness is opt-in per future handler. Local screenshot, package,
file, and input primitives do not require it. A network-requiring handler may
accept current direct/disabled state, or an HTTP proxy only when its desired
and applied revisions match and its state is ready. Unmanaged legacy direct
networking is accepted only when the handler explicitly allows it. Geography
is never a readiness signal.

## Artifact storage

The default root is `~/.local/share/tiktok-manager/artifacts/`. It must be an
owner-controlled real directory, is forced to mode `0700`, and contains only
generated storage keys with mode `0600`. Writes use a private temporary name,
`fsync`, and an atomic rename. Symlinks, traversal, foreign ownership, unsafe
permissions, oversized files, and invalid storage keys are rejected.

SQLite stores only metadata: safe display filename, generated storage key,
MIME type, byte count, SHA-256, retention timestamp, and cleanup state. Service
results never expose the artifact root or storage key.

Screenshots use `adb -s SERIAL exec-out screencap -p`; the service validates the
PNG signature and IHDR dimensions before storage. Push operations accept only
an artifact ID and target `/sdcard/Download/TikTokManager/`. Pull operations
accept only a direct child of that same directory and ingest the result as a
new artifact.

Media import accepts managed image/video artifacts, pushes to the managed
directory, verifies remote size, requests an Android MediaStore scan, and
polls for a matching media row for a bounded interval.

## Phase 3 execution boundary

Phase 3 adds validated `device.*` definitions, a complete
`JobExecutionContext`, durable hashed claims, leases and heartbeats, structured
events, typed retry classification, and cooperative cancellation. Workers call
the narrow `/jobs/{id}/execute` backend boundary and never execute ADB.

Raw claim tokens exist only in claim responses and worker memory. SQLite stores
their SHA-256 digest. Every worker mutation is fenced by token, attempt, and
lease expiry. Expired safe actions may retry; uncertain post-dispatch actions
fail for operator review rather than being replayed blindly.

Controlled uploads use `POST /artifacts`; downloads require an exact
Job/artifact association. Neither endpoint exposes the artifact root or
storage key. Input-control primitives remain unavailable as public Job types.

## Phase 4 live validation

The complete Job-to-worker-to-backend-to-ADB path was validated on a disposable
managed Redroid Runtime provisioned and deprovisioned through the public
lifecycle APIs. Screenshot capture and download, package observation,
launch/force-stop, managed upload/push/pull, and MediaStore import succeeded.
Runtime-lock, active-screen, stopped-Runtime, cancellation, expired-lease, and
backend-restart behavior were also exercised. Device03 was used only as a
read-only isolation control and remained stopped and unchanged.

Live validation established three implementation details required for reliable
operation:

- Package launch resolves an exact launcher component and invokes it with a
  typed `am start` command; it does not depend on Redroid's `monkey` behavior.
- Readiness may reconnect only the exact stored ADB serial after a backend/ADB
  server restart, without starting a stopped container.
- Cooperative cancellation is preserved through readiness and file/media
  transfer error translation. The worker allows a longer HTTP execution window
  than ordinary control requests so backend-owned command deadlines and
  cancellation determine the result.

Job progress events are buffered while an ADB operation owns the Runtime lock,
preventing a long SQLite write transaction from blocking independent worker
heartbeats and cancellation requests. No claim token, raw ADB output, artifact
bytes, or host storage path is written to JobLog metadata.
