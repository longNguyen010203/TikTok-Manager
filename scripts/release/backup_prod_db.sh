#!/usr/bin/env bash
set -euo pipefail

if [[ "${TIKTOK_MANAGER_ENV:-}" != "production" ]]; then
  echo "error: set TIKTOK_MANAGER_ENV=production explicitly" >&2
  exit 2
fi

production_root="${TIKTOK_MANAGER_PRODUCTION_ROOT:-${HOME}/Desktop/MMO/TikTok-Manager-prod}"
python_path="${production_root}/backend/.venv/bin/python"
if [[ ! -x "${python_path}" ]]; then
  echo "error: production Python is missing: ${python_path}" >&2
  exit 2
fi

cd "${production_root}/backend"
exec "${python_path}" -m app.production_backup
