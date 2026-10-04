# TIK-021 content pipeline

## Durable content boundary

The content library owns reusable, long-lived media independently from a Job.
A `ContentAsset` is mutable catalog metadata; every byte revision is an
immutable `ContentAssetVersion`; physically identical bytes share one
`ContentBlob`. `JobArtifact` remains execution-scoped input/output governed by
the existing shorter retention policy. Phase 2 does not promote JobArtifacts,
process media asynchronously, generate variants, or deliver content to Android.

## Admission and storage

Uploads are streamed to a generated staging file while SHA-256 and size are
calculated. The backend does not trust browser MIME or filename extension: it
detects a conservative allowlisted signature and requires supplied hints to be
consistent. Uploaded bytes are never executed. A cross-process maintenance
flock serializes the quota/digest/install transaction; SQLite digest uniqueness
is the final race invariant.

The default root is `~/.local/share/tiktok-manager/content/`, containing private
`blobs/`, `staging/`, and `.maintenance.lock`. Directories are `0700`, files are
`0600`, path components and files reject symlinks, and installs use fsync plus
atomic rename. The API never accepts or reveals storage keys or filesystem
paths.

Content uses a separate 500 MiB upload limit and 20 GiB unique-blob quota. A
duplicate digest does not consume the quota twice. Ready library bytes are not
evicted automatically. Quota exhaustion is `CONTENT_STORAGE_FULL`.

## Inspection Jobs and authoritative metadata

Admission atomically creates a runtime-free internal `content.inspect` Job and
stores its ID on the processing version. It cannot be created through the
public Job-create API or selected as Device Automation. The normal worker
claims it with the existing hashed-token lease, heartbeat, retry, and
cooperative cancellation rules, then calls the backend inspection endpoint.
Workers never receive a blob path or run ffprobe themselves.

## Runtime delivery

`POST /content/{id}/deliver` pins a ready ContentAssetVersion and exact Redroid
Runtime into ContentDelivery, then creates an internal `content.deliver` Job in
the same transaction. The public Job-create API cannot create either internal
content Job. ContentBlob bytes are not copied into JobArtifact storage: the
backend verifies their managed regular file, size, and SHA-256 and passes a
typed ManagedFileSource to AndroidAutomationService.

Every remote name combines a sanitized name, durable delivery ID, and inspected
canonical extension. The destination is always
`/sdcard/Download/TikTokManager/`. With `import_media=true`, bounded MediaStore
scan and observation records only a safe content URI. Delivery does not require
network readiness.

An explicit idempotency key is scoped to pinned version and Runtime and returns
the same Delivery and Job. Without a key, an existing pending, delivering, or
successful delivery prevents accidental repetition when `allow_repeat=false`.
`allow_repeat=true` creates an intentional delivery with a distinct name.
Retries retain the same version, Runtime snapshot, and remote identity.

Pending cancellation updates Job and Delivery immediately. Running cancellation
terminates only the owned ADB child and records a conservative uncertain outcome
if transfer may already have completed. The shared Runtime flock prevents
lifecycle, screen, network, deprovision, and delivery overlap. Deprovision
cancels queued deliveries, blocks on active delivery, clears the nullable
Runtime FK, and preserves the Runtime snapshot and history. Archived ready
assets remain deliverable; deleted assets do not.

One private `content-version-{id}.lock` flock prevents concurrent authoritative
inspection. The lock is no-follow, private, host-local, and released on process
death. The version's database state remains authoritative. Worker polling also
reconciles processing versions whose inspection Job is missing or terminally
failed for a retryable infrastructure reason.

Pillow authoritatively verifies PNG, JPEG, and WebP content, including bounded
dimensions, total pixels, frame count, animation state, and safe EXIF
orientation. Decompression-bomb protection remains enabled. ffprobe handles
MP4, MOV, WebM, MP3, M4A/AAC, WAV, and Ogg using an absolute trusted executable,
argument arrays, `shell=False`, a local file, a file-only protocol allowlist,
bounded time/output, JSON, and exact owned-child cancellation. Only normalized
metadata is persisted; raw probe JSON, stderr, commands, and paths are not.

Success changes the version to `ready`, stores normalized metadata, selects it
as current when it is the first valid or newest successful intended version,
and marks the active asset ready in one DB commit. Deterministic invalid media
changes the version to `invalid`; without an older current version the asset is
invalid, while a failed replacement preserves the older ready asset/download.
Retryable infrastructure or cancellation errors leave the version processing.
Events record `processing_queued`, `processing_started`, `ready`, and `invalid`
without raw tool output.

## State and history

Admission creates a logical asset and version 1 in `processing`, records upload
and queue events, and returns HTTP 202. Clients poll until ready or invalid.
Archive is reversible catalog state; delete is soft and does not purge physical
bytes. Metadata changes and state transitions append safe events. Prior version
bytes remain immutable. `POST /content/{id}/versions` admits a replacement but
does not switch away from the previous current version until inspection passes.

Filesystem and SQLite commits cannot be one transaction. Failed owned installs
are compensated when their generated identity is known. Reconciliation removes
only old, generated, privately owned staging files; it marks proven missing blob
rows and unreferenced rows; and it reports foreign or uncertain filesystem state
without deleting it.

## Later phases

Thumbnail and compatibility variants may later use `content_variants`.
Transcoding, promotion from JobArtifact, and frontend library
workflows remain later work.
