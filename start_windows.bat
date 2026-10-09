@echo off
setlocal
cd /d %~dp0

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or 3.12 is required. Install Python with the Python Launcher, then run this file again.
  pause
  exit /b 1
)

if not exist .venv (
  echo First run: creating private Python environment...
  py -3 -m venv .venv
)
call .venv\Scripts\activate.bat
if errorlevel 1 goto :error
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -e .
if errorlevel 1 goto :error
python scripts\install_models.py
if errorlevel 1 goto :error
if not exist data\tokens mkdir data\tokens
start "" http://127.0.0.1:8765
echo Face Photo Finder is running at http://127.0.0.1:8765
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
goto :eof

:error
echo.
echo Setup failed. Review the error above, then try again.
pause
exit /b 1
