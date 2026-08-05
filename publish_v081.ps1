# Twitcher v0.8.1 release deployment
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# Retrieve token from Git Credential Manager
$inputText = "protocol=https`nhost=github.com`n`n"
$cred = $inputText | git credential fill 2>$null
$token = ($cred | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) { Write-Host "ERROR: No GitHub token found."; exit 1 }
Write-Host "[OK] Token retrieved."

$headers = @{ Authorization = "token $token"; Accept = "application/vnd.github+json" }
$api = "https://api.github.com/repos/pastfama/Twitcher"

# Create v0.8.1 release
Write-Host "`n[Release] Creating v0.8.1 release..."
$releaseNotes = "## Twitcher v0.8.1 - Fundamental Architecture Rewrite`n`n### Core Architecture Rewrite`n- StreamState: Single source of truth for all stream data with Qt signals`n- UpdateScheduler: Single master clock replacing 5 separate QTimers`n- ServiceLayer: Isolated API calls`n- Reactive panels: Panels self-update via StreamState signals`n`n### Bug Fixes`n- Fixed ImageCache.setPixmap(None) PySide6 error`n- Fixed panel switching to random streamers`n- Fixed viewer count not refreshing`n- Fixed MOM gauge not moving`n- Fixed live channels never refreshing`n`n### Performance Improvements`n- ViewerMonitor: 4s to 2s polling`n- MOM gauge: smooth 60fps animation`n- Momentum: dual EMA calculation`n- SullyGoose: current channel priority, 10min cache`n- Graph: 60 data points`n- DB writes throttled to 8s`n`n### Install`nDownload Watcher.exe below and double-click to run."

$relBody = @{
    tag_name = "v0.8.1"
    name = "v0.8.1 - Fundamental Rewrite"
    body = $releaseNotes
    draft = $false
    prerelease = $false
} | ConvertTo-Json
try {
    $rel = Invoke-RestMethod -Uri "$api/releases" -Method Post -Headers $headers -Body $relBody -ContentType "application/json"
    Write-Host "[OK] Release created: $($rel.html_url)"
} catch {
    Write-Host "[WARN] Release creation issue: $($_.Exception.Message)"
    try {
        $rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.8.1" -Headers $headers
        Write-Host "[OK] Using existing release: $($rel.html_url)"
    } catch {
        Write-Host "ERROR: Could not create or find release."; exit 1
    }
}

# Upload Watcher.exe asset
$exePath = Join-Path $root "dist\Watcher.exe"
if (-not (Test-Path $exePath)) { Write-Host "ERROR: $exePath not found"; exit 1 }
Write-Host "`n[Upload] Attaching Watcher.exe ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..."
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

Write-Host "`n[SUCCESS] RELEASE v0.8.1 COMPLETE"
Write-Host "$($rel.html_url)"