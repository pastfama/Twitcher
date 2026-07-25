@echo off
cd /d "%~dp0"
echo Running Twitcher in watch mode
set "TWITCHER_WATCH=1"

:restart
echo Starting Twitcher...
python "%~dp0twitcher.py"
set "EXITCODE=%ERRORLEVEL%"

echo [WATCH] Twitcher exited with code %EXITCODE%. Restarting in 3 seconds...

timeout /t 3 /nobreak >nul

goto restart

:end
exit /b %EXITCODE%
