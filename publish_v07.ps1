# ============================================================
#   GitHub release deployment for Twitcher v0.7 "Platform Equality"
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

# --- Create v0.7 release ---
Write-Host "`n[Release] Creating v0.7 'Platform Equality' release..."
$releaseNotes = @"
## Twitcher v0.7 - Platform Equality

### Unified multi-platform architecture
- Single PlatformManager now wraps the Platform ABC classes for Twitch, Kick, and YouTube
- One consistent interface: get_stream_info(), get_live_streams(), get_followed_channels()
- Canonical stream dicts with a mandatory platform field across all subsystems

### Platform-prefix syntax
- Explicit prefixes: kick:xqc, yt:@handle, twitch:pokimane, tw:pokimane
- Auto-detection for URLs (twitch.tv, kick.com, youtube.com, youtu.be)
- Prefix stripping in stream resolver, video window, and channel state

### Equal discovery (watchlist)
- New watchlist UI: platform dropdown + channel input + add button
- Kick/YouTube live streams now actually fetched (previously empty lists)
- watchlist_changed signal triggers live-channel refresh

### Equal watching
- start_channel resolves via multi-platform resolver (was Twitch-only)
- Dispatcher carries platform through switch_stream and DB history
- ViewerMonitor routes each channel through the correct platform client

### Equal UI (platform badges)
- Color-coded badges: Twitch purple, Kick green, YouTube red
- Live followed panel, current watching panel, next stream panel
- Graceful "chat unavailable" state for non-Twitch platforms

### Bug fixes
- Fixed raid detection crash (TypeError on switch_stream)
- Fixed is_kick_configured always returning True
- Fixed get_user_access_token TypeError
- Fixed EventSub websocket protocol (session_welcome + subscription)
- Fixed DB cross-platform collisions (platform column + migration)
- Fixed SullyGoose cache key mismatch
- Fixed ViewerTracker ignoring Kick/YouTube channel field

### Requirements
- Windows 10/11
- VLC media player installed

### Install
Download Watcher.exe below and double-click to run.
"@
$relBody = @{
    tag_name = "v0.7"
    name = "v0.7 - Platform Equality"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json
try {
    $rel = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body $relBody -ContentType "application/json"
    Write-Host "[OK] Release created: $($rel.html_url)"
} catch {
    Write-Host "[WARN] Release creation issue (may already exist): $($_.Exception.Message)"
    $rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.7" -Headers $headers
    Write-Host "[OK] Using existing release: $($rel.html_url)"
}

# --- Upload Watcher.exe asset ---
$exePath = Join-Path $root "dist\Watcher.exe"
if (-not (Test-Path $exePath)) { Write-Host "ERROR: $exePath not found"; exit 1 }
Write-Host "`n[Upload] Attaching Watcher.exe ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..."
$uploadUrl = ($rel.upload_url -replace "{.*}", "") + "?name=Watcher.exe"
$uploadResult = curl.exe -s -L -H "Authorization: token $token" -H "Content-Type: application/octet-stream" --data-binary "@dist/Watcher.exe" $uploadUrl
if ($uploadResult -match '"browser_download_url"\s*:\s*"([^"]+)"') {
    Write-Host "[OK] Asset uploaded: $($Matches[1])"
} else {
    Write-Host "[WARN] Upload response: $($uploadResult.Substring(0, [math]::Min(200, $uploadResult.Length)))"
}

Write-Host "`n============================================================"
Write-Host "  RELEASE v0.7 COMPLETE"
Write-Host "  $($rel.html_url)"
Write-Host "============================================================"