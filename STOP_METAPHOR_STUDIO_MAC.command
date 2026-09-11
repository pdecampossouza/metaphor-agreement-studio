#!/bin/bash
set -u
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

STOPPED=0
if [ -f .mas_streamlit.pid ]; then
  PID="$(cat .mas_streamlit.pid 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID" >/dev/null 2>&1 || true
    STOPPED=1
  fi
fi

if [ "$STOPPED" -eq 0 ] && [ -f .mas_streamlit.port ] && command -v lsof >/dev/null 2>&1; then
  PORT="$(cat .mas_streamlit.port 2>/dev/null || true)"
  if [ -n "$PORT" ]; then
    PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
    if [ -n "$PIDS" ]; then
      kill $PIDS >/dev/null 2>&1 || true
      STOPPED=1
    fi
  fi
fi

rm -f .mas_streamlit.pid .mas_streamlit.port
if [ "$STOPPED" -eq 1 ]; then
  echo "Metaphor Agreement Studio stopped."
else
  echo "No running Metaphor Agreement Studio process was found."
fi
sleep 1
