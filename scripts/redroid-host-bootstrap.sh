#!/usr/bin/env bash

set -Eeuo pipefail

readonly BINDERFS_MOUNT_POINT="/dev/binderfs"
readonly BINDER_DEVICES=(
    "/dev/binderfs/binder"
    "/dev/binderfs/hwbinder"
    "/dev/binderfs/vndbinder"
)

log() {
    printf '[redroid-host-bootstrap] %s\n' "$*"
}

fail() {
    printf '[redroid-host-bootstrap] ERROR: %s\n' "$*" >&2
    exit 1
}

on_error() {
    local exit_code=$?
    printf '[redroid-host-bootstrap] ERROR: command failed at line %s (exit %s)\n' \
        "${BASH_LINENO[0]}" "${exit_code}" >&2
    exit "${exit_code}"
}

trap on_error ERR

if [[ "${EUID}" -ne 0 ]]; then
    fail "must run as root"
fi

for command_name in modprobe mount mountpoint findmnt install; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done

log "loading binder_linux with binder,hwbinder,vndbinder devices"
modprobe binder_linux devices=binder,hwbinder,vndbinder

[[ -d /sys/module/binder_linux ]] \
    || fail "binder_linux did not load; check kernel module availability"

install -d -m 0755 "${BINDERFS_MOUNT_POINT}"

if mountpoint -q "${BINDERFS_MOUNT_POINT}"; then
    mounted_type="$(findmnt -n -o FSTYPE --target "${BINDERFS_MOUNT_POINT}")"
    [[ "${mounted_type}" == "binder" ]] \
        || fail "${BINDERFS_MOUNT_POINT} is already mounted as ${mounted_type}, not binder"
    log "binderfs is already mounted at ${BINDERFS_MOUNT_POINT}"
else
    log "mounting binderfs at ${BINDERFS_MOUNT_POINT}"
    mount -t binder binder "${BINDERFS_MOUNT_POINT}"
fi

for endpoint in "${BINDER_DEVICES[@]}"; do
    [[ -e "${endpoint}" ]] \
        || fail "Binder endpoint is missing after module load: ${endpoint}"
done

mounted_type="$(findmnt -n -o FSTYPE --target "${BINDERFS_MOUNT_POINT}")"
[[ "${mounted_type}" == "binder" ]] \
    || fail "Binder filesystem verification failed at ${BINDERFS_MOUNT_POINT}"

log "Binder host initialization is ready"
