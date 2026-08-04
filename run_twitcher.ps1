# Runs twitcher.py and mirrors all output (stdout+stderr) to twitcher_run.log.
# stderr is merged inside cmd so PowerShell does not wrap every stderr line
# as a red NativeCommandError.
$root = $PSScriptRoot
$log = Join-Path $root 'twitcher_run.log'

& cmd /c "python -u `"$root\twitcher.py`" 2>&1" | Tee-Object -FilePath $log
exit $LASTEXITCODE