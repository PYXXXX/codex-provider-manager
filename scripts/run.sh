#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
PYTHON="$VENV/bin/python"
STAMP="$VENV/.cpm-installed"
NEEDS_INSTALL=0

valid_venv() {
  [ -x "$PYTHON" ] &&
  [ -f "$VENV/pyvenv.cfg" ] &&
  "$PYTHON" -c "import codex_provider_manager" >/dev/null 2>&1
}

if ! valid_venv; then
  NEEDS_INSTALL=1
  if [ -e "$VENV" ]; then
    rm -rf "$VENV" || {
      VENV="$ROOT/.venv-run"
      PYTHON="$VENV/bin/python"
      STAMP="$VENV/.cpm-installed"
      rm -rf "$VENV"
    }
  fi
  python3 -m venv "$VENV"
fi

if [ "$NEEDS_INSTALL" -eq 1 ] || [ ! -f "$STAMP" ]; then
  "$PYTHON" -m pip install -e "$ROOT"
  touch "$STAMP"
fi

if [ "$#" -eq 0 ]; then
  "$PYTHON" -m codex_provider_manager.cli tui
else
  "$PYTHON" -m codex_provider_manager.cli "$@"
fi
