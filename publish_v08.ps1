# ============================================================
#   GitHub release deployment for Twitcher v0.8 "Installation Wizard"
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

# --- Create v0.8 release ---
Write-Host "`n[Release] Creating v0.8 'Installation Wizard' release..."
$releaseNotes = @'
## Twitcher v0.8 - Installation Wizard

### New: Multi-Step Installation Wizard
- **Step 1: Welcome** - app poster, platform badges, feature list, install folder confirmation
- **Step 2: License Agreement** - scrollable MIT license + personal use addendum; "I Accept" checkbox required to proceed
- **Step 3: Data & Database Setup** - shows data folder location, initializes SQLite database, migrates legacy data if found
- **Step 4: Shortcuts** - optional desktop and Start Menu shortcut creation
- **Step 5: Complete** - launch Watcher

### Licensing
- Added LICENSE file: MIT License + Personal Use Addendum
- License states: open source, personal use only, not distributed, not affiliated with Twitch/Kick/YouTube
- License is bundled with the exe and shown in the installation wizard

### Data & Database
- New paths.py module: centralized path resolution for frozen exe vs dev mode
- Database, logs, and settings now stored in %APPDATA%\Watcher\ (frozen) or project root (dev)
- Legacy data migration: existing watcher.db and logs are automatically copied to the new location
- No separate database software required - SQLite is embedded

### Includes v0.7.1 Features
- First-run wizard foundation
- Unified PlatformManager for Twitch, Kick, and YouTube
- Watchlist UI + platform badges
- 10 bug fixes (raid crash, EventSub protocol, DB collisions, etc.)
- Bundled VLC runtime - no external VLC install needed

### Requirements
- Windows 10/11

### Install
Download Watcher.exe below and double-click to run.
'@

$relBody = @{
    tag_name = "v0.8"
    name = "v0.8 - Installation Wizard"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json
try {
    $rel = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body $relBody -ContentType "application/json"
    Write-Host "[OK] Release created: $($rel.html_url)"
} catch {
    Write-Host "[WARN] Release creation issue (may already exist): $($_.Exception.Message)"
    $rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.8" -Headers $headers
    Write-Host "[OK] Using existing release: $($rel.html_url)"
}

# --- Upload Watcher.exe asset (delete existing first so re-publish works) ---
$exePath = Join-Path $root "dist\Watcher.exe"
if (-not (Test-Path $exePath)) { Write-Host "ERROR: $exePath not found"; exit 1 }
Write-Host "`n[Upload] Attaching Watcher.exe ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..."
# Delete any existing Watcher.exe asset on the release (GitHub rejects duplicate names).
$existingAssets = Invoke-RestMethod -Uri "$api/releases/$($rel.id)/assets" -Headers $headers
foreach ($asset in $existingAssets) {
    if ($asset.name -eq "Watcher.exe") {
        Write-Host "[OK] Deleting existing asset: $($asset.name)"
        Invoke-RestMethod -Uri "$api/releases/assets/$($asset.id)" -Method Delete -Headers $headers | Out-Null
    }
}
$uploadUrl = ($rel.upload_url -replace "{.*}", "") + "?name=Watcher.exe"
$uploadResult = curl.exe -s -L -H "Authorization: token $token" -H "Content-Type: application/octet-stream" --data-binary "@dist/Watcher.exe" $uploadUrl
if ($uploadResult -match '"browser_download_url"\s*:\s*"([^"]+)"') {
    Write-Host "[OK] Asset uploaded: $($Matches[1])"
} else {
    Write-Host "[WARN] Upload response: $($uploadResult.Substring(0, [math]::Min(200, $uploadResult.Length)))"
}

Write-Host "`n============================================================"
Write-Host "  RELEASE v0.8 COMPLETE"
Write-Host "  $($rel.html_url)"
Write-Host "============================================================"