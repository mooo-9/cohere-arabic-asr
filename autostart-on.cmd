@echo off
rem Makes the server start hidden every time you log in to Windows, and starts it now.
cd /d "%~dp0"
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Cohere Arabic ASR.lnk'); $s.TargetPath='wscript.exe'; $s.Arguments='\"%~dp0start-hidden.vbs\"'; $s.WorkingDirectory='%~dp0'; $s.Save()"
wscript.exe "%~dp0start-hidden.vbs"
echo Auto-start is on. The server is starting in the background: http://127.0.0.1:8790/
pause
