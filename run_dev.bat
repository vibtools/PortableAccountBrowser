@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Project-local .venv was not found.
  echo Run setup_dev.bat first.
  pause
  exit /b 1
)

if not exist "runtime\chromium\chrome.exe" (
  echo Portable Chromium was not found.
  echo Run setup_dev.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" app.py
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo Application exited with code %EXITCODE%.
  echo Check data\logs\app.log for details.
  pause
)
exit /b %EXITCODE%
