@echo off
rem One-time setup: Python environment + packages + the 2.3 GB model. Safe to run again (it continues where it stopped).
setlocal
cd /d "%~dp0"
echo === Cohere Transcribe Arabic (local) - setup ===
echo.
set "PY="
where py >nul 2>nul && py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.10 or newer was not found.
  echo Install it from https://www.python.org/downloads/ - tick "Add python.exe to PATH" - then run setup.cmd again.
  goto :fail
)
if not exist "venv\Scripts\python.exe" (
  echo [1/3] Creating the Python environment...
  %PY% -m venv venv || goto :fail
) else (
  echo [1/3] Python environment already exists.
)
echo [2/3] Installing packages...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto :fail
echo [3/3] Getting the model (about 2.3 GB)...
"venv\Scripts\python.exe" download_model.py || goto :fail
echo.
echo Setup finished. Double-click start-server.cmd, then open http://127.0.0.1:8790/ in your browser.
if not defined NOPAUSE pause
exit /b 0

:fail
echo.
echo Setup did not finish - see the messages above. Run setup.cmd again to continue.
if not defined NOPAUSE pause
exit /b 1
