@echo off
setlocal

if "%RCBT_API_KEY%"=="" (
  echo [ERROR] RCBT_API_KEY is not set.
  echo Set it first in this terminal:
  echo   set RCBT_API_KEY=YOUR_API_KEY
  exit /b 1
)

python scripts\realtime_worker.py %*
