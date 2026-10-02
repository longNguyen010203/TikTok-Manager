# Redroid Binder host bootstrap

Redroid requires the Ubuntu host's `binder_linux` module, the Binder device
endpoints, and a mounted Binder filesystem. TikTok Manager does not perform
privileged host repair. Install the supplied systemd oneshot service so Binder
is initialized during boot before Redroid is used.

The bootstrap only prepares Binder. It does not start Docker, TikTok Manager,
or any Redroid container, and it does not modify container data.

## Install

Run these commands from the repository root:

```bash
sudo install -m 0755 scripts/redroid-host-bootstrap.sh \
  /usr/local/sbin/redroid-host-bootstrap
sudo install -m 0644 deploy/redroid-binder.service \
  /etc/systemd/system/redroid-binder.service
sudo install -d -m 0755 /usr/local/share/tiktok-manager
sudo install -m 0644 docs/REDROID_HOST_BOOTSTRAP.md \
  /usr/local/share/tiktok-manager/REDROID_HOST_BOOTSTRAP.md
sudo systemctl daemon-reload
sudo systemctl enable --now redroid-binder.service
```

`enable --now` runs the idempotent bootstrap immediately and enables it for
future boots. If Binder is already correctly initialized, rerunning the service
leaves the existing mount in place.

## Verify

```bash
systemctl status redroid-binder.service
test -d /sys/module/binder_linux
findmnt --target /dev/binderfs
ls -l /dev/binderfs/binder /dev/binderfs/hwbinder /dev/binderfs/vndbinder
docker inspect -f '{{.State.Status}}' redroid-device-01
```

The service should show `active (exited)`, `/dev/binderfs` should have filesystem
type `binder`, and all three device endpoints should exist. The Redroid
container should remain `exited` unless it was explicitly started elsewhere.

## Reboot verification

```bash
sudo reboot
```

After reconnecting to the host:

```bash
systemctl is-active redroid-binder.service
systemctl status redroid-binder.service
test -d /sys/module/binder_linux
findmnt -n -o FSTYPE --target /dev/binderfs
ls -l /dev/binderfs/binder /dev/binderfs/hwbinder /dev/binderfs/vndbinder
docker inspect -f '{{.State.Status}}' redroid-device-01
```

Expected results are `active`, filesystem type `binder`, all endpoints present,
and `redroid-device-01` still `exited`. Docker may start normally during boot;
the Binder service neither starts nor stops the Docker daemon.

If TikTok Manager reports a Binder `HostDependencyError`, inspect the service:

```bash
journalctl -u redroid-binder.service -b --no-pager
sudo systemctl restart redroid-binder.service
```

Do not work around the error by granting the backend passwordless sudo. Repair
the host service instead.
