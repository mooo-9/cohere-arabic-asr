@echo off
rem Stops the server from starting at login (does not stop one that is already running).
powershell -NoProfile -Command "Remove-Item -LiteralPath ([Environment]::GetFolderPath('Startup')+'\Cohere Arabic ASR.lnk') -ErrorAction SilentlyContinue"
echo Auto-start is off.
pause
