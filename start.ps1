#!/usr/bin/env pwsh
# 一条命令起本地服务（讲义 + 速答框 + 独立提问页）。
# 用法：./start.ps1            （默认读 config.json，站点目录 site）
#      ./start.ps1 -Site site  （指定站点目录）
param(
  [string]$Site = ""
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

if ($Site) { $env:LF_SITE = $Site }

$py = "python"
if (Test-Path ".\.venv\Scripts\python.exe") { $py = ".\.venv\Scripts\python.exe" }

if (-not (Test-Path ".\site\index.html")) {
  Write-Host "还没有 site/，先用示例讲义构建一次：" -ForegroundColor Yellow
  & $py -m lecture_forge build .\examples\demo-lecture -o site
}

Write-Host "笔记：在 config.json 里填 model.api_key 就能问任意问题（不填则只查问答库）" -ForegroundColor DarkGray
& $py -m lecture_forge serve
