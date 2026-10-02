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
