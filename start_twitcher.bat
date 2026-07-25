@echo off

cd /d "%~dp0"

:restart

echo Starting Twitcher...

python twitcher.py

set "EXITCODE=%ERRORLEVEL%"

if not "%EXITCODE%"=="0" (
    echo [AUTO-RESTART] Twitcher exited with code %EXITCODE%. Restarting in 5 seconds...
    timeout /t 5 /nobreak >nul
    goto restart
)

echo [AUTO-RESTART] Twitcher exited cleanly.

exit /b %EXITCODE%