@echo off
rem ===================================================================
rem  lecture-forge  launcher (Windows)
rem  Double-click this file.  If the window flashes and closes, the
rem  reason is printed below - this file always pauses at the end.
rem ===================================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0"
title lecture-forge

echo.
echo   lecture-forge
echo   ------------------------------------------------------------
echo   current folder: %CD%
echo.

rem --- 1) find a python we can actually use -------------------------
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo   [ERROR] Python not found on PATH.
  echo.
  echo   Install Python 3.9+ from python.org and tick
  echo   "Add python.exe to PATH", then double-click this file again.
  goto :end
)

echo   python: %PY%
%PY% -c "import sys;print('   version:',sys.version.split()[0],'|',sys.executable)" 2>nul
if errorlevel 1 (
  echo   [ERROR] that python cannot even run. Try: py -3 --version
  goto :end
)

rem --- 2) the only hard requirement (stage build/serve) -------------
%PY% -c "import markdown" >nul 2>&1
if errorlevel 1 (
  echo.
  echo   [ERROR] missing package: markdown
  echo   fix it with:   %PY% -m pip install -r requirements.txt
  goto :end
)

rem --- 3) first run: build the bundled demo ------------------------
if not exist "site\index.html" (
  echo.
  echo   no site\ yet - building the bundled demo lecture...
  %PY% -m lecture_forge build examples\demo-lecture -o site
  if errorlevel 1 (
    echo   [ERROR] build failed. Run:  python -m lecture_forge doctor
    goto :end
  )
)

echo.
echo   open  http://127.0.0.1:8765   in your browser
echo   close this window to stop the server
echo.
if not defined LF_NO_BROWSER start "" http://127.0.0.1:8765

%PY% -m lecture_forge serve
echo.
echo   server stopped with exit code %errorlevel%

:end
echo.
echo   ------------------------------------------------------------
echo   this window stays open so you can read the message above.
pause
