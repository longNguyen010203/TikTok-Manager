# TIK-019 Phase 4 bridge operations

The real bridge is an externally supervised transient systemd service named
`tiktok-manager-network-r<RUNTIME_ID>.service`. It listens only on
`127.0.0.1:<allocated-host-port>` and forwards HTTP proxy traffic to the
configured upstream. Android reaches that listener only through the exact
Runtime ADB reverse rule.

## Host prerequisites

Choose one supported supervision scope:

- `RUNTIME_NETWORK_BRIDGE_SYSTEMD_SCOPE=user` requires a running user systemd
  manager for the backend account.
- `RUNTIME_NETWORK_BRIDGE_SYSTEMD_SCOPE=system` requires the backend service
  account to be explicitly authorized to create, inspect, and stop only the
  `tiktok-manager-network-r*.service` transient units. Running the web service
  broadly as root is not recommended.

Configure `RUNTIME_NETWORK_BRIDGE_STATE_DIRECTORY` as a private directory owned
by that account. The default user scope uses
`/run/user/<uid>/tiktok-manager-network`; a system service should normally use a
dedicated protected runtime directory such as `/run/tiktok-manager-network`.
The configured Python executable and bridge worker must be regular readable
files. The host systemd version must support `LoadCredential`.

The backend process must inherit the user-bus environment, normally:

```text
XDG_RUNTIME_DIR=/run/user/<uid>
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/<uid>/bus
```

An interactive shell can have a working user manager while a separately
launched automation process lacks these variables; in that case
`systemctl --user` fails with `No medium found` even though the bus socket
exists. Configure the backend service environment explicitly rather than
weakening supervisor ownership checks.

Proxy credentials remain environment-secret references in desired state, for
example `env:TIKTOK_PROXY_TEST_USERNAME`. Plaintext values must be injected into
the backend service environment by the deployment secret mechanism. Do not put
them in API bodies, unit environment variables, command lines, or committed
files.

## Recovery and ownership

The supervisor persists a mode-0600 non-secret manifest. Inspection and stop
require agreement between that manifest and live systemd/process/listener
evidence. An ownership conflict is deliberately not auto-repaired and no
process is killed.

Systemd may report a worker active just before its listening socket is bound.
The supervisor performs a bounded readiness wait and records the process birth
identity only after the exact loopback listener is observed.

Manager startup never starts a stopped Android Runtime. It stops a stopped
Runtime's orphan bridge only when ownership is proven, and restores ephemeral
bridge/reverse/proxy state only for a Runtime already observed running and ADB
ready. Start and restart endpoints reapply pending HTTP intent after Android is
ready, without coupling network failure to lifecycle readiness.

## Live-test gate

Before provisioning a disposable test device, verify all of the following:

1. one supervision scope is usable by the backend account;
2. a controlled upstream HTTP proxy host and port are available;
3. any required `TIKTOK_PROXY_*` environment secrets are present;
4. the operational API is running with the same database and environment;
5. Device 03 control snapshots can be collected without mutation.

If the gate fails, do not provision the disposable Runtime and do not apply
network state to any existing device. This preserves Device 01/02/03 and avoids
leaving untestable resources behind.
