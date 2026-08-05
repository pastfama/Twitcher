@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

:: ============================================================
:: Watcher Launcher — auto-restarts on crash, logs to file
:: ============================================================

:: Activate venv if present
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

set "LOG=watcher_output.txt"
set "MAX_RESTARTS=50"
set "RESTART_COUNT=0"

echo [%date% %time%] Watcher launcher started >> "%LOG%"

:restart

set /a RESTART_COUNT+=1

if %RESTART_COUNT% gtr %MAX_RESTARTS% (
    echo [%date% %time%] Max restarts (%MAX_RESTARTS%) reached. Exiting.
    echo [%date% %time%] Max restarts reached. >> "%LOG%"
    goto end
)

echo [%date% %time%] Starting Watcher... (attempt %RESTART_COUNT%)
echo [%date% %time%] --- Watcher start (attempt %RESTART_COUNT%) --- >> "%LOG%"

python -u watcher.py 2>>"%LOG%"
set "EXITCODE=%ERRORLEVEL%"

if "%EXITCODE%"=="0" (
    echo [%date% %time%] Watcher exited cleanly.
    echo [%date% %time%] --- Watcher exited cleanly --- >> "%LOG%"
    goto end
)

echo [%date% %time%] Watcher crashed with code %EXITCODE%. Restarting in 3s...
echo [%date% %time%] --- Crash exit code: %EXITCODE% --- >> "%LOG%"
timeout /t 3 /nobreak >nul
goto restart

:end
endlocal
exit /b 0