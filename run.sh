#!/usr/bin/env bash
# Start SAINT on Linux. Extra arguments are passed through (e.g. ./run.sh --background).
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  source .venv/bin/activate
  exec .venv/bin/python app.py "$@"
fi
exec python3.12 app.py "$@"
