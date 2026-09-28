#!/usr/bin/env bash
# One process. Builds the UI if Node is available, then the API serves it.
# After the first build, Node is not required to open the app.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) PY="$ROOT/.venv/Scripts/python.exe" ;;
  *) PY="$ROOT/.venv/bin/python" ;;
esac
if [[ ! -x "$PY" && ! -f "$PY" ]]; then
  PY="python3"
fi

if command -v npm >/dev/null 2>&1; then
  echo "Building the UI..."
  (cd "$ROOT/frontend" && npm run build)
elif [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  echo "Node is not installed and frontend/dist is missing. Install Node 18+ once, run this script again, then later starts do not need Node."
  exit 1
fi

echo "Open http://127.0.0.1:8000"
exec "$PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
