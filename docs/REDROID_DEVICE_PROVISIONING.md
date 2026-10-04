# Redroid device provisioning

Managed Redroid lifecycle operations use one `Device` record with exactly one
configured `Runtime` record. A second Runtime must not be attached to the same
Device because lifecycle and screen endpoints intentionally reject ambiguous
assignments.

Every managed Redroid device must have unique boundaries:

- Docker container name
- host ADB endpoint
- host directory mounted at `/data`
- Docker network

Do not bind host `/dev/binder`, `/dev/hwbinder`, `/dev/vndbinder`, or equivalent
paths from the host binderfs into managed containers. Redroid creates the Binder
devices it needs in the container's private mount namespace. The host bootstrap
only verifies that Binder kernel support is ready.

## Automated provisioning foundation

Automated provisioning uses a durable `redroid_provisionings` manifest before
creating Docker or filesystem resources. Allocation is serialized briefly in
the database and never derives a device number from Device/Runtime primary keys.
Every device number remains reserved after failure or rollback.

Trusted provisioning configuration is stored in
`~/.config/tiktok-manager/config.toml` and created by the one-time installer.
Normal users do not export these values. The corresponding environment names
remain available as explicit development/test overrides:

- `TIKTOK_MANAGER_INSTALLATION_ID`: stable safe installation identifier
- `REDROID_PROVISIONING_IMAGE`: immutable `image@sha256:<64 hex>` reference
- `REDROID_PROVISIONING_DATA_ROOT`: absolute non-root directory
- `REDROID_PROVISIONING_BASE_ADB_PORT`: optional; defaults to `5554`
- `REDROID_PROVISIONING_NETWORK_PREFIX`: optional; defaults to `redroid-device`
- `REDROID_PROVISIONING_PROFILE`: optional; defaults to `android-12-redroid`

The provisioning adapter passes argument arrays to Docker with `shell=False`,
publishes ADB on `127.0.0.1` only, creates no Binder mappings, and leaves the
container stopped. Container, network, and filesystem rollback requires the
recorded resource ID plus matching installation/provisioning/ownership labels
or marker. A name alone is never authority to delete a resource.

Existing Device 01 and Device 02 remain legacy managed runtimes. They are not
automatically adopted into the provisioning manifest and cannot be removed by
the provisioning rollback path.

The TIK-019 network schema does not backfill these legacy
Runtimes and does not change their Android settings, Docker networks, routes,
or host firewall. New provisioning completion creates direct revision 1 and
disabled/applied network state atomically with its Device and Runtime. Existing
provisioning history, including Device 03, is not rewritten. No real host proxy
bridge implementation is launched in Phase 3.

Provisioning is exposed internally through `POST /redroid-provisionings` and
`GET /redroid-provisionings/{provisioning_id}`. POST requires an
`Idempotency-Key`; retries reuse the same durable attempt and allocation. A
nonblocking `flock` file keyed by the provisioning UUID prevents multiple
backend processes on the same host from advancing one attempt simultaneously.
The short allocation lock remains database-backed (`BEGIN IMMEDIATE` on
SQLite), and neither lock is held while another request owns the attempt.

These endpoints control privileged Docker resources and are host-administration
capabilities. Keep the backend bound to a trusted/local interface and do not
publish the endpoint without administrator authentication and authorization.

## Managed deprovisioning

Provisioned devices must be removed with
`POST /redroid-provisionings/{provisioning_id}/deprovision`. Generic
`DELETE /devices/{id}` rejects provisioned managed devices; legacy Device 01/02
retain their existing unmanaged behavior and are never adopted automatically.

Deprovisioning uses the same cross-process attempt lock as provisioning. Before
the first state-changing action, it verifies the installation ID, provisioning
and ownership labels, recorded container/network IDs, exact Device/Runtime
mapping, derived allocation, and data ownership marker. Resource names are only
checked for conflicts and never authorize deletion. An ownership mismatch sets
`deprovision_failed` and preserves resources for manual recovery.

