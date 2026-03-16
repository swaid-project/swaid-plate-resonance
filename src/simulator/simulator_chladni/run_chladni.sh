#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: Python executable '$PYTHON_BIN' was not found."
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating virtual environment in $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "Error: pip install is allowed only inside an active virtual environment."
  exit 1
fi

if ! python -c "import numpy, scipy, matplotlib" >/dev/null 2>&1; then
  echo "Installing dependencies from $SCRIPT_DIR/requirements.txt ..."
  if ! python -m pip --version >/dev/null 2>&1; then
    echo "pip is broken or missing. Repairing with ensurepip ..."
    python -m ensurepip --upgrade
  fi
  python -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

if [[ "${1:-}" == "--check" ]]; then
  echo "Environment check OK. Dependencies are installed."
  exit 0
fi

cd "$REPO_ROOT/src"
python -m simulator.simulator_chladni "$@"
