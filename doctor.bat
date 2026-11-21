@echo off
rem Never-changing window: run the environment check and keep it visible.
setlocal
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
cd /d "%~dp0"
title lecture-forge - doctor

set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)

if not defined PY (
  echo.
  echo   [ERROR] Python not found on PATH.
  echo   Install Python 3.9+ from python.org, tick "Add to PATH", then retry.
  echo.
  pause
  exit /b 1
)

%PY% -m lecture_forge doctor
set RC=%errorlevel%

echo.
echo   ------------------------------------------------------------
echo   doctor exit code: %RC%
echo   If something says MISS, run the command printed under it.
pause
