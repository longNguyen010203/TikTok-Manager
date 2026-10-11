#!/usr/bin/env bash
set -euo pipefail

case "${TIKTOK_MANAGER_ENV:-}" in
  production) port=8000 ;;
  development) port=8001 ;;
  *) echo "error: TIKTOK_MANAGER_ENV must be production or development" >&2; exit 2 ;;
esac

curl --fail --silent --show-error --max-time 10 \
  "http://127.0.0.1:${port}/health"
printf '\n'
