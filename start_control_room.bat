@echo off
setlocal
cd /d "%~dp0"

set "PYEXE=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python 3 and rerun this launcher.
    pause
    exit /b 1
  )
  set "PYEXE=py -3"
)

start "" http://localhost:8000/index.html
%PYEXE% scripts\dev_server.py

endlocal
