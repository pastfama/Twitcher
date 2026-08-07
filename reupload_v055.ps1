$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$inputText = "protocol=https`nhost=github.com`n`n"
$cred = $inputText | git credential fill 2>$null
$token = ($cred | Where-Object { $_ -like "password=*" }) -replace "^password=", ""
if (-not $token) { Write-Host "ERROR: No GitHub token found."; exit 1 }
Write-Host "[OK] Token retrieved."

$headers = @{ Authorization = "token $token"; Accept = "application/vnd.github+json" }
$api = "https://api.github.com/repos/pastfama/Twitcher"

$rel = Invoke-RestMethod -Uri "$api/releases/tags/v0.55" -Headers $headers
Write-Host "[OK] Found release: $($rel.html_url)"

$oldAsset = $rel.assets | Where-Object { $_.name -eq "Twitcher.exe" }
if ($oldAsset) {
    Write-Host "[Delete] Removing old Twitcher.exe (asset id $($oldAsset.id))..."
    Invoke-RestMethod -Uri "$api/releases/assets/$($oldAsset.id)" -Method Delete -Headers $headers
    Write-Host "[OK] Old asset deleted."
}

$exePath = Join-Path $root "dist\Twitcher.exe"
if (-not (Test-Path $exePath)) { Write-Host "ERROR: $exePath not found"; exit 1 }
Write-Host "[Upload] Attaching Twitcher.exe ($([math]::Round((Get-Item $exePath).Length/1MB,1)) MB)..."
$uploadUrl = ($rel.upload_url -replace "{.*}", "") + "?name=Twitcher.exe"
$uploadResult = curl.exe -s -L -H "Authorization: token $token" -H "Content-Type: application/octet-stream" --data-binary "@dist/Twitcher.exe" $uploadUrl
if ($uploadResult -match '"browser_download_url"\s*:\s*"([^"]+)"') {
    Write-Host "[OK] Asset uploaded: $($Matches[1])"
} else {
    Write-Host "[WARN] Upload response: $($uploadResult.Substring(0, [math]::Min(200, $uploadResult.Length)))"
}

Write-Host "RE-UPLOAD v0.55 COMPLETE"
Write-Host $rel.html_url