#!/usr/bin/env bash
set -euo pipefail

production_root="${TIKTOK_MANAGER_PRODUCTION_ROOT:-${HOME}/Desktop/MMO/TikTok-Manager-prod}"
if [[ ! -d "${production_root}/.git" && ! -f "${production_root}/.git" ]]; then
  echo "error: production worktree is missing: ${production_root}" >&2
  exit 2
fi

tag="$(git -C "${production_root}" describe --tags --exact-match HEAD 2>/dev/null || true)"
if [[ -z "${tag}" ]]; then
  echo "error: production worktree HEAD is not an exact release tag" >&2
  exit 1
fi
if [[ -n "$(git -C "${production_root}" status --porcelain)" ]]; then
  echo "error: production worktree is not clean" >&2
  exit 1
fi
printf 'release=%s\ncommit=%s\n' "${tag}" "$(git -C "${production_root}" rev-parse HEAD)"
