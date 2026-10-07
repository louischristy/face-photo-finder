#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -e .
(sleep 2; open http://127.0.0.1:8765) &
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
