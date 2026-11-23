' Starts the Cohere Arabic speech-to-text server with no window (output goes to server.log).
' Used by autostart-on.cmd. To stop it: Task Manager > Details > end the python.exe that runs server.py.
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "cmd /c cd /d """ & here & """ && ""venv\Scripts\python.exe"" server.py >> server.log 2>&1", 0, False
