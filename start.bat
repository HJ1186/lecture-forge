@echo off
rem ===================================================================
rem  lecture-forge launcher (Windows)  -  CRLF, ASCII only, always pauses
rem  Every pre-flight step is also written to start-log.txt so that a
rem  window that still flashes leaves behind something to read.
rem ===================================================================
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0"
title lecture-forge

set "LOG=%~dp0start-log.txt"
> "%LOG%" echo lecture-forge launcher log
>>"%LOG%" echo.
>>"%LOG%" echo time : %DATE% %TIME%
>>"%LOG%" echo folder: %CD%
>>"%LOG%" echo script: %~f0

call :prep >> "%LOG%" 2>&1
set "RC=%errorlevel%"
type "%LOG%"
echo.
if not "%RC%"=="0" goto :end

if not defined LF_NO_BROWSER (
  echo   opening http://127.0.0.1:8765 in your browser...
  start "" http://127.0.0.1:8765
)
echo   serving. close this window to stop.
echo.
%PY% -m lecture_forge serve
echo.
echo   server stopped, exit code %errorlevel%

:end
echo.
echo   ------------------------------------------------------------
echo   log written to: %LOG%
echo   if the problem is not obvious, send that file along.
echo.
pause
exit /b

rem -------------------------------------------------------------------
rem  pre-flight: find python, check the one required package, build once
rem  success = exit 0 ; failure = exit 1
rem -------------------------------------------------------------------
:prep
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo [FAIL] Python not found on PATH.
  echo        Install Python 3.9+ from python.org and tick "Add to PATH".
  exit /b 1
)
echo python: %PY%
%PY% -c "import sys;print(' version:',sys.version.split()[0]);print(' exe    :',sys.executable)"
if errorlevel 1 (
  echo [FAIL] that python cannot run. Try: py -3 --version
  exit /b 1
)
%PY% -c "import markdown" >nul 2>&1
if errorlevel 1 (
  echo [FAIL] missing package: markdown
  echo        fix: %PY% -m pip install -r requirements.txt
  exit /b 1
)
if exist "site\index.html" exit /b 0
echo building the bundled demo lecture...
%PY% -m lecture_forge build examples\demo-lecture -o site
if errorlevel 1 (
  echo [FAIL] build failed, run: %PY% -m lecture_forge doctor
  exit /b 1
)
exit /b 0
