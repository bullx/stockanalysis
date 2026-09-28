#!/usr/bin/env bash
# macOS, Linux, and Git Bash on Windows.
# PowerShell on Windows cannot run this file. Use scripts/setup.ps1 there.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  printf '%s\n' "$1"
  exit 1
}

pick_python() {
  if command -v python3.11 >/dev/null 2>&1 && python3.11 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON=(python3.11)
    return
  fi
  if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON=(python3)
    return
  fi
  if command -v py >/dev/null 2>&1 && py -3.11 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
    PYTHON=(py -3.11)
    return
  fi
  fail "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/"
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PY="$ROOT/.venv/Scripts/python.exe" ;;
  *) VENV_PY="$ROOT/.venv/bin/python" ;;
esac

pick_python

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  fail "Node.js 18 or newer is required. Install it from https://nodejs.org/"
fi
NODE_MAJOR="$(node -v | sed 's/^v//' | cut -d. -f1)"
if [[ "$NODE_MAJOR" -lt 18 ]]; then
  fail "Node.js $(node -v) is installed. This app needs 18 or newer."
fi

if [[ ! -f "$VENV_PY" ]]; then
  if [[ -d "$ROOT/.venv" ]]; then
    fail "The .venv folder exists but its Python is missing. Delete .venv and run setup again."
  fi
  printf '%s\n' "Creating .venv"
  "${PYTHON[@]}" -m venv "$ROOT/.venv"
fi

printf '%s\n' "Installing Python packages"
"$VENV_PY" -m pip install -r "$ROOT/backend/requirements.txt"

printf '%s\n' "Installing frontend packages"
(
  cd "$ROOT/frontend"
  npm install
)

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  printf '%s\n' "Created .env from .env.example"
else
  printf '%s\n' ".env already exists. Left it unchanged."
fi

printf '\n%s\n' "Setup finished."
printf '%s\n' "Start the app with:  bash scripts/run.sh"
printf '%s\n' "The default is Ollama and llama3.1:8b. To click through the UI with no model, set LLM_PROVIDER=mock and LLM_MODEL=mock in .env."
