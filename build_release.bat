@echo off
setlocal
call "%~dp0build_publish_ready.bat" %*
exit /b %ERRORLEVEL%