The Runtime-specific operation lock is also checked before removal. Active
automation or another Runtime mutation returns a busy conflict and is never
interrupted. Once the lock is owned, pending/retrying `device.*` Jobs for that
exact Runtime are cancelled with a durable `runtime_deprovisioned` log event;
Jobs are never redirected to another Runtime. Historical Jobs and JobLogs are
preserved after the Runtime foreign key is cleared.

The normal order is: close the tracked screen, stop a running container by its
verified ID, remove that stopped container by ID, remove the verified empty
dedicated network by ID, and atomically remove the active Device/Runtime rows.
Account and Job references follow their existing `SET NULL` semantics. The
provisioning row remains in `deprovisioned` state with historical Device and
Runtime IDs plus durable removal flags, so retries are idempotent and its device
number can never be allocated again.

The data directory and `.tiktok-manager-provisioning.json` marker are always
preserved by this workflow. Phase 6 intentionally provides no permanent-data
deletion option. A frontend action should therefore be offered only for a
device backed by a completed provisioning record, warn that the container and
network will be removed, and state clearly that persistent data is retained.

### Frontend registry recovery

The frontend keeps a convenience mapping from Device IDs to provisioning IDs in
browser `localStorage`; it is not an ownership authority. If that registry is
missing or cleared, the UI first attempts the ordinary Device delete. For a
provisioned managed Device, the backend rejects that request with `409 Conflict`
and includes the dedicated deprovision path containing the authoritative
provisioning ID. The frontend extracts that ID, fetches
`GET /redroid-provisionings/{provisioning_id}`, rebuilds its local registry from
the durable backend record, and directs the operator into the Deprovision flow.
No Docker resource is deleted by the rejected generic request.

## Device 03 API provisioning verification

Device 03 was provisioned through `POST /redroid-provisionings` on 2026-10-02
using the explicit operational database documented in `docs/database.md` and:

- installation ID `tiktok-manager-longnguyen-host-01`
- profile `android-12-redroid`
- base ADB port `5554`
- data root `/home/longnguyen/redroid-test`
- image `redroid/redroid@sha256:a6c464bbedcf1dcb67dbf91f329fbb19bee5b50631f0ca6bda6ed7c41b0e64e2`

Docker reported that exact value as both the installed image ID and RepoDigest.
The API allocated Device number 3, container `redroid-device-03`, ADB serial
`localhost:5557`, data directory `device-03-data`, and network
`redroid-device-03-net`. Pre-boot inspection confirmed the container had never
started, ADB was published only on `127.0.0.1:5557`, no Binder devices were
mapped, `/data` used the dedicated bind source, and restart/auto-remove were
disabled.

An identical idempotent replay returned the original completed attempt without
creating another resource. A changed request under the same key returned
`409 Conflict`. The first lifecycle-API boot reached ready in 5.699 seconds.
Subsequent stop/start, screen open/close, and persistence checks left all three
devices ready; Device 03 retained its Android ID, container ID, data path,
ownership labels, and marker hash.

## Device 02

Device 02 is defined in `deploy/redroid-devices.compose.yml` with:

- container `redroid-device-02`
- ADB `127.0.0.1:5556` mapped to container port `5555`
- persistent data `/home/longnguyen/redroid-test/device-02-data`
- network `redroid-device-02-net`
- immutable Redroid image digest matching Device 01
- restart policy `no` and no automatic removal
- TikTok Manager ownership labels

Run these commands from the repository root. `docker compose create` creates the
network and stopped container; it does not boot Android.

```bash
sudo install -d -m 0771 \
  -o longnguyen -g longnguyen \
  /home/longnguyen/redroid-test/device-02-data

docker compose -f deploy/redroid-devices.compose.yml config
docker compose -f deploy/redroid-devices.compose.yml create redroid-device-02
```

Inspect the stopped container before inserting its Runtime record:

