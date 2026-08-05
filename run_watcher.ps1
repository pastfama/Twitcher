# Runs watcher.py and mirrors all output (stdout+stderr) to watcher_run.log.
# stderr is merged inside cmd so PowerShell does not wrap every stderr line
# as a red NativeCommandError.
$root = $PSScriptRoot
$log = Join-Path $root 'watcher_run.log'

& cmd /c "python -u `"$root\watcher.py`" 2>&1" | Tee-Object -FilePath $log
exit $LASTEXITCODE