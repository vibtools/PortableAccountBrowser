@echo off
setlocal
set "RELEASE_ROOT=D:\Project\Python\Mailbox\release"
if not "%~1"=="" set "RELEASE_ROOT=%~1"
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\verify_publish_release.py" --release-root "%RELEASE_ROOT%" --version 1.3.1
set EXITCODE=%ERRORLEVEL%
if not "%EXITCODE%"=="0" pause
exit /b %EXITCODE%
