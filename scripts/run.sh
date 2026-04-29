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

editable_install() {
  valid_venv &&
  "$PYTHON" - "$ROOT" <<'PY' >/dev/null 2>&1
from pathlib import Path
import sys
import codex_provider_manager
root = Path(sys.argv[1]).resolve()
actual = Path(codex_provider_manager.__file__).resolve().parent
expected = root / "src" / "codex_provider_manager"
raise SystemExit(0 if actual == expected else 1)
PY
}

install_fresh() {
  [ -f "$STAMP" ] || return 1
  newest="$(find "$ROOT/src" -type f -name '*.py' -newer "$STAMP" -print -quit)"
  [ -z "$newest" ] || return 1
  [ ! "$ROOT/pyproject.toml" -nt "$STAMP" ]
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

if [ "$NEEDS_INSTALL" -eq 1 ] || ! editable_install || ! install_fresh; then
  "$PYTHON" -m pip install -e "$ROOT"
  touch "$STAMP"
fi

if [ "$#" -eq 0 ]; then
  "$PYTHON" -m codex_provider_manager.cli tui
else
  "$PYTHON" -m codex_provider_manager.cli "$@"
fi
