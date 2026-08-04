@echo off
cd /d "%~dp0"
echo Running Twitcher in watch mode (VERBOSE DEBUG)
set "TWITCHER_WATCH=1"
set "TWITCHER_DEBUG=1"
set "PYTHONFAULTHANDLER=1"
set "PYTHONUNBUFFERED=1"
rem NOTE: do NOT enable qt.* debug logging - qt.text.font.colrv1 floods
rem output on every emoji render and freezes the UI.
set "QT_LOGGING_RULES=qt.text.*=false"

:restart
echo Starting Twitcher... [%date% %time%]
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_twitcher.ps1"
set "EXITCODE=%ERRORLEVEL%"

echo [WATCH] Twitcher exited with code %EXITCODE%. Restarting in 3 seconds...

timeout /t 3 /nobreak >nul

goto restart

:end
exit /b %EXITCODE%