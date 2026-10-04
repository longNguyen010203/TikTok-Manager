# TIK-019 network service foundation

Phase 2 implements durable desired and observed per-Runtime network state.
Phase 3 adds its API and apply/clear orchestration. Phase 4 adds a systemd-backed
loopback HTTP bridge and startup/lifecycle recovery. Lifecycle readiness remains
separate from network readiness.

## Desired-state behavior

`RuntimeNetworkService` treats an absent configuration as unmanaged. Creating
or changing desired state requires an optimistic `expected_revision` and
creates an immutable revision snapshot. HTTP proxy desired state requires a
Redroid Runtime with an ADB serial. Desired changes do not invoke ADB or the
bridge supervisor; an HTTP proxy update therefore becomes `pending`, including
when its Runtime is stopped. Explicit apply and clear endpoints invoke adapter
boundaries only after Runtime-scoped locking and readiness checks.

An HTTP configuration retains its allocated host port across HTTP revisions.
When a stopped Runtime changes to direct mode, historical HTTP ports remain
reserved while observed ownership remains. Successful cleanup clears ownership
and releases the reservation.

The provisioning helper adds direct revision 1 and disabled observed state to
the caller's existing transaction. New managed provisioning calls it with
applied revision 1 because a never-booted fresh Runtime has no prior proxy
state. Legacy Runtimes are not backfilled.

## Allocation and locking

Host bridge ports come from the configured inclusive range, defaulting to
8800-8899. Allocation holds a host-wide no-follow `flock`, excludes ports
already persisted by another Runtime, and checks availability by binding a
temporary socket to `127.0.0.1`. The database unique constraint remains the
final allocation invariant. An occupied port is skipped and no process is
terminated.

Runtime mutation locks are named only from a validated positive Runtime ID.
Lock files are opened relative to a no-follow directory descriptor and with
`O_NOFOLLOW`. The guard is an interface boundary that can later be replaced by
PostgreSQL advisory locks.

## Secrets

New API writes accept a username/password pair and store it with authenticated
Fernet encryption in the Runtime credential row. The installation master key
is a mode-0600, non-symlink file outside SQLite at
`~/.config/tiktok-manager/credentials.key`. A clean install creates it
automatically. If encrypted rows exist and the key is missing, invalid, or
wrong, startup/application fails safely rather than generating a replacement.

`NetworkCredentialProvider` resolves either encrypted storage or the temporary
legacy `env:TIKTOK_PROXY_...` source. The legacy resolver rejects file paths and
unrelated variables. Resolved values use a wrapper whose ordinary string and
repr forms are redacted. Values are passed separately from `BridgeSpec`; the
bridge specification contains no credentials.

API-oriented desired-state views contain only `username_configured` and
`password_configured` booleans. They omit both resolved values and stored
references.

## Android and bridge boundaries

`AndroidNetworkAdapter` provides get/set/clear operations for Android global
proxy keys and exact ADB reverse list/add/remove operations. Every subprocess
command has the form `adb -s <exact Runtime serial> ...`, passes an argument
list with `shell=False`, and carries no proxy credentials.

`HostProxyBridgeSupervisor` remains the service boundary. Production uses a
systemd transient-unit implementation; automated orchestration tests can still
inject the in-memory fake. The implementation uses a small generic HTTP proxy
bridge worker and does not expose implementation-specific fields in the
database.

The production supervisor proves a Runtime-specific unit name, owner token,
loopback address and port, process start identity, and adapter/config
fingerprint before it reports or stops a bridge. A PID, port, or executable
name alone is never accepted as ownership. Conflicting evidence returns
`BRIDGE_OWNERSHIP_CONFLICT` and leaves the process untouched.

Resolved credentials are written to a unique mode-0600 attempt file and
imported with systemd `LoadCredential`. They do not appear in the worker argv, unit
description, manifest, or database, and the source attempt file is removed
after systemd has loaded it. The worker replaces any client-supplied upstream
proxy authorization header with the resolved credential.

At manager startup, lifecycle discovery runs first. Managed stopped Runtimes
remain stopped, proven-owned orphan bridges are stopped, and HTTP intent is
left pending. Running Runtimes are reconciled through the same apply operation,
which restores a missing bridge, exact ADB reverse, or Android proxy setting.
Device start/restart similarly reapplies non-direct or unapplied desired state;
network failure is persisted separately and cannot turn a lifecycle-ready
Runtime into stopped/offline state.

## Direct-mode WebView limitation

Clearing direct mode removes the Android global proxy keys, exact ADB reverse
rule, and proven-owned host bridge. An already-running Android WebView or
browser process can nevertheless retain its prior proxy state temporarily.
This is process-level Android caching, not incomplete backend cleanup. Restart
the Android Runtime/device to recreate those processes; direct connectivity
then returns normally.

## Trusted settings

Stable host settings are read from
`~/.config/tiktok-manager/config.toml`; normal operation requires no exported
variables. Explicit environment overrides remain available for isolated
development/tests.

- `RUNTIME_NETWORK_BRIDGE_PORT_START` defaults to `8800`.
- `RUNTIME_NETWORK_BRIDGE_PORT_END` defaults to `8899`.
- `RUNTIME_NETWORK_BRIDGE_DEVICE_PORT` defaults to `8888`.
- `RUNTIME_NETWORK_LOCK_DIRECTORY` defaults to
  `/tmp/tiktok-manager-network-locks`.
- `RUNTIME_NETWORK_BRIDGE_STATE_DIRECTORY` defaults to
  `/run/user/<uid>/tiktok-manager-network`.
- `RUNTIME_NETWORK_BRIDGE_PYTHON` defaults to the backend Python executable.
- `RUNTIME_NETWORK_BRIDGE_SYSTEMD_SCOPE` defaults to `user`; `system` is
  supported when the backend service account is authorized to manage the
  Runtime-specific transient units.

These settings validate port ranges, scope, and absolute paths. A usable user
systemd manager (or explicit system-unit authorization) is an operational
prerequisite; the supervisor fails closed when neither is available.
