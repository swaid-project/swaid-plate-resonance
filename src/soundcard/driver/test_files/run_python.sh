#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/trans.so" ]]; then
  echo "[run_python] trans.so not found, building it first..."
  make -C "$SCRIPT_DIR" trans.so
fi

exec python3 "$SCRIPT_DIR/test_hi.py" "$@"
