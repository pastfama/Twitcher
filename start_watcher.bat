@echo off

cd /d "%~dp0"

:restart

echo Starting Watcher...

python watcher.py

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo [AUTO-RESTART] Watcher exited with code %EXITCODE%. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto restart
)

echo [AUTO-RESTART] Watcher exited cleanly.

exit /b %EXITCODE%