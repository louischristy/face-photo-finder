#!/bin/bash
set -e
cd "$(dirname "$0")"

PYTHON=""
for candidate in python3.12 python3.11; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  echo "Face Photo Finder requires Python 3.11 or 3.12."
  echo "Your current python3 may be an older macOS Python and will not work."
  echo "Install Python 3.12 from python.org, then run this launcher again."
  exit 1
fi

PYTHON_VERSION="$($PYTHON -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
echo "Using $PYTHON (Python $PYTHON_VERSION)"

if [ -d .venv ]; then
  VENV_VERSION="$(.venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
  if [ "$VENV_VERSION" != "3.11" ] && [ "$VENV_VERSION" != "3.12" ]; then
    echo "Removing incompatible existing virtual environment (Python ${VENV_VERSION:-unknown})..."
    rm -rf .venv
  fi
fi

if [ ! -d .venv ]; then
  echo "Creating private Python environment..."
  "$PYTHON" -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python scripts/install_models.py
python scripts/smoke_face_engine.py
mkdir -p data/tokens
(sleep 2; open http://127.0.0.1:8765) &
echo "Face Photo Finder is running at http://127.0.0.1:8765"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
