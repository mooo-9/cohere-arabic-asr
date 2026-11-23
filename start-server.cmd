@echo off
rem Starts the Cohere Arabic speech-to-text server in this window. Close the window to stop it.
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Run setup.cmd first.
  pause
  exit /b 1
)
if not defined PORT set PORT=8790
echo Cohere Transcribe Arabic is running.
echo   Try it in the browser:  http://127.0.0.1:%PORT%/
echo   API base URL for apps:  http://127.0.0.1:%PORT%/v1
echo Close this window to stop the server.
echo.
"venv\Scripts\python.exe" server.py
pause
