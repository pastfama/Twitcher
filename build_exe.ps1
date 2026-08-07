# ============================================================
#                 WATCHER BUILD SCRIPT
# ============================================================
# Builds a standalone Windows .exe using PyInstaller.
#
# Prerequisites:
#   pip install pyinstaller
#
# Usage:
#   powershell -File build_exe.ps1
#
# Output:
#   dist/Watcher.exe  (standalone executable)
# ============================================================

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "                 WATCHER BUILD" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# --- Check PyInstaller ---
Write-Host "[1/4] Checking PyInstaller..." -ForegroundColor Yellow
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "  PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to install PyInstaller." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  PyInstaller OK." -ForegroundColor Green

# --- Clean previous builds ---
Write-Host "[2/4] Cleaning previous builds..." -ForegroundColor Yellow
$buildDir = Join-Path $root "build"
$distDir = Join-Path $root "dist"
if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
Write-Host "  Clean." -ForegroundColor Green

# --- Build ---
Write-Host "[3/4] Building Watcher.exe..." -ForegroundColor Yellow
Set-Location $root
pyinstaller watcher.spec --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed." -ForegroundColor Red
    exit 1
}

# --- Verify ---
Write-Host "[4/4] Verifying build..." -ForegroundColor Yellow
$exe = Join-Path $distDir "Watcher.exe"
if (Test-Path $exe) {
    $size = (Get-Item $exe).Length / 1MB
    Write-Host "  SUCCESS: $exe ($([math]::Round($size, 1)) MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  BUILD COMPLETE" -ForegroundColor Green
    Write-Host "  Output: dist\Watcher.exe" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Cyan
} else {
    Write-Host "ERROR: Watcher.exe not found in dist/" -ForegroundColor Red
    exit 1
}