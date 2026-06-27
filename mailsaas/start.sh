#!/usr/bin/env bash
# ============================================================
#  MailSaaS - one-click start for macOS / Linux
#  Run with:  ./start.sh      (or: bash start.sh)
# ============================================================
set -e
cd "$(dirname "$0")"

echo
echo "  =============================================="
echo "    MailSaaS - starting up..."
echo "  =============================================="
echo

# Pick a Python interpreter (python3 preferred).
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "  [ERROR] Python was not found."
  echo "  Install Python 3.8+ from https://python.org/downloads"
  echo "  (macOS: 'brew install python', Debian/Ubuntu: 'sudo apt install python3 python3-pip')"
  exit 1
fi

echo "  Using Python: $($PY --version)"
echo "  Installing dependencies (first run only)..."
$PY -m pip install -r requirements.txt

PORT="${PORT:-5005}"
URL="http://127.0.0.1:${PORT}"

# Try to open a browser (best effort; ignore if unavailable).
( sleep 2
  if command -v open    >/dev/null 2>&1; then open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$URL"
  fi ) >/dev/null 2>&1 &

echo
echo "  Server starting at ${URL}  (press Ctrl+C to stop)"
echo
PORT="$PORT" $PY run.py
