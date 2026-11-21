@echo off
rem ---------------------------------------------------------------
rem  One-click launcher for Windows (double-click this file).
rem  Kept ASCII-only on purpose: a .bat with Chinese text inside
rem  if(...) blocks gets mangled by cmd.exe's OEM codepage.
rem  For Chinese prompts use start.ps1 instead.
rem ---------------------------------------------------------------
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

if not exist "site\index.html" (
  echo No site\ folder yet - building the bundled demo lecture first...
  %PY% -m lecture_forge build examples\demo-lecture -o site
)

echo.
echo   Lecture + ask box:  http://127.0.0.1:8765
echo   Put model.api_key into config.json to ask anything.
echo   Leave it empty to use the offline QA bank only.
echo.

%PY% -m lecture_forge serve
pause
