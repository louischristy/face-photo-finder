#!/bin/bash
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.11 or 3.12 is required. Install Python, then run this launcher again."
  read -n 1 -s -r -p "Press any key to close..."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: creating private Python environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/install_models.py
mkdir -p data/tokens
(sleep 2; open http://127.0.0.1:8765) &
echo "Face Photo Finder is running at http://127.0.0.1:8765"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
