@echo off
setlocal
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_dev.ps1" %*
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" (
  echo.
  echo SETUP FAILED with exit code %EXITCODE%.
  pause
)
exit /b %EXITCODE%
