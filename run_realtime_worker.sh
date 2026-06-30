#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${RCBT_API_KEY:-}" ]]; then
  echo "[ERROR] RCBT_API_KEY is not set."
  echo "Set it first in this shell:"
  echo "  export RCBT_API_KEY=YOUR_API_KEY"
  exit 1
fi

python scripts/realtime_worker.py "$@"
