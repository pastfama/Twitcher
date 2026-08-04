# ============================================================
#   GitHub release deployment for Twitcher v0.6 "timeboss"
#   Uses the token stored in Git Credential Manager.
# ============================================================
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# --- Retrieve token from Git Credential Manager ---
$inputText = "protocol=https`nhost=github.com`n`n"
$cred = $inputText | git credential fill 2>$null
$token = ($cred | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) { Write-Host "ERROR: No GitHub token found."; exit 1 }
Write-Host "[OK] Token retrieved."

$headers = @{ Authorization = "token $token"; Accept = "application/vnd.github+json" }
$api = "https://api.github.com/repos/pastfama/Twitcher"

# --- Create v0.6 release ---
Write-Host "`n[Release] Creating v0.6 'timeboss' release..."
$releaseNotes = @"
## Twitcher v0.6 - TimeBoss

### Centralized timer architecture
- Introduced TimeBoss (core/time_boss) - one QTimer drives ALL periodic work
- Priority-based slot scheduling: video window > UI > background analytics
- ViewerMonitor now registers with TimeBoss instead of owning its own timer
- Periodic live channels refresh every 4 seconds keeps the UI current

### Current Watching panel overhaul
- Complete rewrite of currwatching panel and UI modules
- Streamlined MOM and Sullygoose widget integration
- Improved analytics display with emoji status indicators

### Stability improvements
- Fixed Cyrillic chat crash (UTF-8 safe logging)
- Graceful fallback for Twitch API library
- Better thread pool management - no more GUI hangs from exhausted threads

### Requirements
- Windows 10/11
- VLC media player installed

### Install
Download Twitcher.exe below and double-click to run.
"@
$relBody = @{
    tag_name = "v0.6"
    name = "v0.6 - TimeBoss"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json
try {
    $rel = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body $relBody -ContentType "application/json"
    Write-Host "[OK] Release created: $($rel.html_url)"
} catch {
    Write-Host "[WARN] Release creation issue (may already exist): $($_.Exception.Message)"
    $rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.6" -Headers $headers
    Write-Host "[OK] Using existing release: $($rel.html_url)"
}

# --- Upload Twitcher.exe asset ---
$exePath = Join-Path $root "dist\Twitcher.exe"
if (-not (Test-Path $exePath)) { Write-Host "ERROR: $exePath not found"; exit 1 }
Write-Host "`n[Upload] Attaching Twitcher.exe ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..."
$uploadUrl = ($rel.upload_url -replace "{.*}", "") + "?name=Twitcher.exe"
$uploadResult = curl.exe -s -L -H "Authorization: token $token" -H "Content-Type: application/octet-stream" --data-binary "@dist/Twitcher.exe" $uploadUrl
if ($uploadResult -match '"browser_download_url"\s*:\s*"([^"]+)"') {
    Write-Host "[OK] Asset uploaded: $($Matches[1])"
} else {
    Write-Host "[WARN] Upload response: $($uploadResult.Substring(0, [math]::Min(200, $uploadResult.Length)))"
}

Write-Host "`n============================================================"
Write-Host "  RELEASE v0.6 COMPLETE"
Write-Host "  $($rel.html_url)"
Write-Host "============================================================"