```bash
docker inspect redroid-device-02
docker inspect -f '{{.State.Status}}' redroid-device-02
docker inspect -f '{{json .HostConfig.PortBindings}}' redroid-device-02
docker inspect -f '{{json .Mounts}}' redroid-device-02
docker inspect -f '{{json .NetworkSettings.Networks}}' redroid-device-02
docker inspect -f '{{json .Config.Labels}}' redroid-device-02
```

Expected state is `created`, with host port `127.0.0.1:5556`, only the Device 02
data directory mounted at `/data`, network `redroid-device-02-net`, and the
`com.tiktok-manager.managed=true` label. Do not use `docker compose up` during
foundation provisioning because it starts the container.

Register Device 02 only after inspection. The Device starts as `offline`; its
single Runtime starts as `stopped` with `last_seen_at=null`, container name
`redroid-device-02`, and ADB serial `localhost:5556`. Let the database allocate
both IDs.

## Verified isolation boundaries

The two-device layout was exercised on 2026-10-02 with both devices reporting
`sys.boot_completed=1`, ADB state `device`, and lifecycle state `ready`.

- Persistent storage is isolated by the two host bind sources. A unique file in
  each device's `/data/local/tmp` was visible only on that device, survived a
  lifecycle-managed stop/start of both containers with the same SHA-256 hash,
  and was removed after the test.
- External media is isolated with `/sdcard` backed by the device's own `/data`.
  Unique PNG markers were scanned through Android's media scanner and each
  device's MediaStore returned only its own marker. The files and their exact
  MediaStore rows were removed after the test; existing media was not changed.
- Android secure IDs were different (`d380cab10e53807f` for Device 01 and
  `428e67ef5438556a` for Device 02). Do not treat these observations as an API
  or mutate device identity as part of provisioning.
- Docker assigned different network namespaces and subnets: Device 01 used the
  default `bridge` network at `172.17.0.2/16`, while Device 02 used
  `redroid-device-02-net` at `172.18.0.2/16`. A temporary blackhole route for
  the documentation-only `198.51.100.0/24` range appeared only in Device 02;
  it was then removed. Device 01 remained booted and ADB-ready.
- A temporary Android HTTP proxy on Device 02 did not change Device 01's proxy
  setting. Clearing a proxy must delete `http_proxy` and the associated
  `global_http_proxy_host`, `global_http_proxy_port`, and
  `global_http_proxy_exclusion_list` keys to restore the prior state. No
  permanent proxy support is implemented by this provisioning definition.

Both containers resolved `example.com` and received an ICMP reply, confirming
DNS and outbound connectivity. Neither image exposed an HTTP client, so the
exercise did not establish the public source IP. Network namespace, interface,
address, route, gateway, and per-device proxy isolation were verified without
changing host routing.

## Final verified topology

| Device | Container | ADB endpoint | Persistent `/data` source | Network |
| --- | --- | --- | --- | --- |
| Device 01 | `redroid-device-01` | `localhost:5555` | `/home/longnguyen/redroid-test/device-01-data` | Docker default `bridge` |
| Device 02 | `redroid-device-02` | `localhost:5556` | `/home/longnguyen/redroid-test/device-02-data` | `redroid-device-02-net` |

Final manager lifecycle verification confirmed that a graceful shutdown with
`STOP_MANAGED_DEVICES_ON_SHUTDOWN=true` closes tracked screen sessions, stops
both managed containers, and reconciles both Runtime/Device pairs to
`stopped`/`offline` without deleting containers or data directories. The
shutdown loop continues after an individual stop failure, as covered by the
host lifecycle regression suite.

On the next manager startup, Docker, ADB, scrcpy, and Binder checks passed. The
manager inspected both stopped runtimes and left them stopped; it did not start
containers or open screens. Each device was then restored independently through
`DeviceLifecycleService`, and both returned to `ready`. The database contains
exactly one managed Runtime per Device, with unique container names and ADB
serials.
