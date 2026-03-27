#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

cleanup() {
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

export SENTINEL_FRONTEND_PORT="${SENTINEL_FRONTEND_PORT:-8010}"
export SENTINEL_UI_RELOAD="${SENTINEL_UI_RELOAD:-1}"
export WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-true}"

PYTHONPATH=src uvicorn sentinel_alpha.api.app:app --host 127.0.0.1 --port 8001 --reload --reload-dir src &
PYTHONPATH=src python -m sentinel_alpha.nicegui.app
