#!/usr/bin/env bash
set -euo pipefail

# Installation always targets the authoritative local database, even if this
# shell was previously used for an isolated development database.
unset DATABASE_URL
export TIKTOK_MANAGER_RUNTIME_MODE=production

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_dir="${project_root}/backend"
venv_dir="${backend_dir}/.venv"
config_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/tiktok-manager"
data_dir="${XDG_DATA_HOME:-${HOME}/.local/share}/tiktok-manager"
database_path="${data_dir}/tiktok_manager.db"
unit_dir="${XDG_CONFIG_HOME:-${HOME}/.config}/systemd/user"
backend_unit_path="${unit_dir}/tiktok-manager-backend.service"
worker_unit_path="${unit_dir}/tiktok-manager-worker.service"
workflow_unit_path="${unit_dir}/tiktok-manager-workflow-orchestrator.service"
cleanup_service_path="${unit_dir}/tiktok-manager-artifact-cleanup.service"
cleanup_timer_path="${unit_dir}/tiktok-manager-artifact-cleanup.timer"
content_cleanup_service_path="${unit_dir}/tiktok-manager-content-cleanup.service"
content_cleanup_timer_path="${unit_dir}/tiktok-manager-content-cleanup.timer"
user_runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if [[ ! -S "${user_runtime_dir}/bus" ]]; then
  echo "User systemd bus is unavailable at ${user_runtime_dir}/bus" >&2
  exit 1
fi
export XDG_RUNTIME_DIR="${user_runtime_dir}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${user_runtime_dir}/bus}"

mkdir -p "${config_dir}" "${data_dir}" "${unit_dir}"
chmod 700 "${config_dir}" "${data_dir}"

if [[ ! -x "${venv_dir}/bin/python" ]]; then
  python3 -m venv "${venv_dir}"
fi
"${venv_dir}/bin/pip" install --editable "${backend_dir}"

(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -m app.bootstrap
)

configured_ffprobe="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().content_ffprobe_path)'
)"
if [[ "${configured_ffprobe}" != /* || ! -f "${configured_ffprobe}" || \
      -L "${configured_ffprobe}" || ! -x "${configured_ffprobe}" ]]; then
  echo "Configured ffprobe is missing or unsafe: ${configured_ffprobe}" >&2
  echo "Install ffmpeg/ffprobe and configure an absolute trusted executable path." >&2
  exit 1
fi
configured_ffmpeg="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().content_ffmpeg_path)'
)"
if [[ "${configured_ffmpeg}" != /* || ! -f "${configured_ffmpeg}" || \
      -L "${configured_ffmpeg}" || ! -x "${configured_ffmpeg}" ]]; then
  echo "Configured ffmpeg is missing or unsafe: ${configured_ffmpeg}" >&2
  exit 1
fi

configured_aapt2="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().managed_app_aapt2_path)'
)"
configured_apksigner="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().managed_app_apksigner_path)'
)"
for apk_tool in "${configured_aapt2}" "${configured_apksigner}"; do
  if [[ "${apk_tool}" != /* || ! -f "${apk_tool}" || -L "${apk_tool}" || ! -x "${apk_tool}" ]]; then
    echo "Managed APK inspection tool is missing or unsafe: ${apk_tool}" >&2
    echo "Managed APK inspection will remain unavailable until a trusted absolute tool path is configured." >&2
  fi
done

if [[ -f "${database_path}" ]]; then
  backup_dir="${data_dir}/backups"
  mkdir -p "${backup_dir}"
  chmod 700 "${backup_dir}"
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  cp --preserve=mode,timestamps "${database_path}" \
    "${backup_dir}/tiktok_manager.pre-install-${timestamp}.db"
  "${venv_dir}/bin/python" -c \
    'import sqlite3,sys; value=sqlite3.connect(sys.argv[1]).execute("PRAGMA integrity_check").fetchone()[0]; print("integrity="+value); raise SystemExit(value != "ok")' \
    "${database_path}"
fi

(
  cd "${backend_dir}"
  "${venv_dir}/bin/alembic" upgrade head
  "${venv_dir}/bin/python" -m app.bootstrap --ensure-key
)

escaped_root="${project_root//&/\\&}"
sed "s|@PROJECT_ROOT@|${escaped_root}|g" \
  "${project_root}/deploy/tiktok-manager-backend.service" > "${backend_unit_path}"
sed "s|@PROJECT_ROOT@|${escaped_root}|g" \
  "${project_root}/deploy/tiktok-manager-worker.service" > "${worker_unit_path}"
sed "s|@PROJECT_ROOT@|${escaped_root}|g" \
  "${project_root}/deploy/tiktok-manager-workflow-orchestrator.service" > "${workflow_unit_path}"
sed "s|@PROJECT_ROOT@|${escaped_root}|g" \
  "${project_root}/deploy/tiktok-manager-artifact-cleanup.service" \
  > "${cleanup_service_path}"
cleanup_interval="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().artifact_cleanup_interval_hours)'
)"
sed "s|@CLEANUP_INTERVAL@|${cleanup_interval}|g" \
  "${project_root}/deploy/tiktok-manager-artifact-cleanup.timer" \
  > "${cleanup_timer_path}"
sed "s|@PROJECT_ROOT@|${escaped_root}|g" \
  "${project_root}/deploy/tiktok-manager-content-cleanup.service" \
  > "${content_cleanup_service_path}"
content_cleanup_interval="$(
  cd "${backend_dir}"
  "${venv_dir}/bin/python" -c \
    'from app.config import load_application_config; print(load_application_config().content_cleanup_interval_hours)'
)"
sed "s|@CONTENT_CLEANUP_INTERVAL@|${content_cleanup_interval}|g" \
  "${project_root}/deploy/tiktok-manager-content-cleanup.timer" \
  > "${content_cleanup_timer_path}"
chmod 600 "${backend_unit_path}" "${worker_unit_path}" "${workflow_unit_path}" \
  "${cleanup_service_path}" "${cleanup_timer_path}" \
  "${content_cleanup_service_path}" "${content_cleanup_timer_path}"

systemctl --user daemon-reload
systemctl --user enable --now tiktok-manager-backend.service
systemctl --user enable --now tiktok-manager-worker.service
systemctl --user enable --now tiktok-manager-workflow-orchestrator.service
systemctl --user enable --now tiktok-manager-artifact-cleanup.timer
systemctl --user enable --now tiktok-manager-content-cleanup.timer
systemctl --user --no-pager status tiktok-manager-backend.service
systemctl --user --no-pager status tiktok-manager-worker.service
systemctl --user --no-pager status tiktok-manager-workflow-orchestrator.service
systemctl --user --no-pager status tiktok-manager-artifact-cleanup.timer
systemctl --user --no-pager status tiktok-manager-content-cleanup.timer
