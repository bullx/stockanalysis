#!/usr/bin/env bash
# macOS, Linux, and Git Bash on Windows.
# Starts the API in the background and the UI in this terminal. Ctrl+C stops both.
# PowerShell on Windows cannot run this file. Use scripts/run.ps1 there.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  printf '%s\n' "$1"
  exit 1
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) VENV_PY="$ROOT/.venv/Scripts/python.exe" ;;
  *) VENV_PY="$ROOT/.venv/bin/python" ;;
esac

if [[ ! -f "$VENV_PY" || ! -d "$ROOT/frontend/node_modules" ]]; then
  fail "Run setup first:  bash scripts/setup.sh"
fi

dotenv() {
  local key="$1"
  local line val
  [[ -f "$ROOT/.env" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    line="${line#export }"
    if [[ "$line" =~ ^[[:space:]]*${key}=(.*)$ ]]; then
      val="${BASH_REMATCH[1]}"
      val="${val#"${val%%[![:space:]]*}"}"
      val="${val%"${val##*[![:space:]]}"}"
      if [[ ${#val} -ge 2 && ( "$val" == \"*\" || "$val" == \'*\' ) ]]; then
        val="${val:1:$((${#val} - 2))}"
      fi
      printf '%s' "$val"
      return 0
    fi
  done < "$ROOT/.env"
}

port_open() {
  "$VENV_PY" - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
sock.settimeout(0.4)
try:
    sock.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
else:
    sys.exit(0)
finally:
    sock.close()
PY
}

if port_open 8000 || port_open 5173; then
  fail "Port 8000 or 5173 is already in use. Stop that process, or open http://localhost:5173 if this app is already running."
fi

PROVIDER="$(dotenv LLM_PROVIDER)"
MODEL="$(dotenv LLM_MODEL)"
API_KEY="$(dotenv LLM_API_KEY)"
PROVIDER="${PROVIDER:-ollama}"
MODEL="${MODEL:-llama3.1:8b}"
PROVIDER_LC="$(printf '%s' "$PROVIDER" | tr '[:upper:]' '[:lower:]')"

case "$PROVIDER_LC" in
  ollama|lmstudio|llamacpp|jan|llamafile|mock) ;;
  *)
    if [[ -z "$API_KEY" ]]; then
      fail "LLM_PROVIDER=$PROVIDER needs LLM_API_KEY in .env. Save the file, then run this script again."
    fi
    ;;
esac

if [[ "$PROVIDER_LC" == "ollama" ]]; then
  set +e
  "$VENV_PY" - "$MODEL" <<'PY'
import sys, urllib.request
model = sys.argv[1]
try:
    with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as resp:
        body = resp.read().decode()
except Exception:
    raise SystemExit(2)
if model not in body:
    raise SystemExit(3)
raise SystemExit(0)
PY
  ollama_status=$?
  set -e
  if [[ "$ollama_status" -eq 2 ]]; then
    fail "Ollama is not answering on port 11434. Install it from https://ollama.com, run 'ollama pull $MODEL', and start the Ollama app. If that app is already open, do not also run 'ollama serve'."
  fi
  if [[ "$ollama_status" -eq 3 ]]; then
    fail "Ollama is up, and $MODEL is not pulled. Run:  ollama pull $MODEL"
  fi
  if [[ "$ollama_status" -ne 0 ]]; then
    exit "$ollama_status"
  fi
fi

API_PID=""
cleanup() {
  if [[ -n "$API_PID" ]]; then
    kill -TERM -"$API_PID" 2>/dev/null || kill -TERM "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

set -m || true
"$VENV_PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!
sleep 1
if ! kill -0 "$API_PID" 2>/dev/null; then
  fail "The API failed to start."
fi

printf '%s\n' "API  http://127.0.0.1:8000/api/health"
printf '%s\n' "UI   http://localhost:5173"
printf '%s\n' "Ctrl+C stops both. After you edit .env, stop and run this script again."

cd "$ROOT/frontend"
npm run dev
