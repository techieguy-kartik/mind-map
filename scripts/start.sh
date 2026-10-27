#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo 'Run python3 -m venv .venv and .venv/bin/pip install -r requirements.lock first.'
  exit 1
fi
if [ ! -f dist/index.html ]; then
  echo 'Run npm ci and npm run build first.'
  exit 1
fi
exec .venv/bin/python -m server.start
