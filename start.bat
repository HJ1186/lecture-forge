@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

if not exist "site\index.html" (
  echo 还没有 site\，先用示例讲义构建一次...
  %PY% -m lecture_forge build examples\demo-lecture -o site
)

echo 笔记：在 config.json 里填 model.api_key 就能问任意问题（不填则只查问答库）
%PY% -m lecture_forge serve
pause
