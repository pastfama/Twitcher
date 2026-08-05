# ============================================================
#   GitHub release deployment for Twitcher v0.7.1 "First-Run Wizard"
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

# --- Create v0.7.1 release ---
Write-Host "`n[Release] Creating v0.7.1 'First-Run Wizard' release..."
$releaseNotes = @"
## Twitcher v0.7.1 - First-Run Wizard

### New: First-Run Wizard
- Shows a welcome poster on first launch describing Watcher (Twitch, Kick, YouTube in one)
- Confirms the app installation folder
- Only appears once; never blocks subsequent startups

### Includes v0.7 Platform Equality
- Unified PlatformManager for Twitch, Kick, and YouTube
- Watchlist UI + platform badges
- 10 bug fixes (raid crash, EventSub protocol, DB collisions, etc.)

### Bundled VLC
- VLC runtime (libvlc.dll + plugins) is now embedded — no VLC install needed

### Requirements
- Windows 10/11

### Install
Download Watcher.exe below and double-click to run.
"@
$relBody = @{
    tag_name = "v0.7.1"
    name = "v0.7.1 - First-Run Wizard"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json
try {
    $rel = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body $relBody -ContentType "application/json"
    Write-Host "[OK] Release created: $($rel.html_url)"
} catch {
    Write-Host "[WARN] Release creation issue (may already exist): $($_.Exception.Message)"
    $rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.7.1" -Headers $headers
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
Write-Host "  RELEASE v0.7.1 COMPLETE"
Write-Host "  $($rel.html_url)"
Write-Host "============================================================"