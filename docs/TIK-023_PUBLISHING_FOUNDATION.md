# TIK-023 Managed App and Publishing Foundation

## Phase 3 boundary

Phase 3 adds durable per-Runtime install intent, typed install/verify Jobs,
required-app convergence, and publishing-readiness APIs. It does not add
publishing workflows, UI automation, login/account behavior, or arbitrary
package management.

## Package lifecycle

An operator creates an app definition with a fixed key and expected Android
package. APK upload streams into the private ContentStorage staging directory,
hashes under the existing content quota, performs bounded ZIP admission, and
deduplicates through ContentBlob. A hidden `managed_app_package` ContentAsset
and immutable version own the blob reference.

The server creates exactly one active runtime-free `app.inspect` Job. Workers
use the existing claim, lease, heartbeat, retry, and cancellation protocol and
call the backend inspection boundary. Reconciliation recreates a missing or
retryably failed inspection Job without allowing concurrent active Jobs for
the same version.

Admission starts every version at `inspection_level=basic`; this describes ZIP
and manifest admission only and is not a signature claim. Valid transitions are:

```text
uploaded -> inspecting -> ready
                       -> invalid
ready/invalid -> retired (except an active current version)
```

Infrastructure failures leave inspection recoverable. Deterministic malformed,
package mismatch, or invalid-signature results mark the immutable version and
internal ContentAsset invalid without deleting bytes.

## Inspection and activation

The configured absolute aapt2 and apksigner executables must be regular,
trusted, non-writable executables. Invocation uses argument arrays,
`shell=False`, managed local blob paths, time and output limits, and exact-child
cancellation. APKs are never extracted to arbitrary paths or executed on the
host. Only normalized package, version, SDK, signer fingerprint, inspector
identity, and safe errors persist.

The discovered package must equal the ManagedApp's expected package. Once a
ready/current signer exists, a candidate with a different signer is invalid
with `APK_SIGNER_MISMATCH`; signer rotation is intentionally not supported yet.
Activation is explicit and idempotent. Old versions remain historical. Existing
live installation rows are marked `outdated` and pin the newly activated
version, but activation itself creates no install Job or Android operation.

When trusted tools are unavailable, an operator may explicitly call
`POST /managed-apps/{app_id}/versions/{version_id}/approve-basic`. This is
allowed only for a version that already passed bounded admission. It records a
`version_basic_approved` event and makes the immutable digest eligible for
activation while retaining `inspection_level=basic` and
`package_verification=post_install`. It does not invent package, version, or
signer metadata. Successful aapt2/apksigner inspection instead promotes the
version to `verified` with `package_verification=pre_and_post_install`.

## Runtime installation and verification

RuntimeAppInstallation stores desired and observed package state independently
from Runtime lifecycle. `app.install` and `app.verify` are internal,
server-created Jobs with an exact Runtime and an installation-ID-only payload.
Workers reuse existing claim/lease/retry/cancellation; the backend re-resolves
the serial, app, version, and verified ContentBlob.

AndroidAppManagementService acquires RuntimeOperationGuard, applies the shared
screen/readiness policy, and uses only typed AdbExecutor operations. Installation
has one fixed `adb -s SERIAL install -r APK` policy—never downgrade,
permission-grant, uninstall, clear-data, split, or caller-defined flags. Exact
desired state causes no reinstall. A known older same-signer verified version
may update; newer, unknown, disabled, or signer-mismatched packages fail closed.
Basic mode permits a fresh install, or a verify-only repeat when durable state
already links the exact managed version. An ambiguous basic-mode update requires
verified inspection. Package-manager state—expected ManagedApp package, package
path, enabled state, and available version metadata—is mandatory after every
install; ADB success alone is never authoritative. Basic mode provides no
signer assurance.

ContentBlob storage keys intentionally have no filename extension. Because the
ADB client rejects an extensionless local install source before streaming, the
installer creates a generated mode-0600 `.apk` hard-link view in the private
content staging directory. It verifies that the view is the same inode and size
as the digest-checked blob, passes only that backend-owned path to ADB, and
removes the link after success, failure, timeout, or cancellation. No package
bytes are copied and abandoned generated views are eligible for safe staging
reconciliation.

## Convergence and publishing readiness

Provisioning creates pending desired rows for active required apps with a ready
current version. It preserves the stopped-Runtime contract and never starts
Android. After explicit start, convergence is scheduled only after lifecycle
readiness and after releasing the lifecycle lock. Restart queues verification
for an installed required app; missing/outdated state uses `app.install`. An app
failure never changes Device or Runtime lifecycle truth.

- `runtime_ready`: container, Android boot, and exact ADB target are ready.
- `required_apps_ready`: all active required apps are observed at their current
  desired version.
- `publishing_ready`: both are true; this says nothing about login or platform
  acceptance.

Deprovision blocks active app operations, cancels queued app Jobs, clears the
nullable Runtime FK, and retains installation/run/event history and the Runtime
snapshot.

## Isolation and retention

Package assets never appear in ordinary content selections and are rejected by
generic content delivery and workflow content binding. ManagedAppVersion's
ContentAssetVersion foreign key is an ordinary strong blob reference, so
content reconciliation and cleanup cannot classify active APK bytes as
orphaned. Physical deduplication may share identical bytes across logical apps,
but every app still performs its own expected-package validation.

## Host prerequisites

Configure trusted absolute paths in `~/.config/tiktok-manager/config.toml`:

```toml
[managed_apps]
max_apk_bytes = 524288000
aapt2_path = "/usr/bin/aapt2"
apksigner_path = "/usr/bin/apksigner"
inspection_timeout_seconds = 30
max_stdout_bytes = 1048576
max_stderr_bytes = 262144
zip_max_entries = 20000
zip_max_expanded_bytes = 2147483648
zip_max_compression_ratio = 200
```

The installer reports missing tooling and never installs or downloads it.
Missing tools prevent stronger pre-install verification, but do not prevent an
explicitly approved controlled APK from using the basic/post-install path.
Operators must supply lawfully obtained APKs. Single-file APK is the only
supported package format; AAB, APKS, and split-package sets are rejected.

## Publishing preparation workflow

`publishing_prepare_review:v1` is a server-owned sequential template. Creation
requires explicit Account, Runtime, ready library ContentAssetVersion,
ManagedApp, and install-eligible ManagedAppVersion IDs. All five bindings are
pinned; Account assignment must match the Runtime and later version activation
cannot alter an existing workflow.

The steps are `publishing.verify_runtime`, `publishing.verify_app`,
`content.deliver`, `device.launch_app`, `publishing.verify_app_state`, and
`workflow.approval`. The publishing checks are internal typed Jobs using the
existing claim/lease/retry/cancel boundary. Delivery pins the exact content
version and launch derives the package from ManagedApp. Verification is limited
to Android/ADB readiness, required-app readiness, installed package/version
state, and safe process observation. It never inspects login, account identity,
credentials, UI contents, or platform challenges.

`publishing_sessions` is a bounded domain-history projection of authoritative
Workflow state. Approval means only “environment prepared for publishing”; it
does not mean content was published.

Frontend app management remains later. Split packages, downgrade, signer
rotation, fleet-wide rollout, login/account automation, and final publishing
actions remain unsupported.
