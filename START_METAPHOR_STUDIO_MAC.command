#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
BACKGROUND=0
if [ "${1:-}" = "--background" ]; then
  BACKGROUND=1
fi

export MAS_WORKSPACE="$ROOT"
export PYTHONPATH="$ROOT/src"
export PYTHONUTF8=1
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

notify_error() {
  local message="$1"
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display dialog \"${message}\" buttons {\"OK\"} default button \"OK\" with title \"Metaphor Agreement Studio\"" >/dev/null 2>&1 || true
  else
    echo "$message"
  fi
}

find_python() {
  for candidate in \
    python3.12 python3.11 python3.13 python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.13 /usr/local/bin/python3 \
    /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3; do
    if [[ "$candidate" = /* ]]; then
      [ -x "$candidate" ] || continue
    else
      command -v "$candidate" >/dev/null 2>&1 || continue
    fi
    if "$candidate" -c 'import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)' >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PY_CMD="$(find_python || true)"
if [ ! -x ".venv/bin/python" ]; then
  if [ -z "$PY_CMD" ]; then
    notify_error "Python 3.12 is required for the first setup. Install Python 3.12 from python.org, then open Metaphor Agreement Studio again."
    exit 1
  fi
  if [ "$BACKGROUND" -eq 1 ] && command -v osascript >/dev/null 2>&1; then
    osascript -e 'display dialog "First-time setup will prepare a private Python environment. This can take a few minutes and requires an internet connection." buttons {"Continue"} default button "Continue" with title "Metaphor Agreement Studio"' >/dev/null 2>&1 || exit 1
  else
    echo ""
    echo "============================================================"
    echo "  Metaphor Agreement Studio - First-time setup"
    echo "============================================================"
    echo "A private Python environment will be created in this folder."
    echo "The original research workbook will not be modified."
  fi
  "$PY_CMD" -m venv .venv || { notify_error "The private Python environment could not be created."; exit 1; }
  .venv/bin/python -m pip install --disable-pip-version-check --upgrade pip >/dev/null || { notify_error "Python setup could not be completed. Check your internet connection and try again."; exit 1; }
fi

if ! .venv/bin/python -c 'import streamlit, openpyxl, pandas, numpy, scipy, statsmodels, sklearn, plotly, matplotlib, jinja2, reportlab' >/dev/null 2>&1; then
  if [ "$BACKGROUND" -eq 0 ]; then
    echo "Installing or updating Release 1.0 requirements..."
  fi
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements-release.txt >/dev/null || { notify_error "Application requirements could not be installed. Check your internet connection and try again."; exit 1; }
fi

PORT="$(.venv/bin/python -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")"
printf '%s\n' "$PORT" > .mas_streamlit.port
URL="http://127.0.0.1:${PORT}"

if [ "$BACKGROUND" -eq 1 ]; then
  nohup .venv/bin/python -m streamlit run app.py --server.port "$PORT" --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false > .mas_streamlit.log 2>&1 &
  PID=$!
  printf '%s\n' "$PID" > .mas_streamlit.pid
  READY=0
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if .venv/bin/python -c "import socket; s=socket.socket(); s.settimeout(.2); raise SystemExit(0 if s.connect_ex(('127.0.0.1', int('$PORT'))) == 0 else 1)" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 0.5
  done
  if [ "$READY" -ne 1 ]; then
    notify_error "Metaphor Agreement Studio did not start. Open .mas_streamlit.log in the application folder for technical details."
    exit 1
  fi
  open "$URL"
  exit 0
fi

echo ""
echo "============================================================"
echo "  Metaphor Agreement Studio - Release 1.0"
echo "============================================================"
echo ""
echo "The application will open in your web browser."
echo "Keep this window open while you use the application."
echo "You can also stop it with STOP_METAPHOR_STUDIO_MAC.command."
echo ""
echo "Local address: $URL"
echo ""
open "$URL"
.venv/bin/python -m streamlit run app.py --server.port "$PORT" --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
STATUS=$?
rm -f .mas_streamlit.port .mas_streamlit.pid
exit "$STATUS"
