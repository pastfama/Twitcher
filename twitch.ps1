# ============================================================
#                 TWITCH RAID CHAIN PLAYER
# ============================================================

$ErrorActionPreference = "Continue"

# ============================================================
# FILES
# ============================================================

$lastChannelFile = "$PSScriptRoot\last_channel.txt"
$raidFile        = "$PSScriptRoot\raid_target.txt"
$monitor         = "$PSScriptRoot\raid_monitor.py"

# ============================================================
# PROGRAM PATHS
# ============================================================

$chatterino = "C:\Program Files\Chatterino\Chatterino.exe"
$vlc        = "C:\Program Files\VideoLAN\VLC\vlc.exe"

# ============================================================
# FUNCTIONS
# ============================================================

function Write-Log {
    param(
        [string]$Message
    )

    $time = Get-Date -Format "HH:mm:ss"
    Write-Host "[$time] $Message"
}

function Get-ElapsedTime {
    param(
        [string]$StartTime
    )

    $start = [DateTime]::Parse($StartTime)
    $duration = (Get-Date) - $start

    $hours = [int]$duration.TotalHours
    $minutes = $duration.Minutes

    if ($hours -gt 0) {
        return "${hours}h ${minutes}m"
    }
    else {
        return "${minutes}m"
    }
}

function Get-LiveFollowedChannels {

    Write-Log "Connecting to Twitch API..."

    $headers = @{
        "Client-ID" = $env:TWITCH_CLIENT_ID
        "Authorization" = "Bearer $env:TWITCH_ACCESS_TOKEN"
    }

    if (
        [string]::IsNullOrWhiteSpace($env:TWITCH_CLIENT_ID) -or
        [string]::IsNullOrWhiteSpace($env:TWITCH_ACCESS_TOKEN)
    ) {
        Write-Host ""
        Write-Host "ERROR: Twitch credentials are missing." -ForegroundColor Red
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit
    }

    # Get logged-in Twitch user
    try {

        $user = Invoke-RestMethod `
            -Uri "https://api.twitch.tv/helix/users" `
            -Headers $headers `
            -ErrorAction Stop

    }
    catch {

        Write-Host ""
        Write-Host "ERROR: Could not authenticate with Twitch." -ForegroundColor Red
        Write-Host $_.Exception.Message
        Write-Host ""

        Read-Host "Press Enter to exit"
        exit
    }

    $userId = $user.data[0].id
    $userName = $user.data[0].display_name

    Write-Log "Logged in as Twitch user: $userName"

    # Get followed channels
    try {

        $followed = Invoke-RestMethod `
            -Uri "https://api.twitch.tv/helix/channels/followed?user_id=$userId&first=100" `
            -Headers $headers `
            -ErrorAction Stop

    }
    catch {

        Write-Host ""
        Write-Host "ERROR: Could not retrieve followed channels." -ForegroundColor Red
        Write-Host $_.Exception.Message
        Write-Host ""

        Read-Host "Press Enter to exit"
        exit
    }

    $followedLogins = @(
        $followed.data.broadcaster_login
    )

    Write-Log "You follow $($followedLogins.Count) channels."

    if ($followedLogins.Count -eq 0) {
        return @()
    }

    # Build API request
    $queryParts = @()

    foreach ($login in $followedLogins) {
        $queryParts += "user_login=$login"
    }

    $query = $queryParts -join "&"

    # Get live channels
    try {

        $live = Invoke-RestMethod `
            -Uri "https://api.twitch.tv/helix/streams?$query" `
            -Headers $headers `
            -ErrorAction Stop

    }
    catch {

        Write-Host ""
        Write-Host "ERROR: Could not retrieve live streams." -ForegroundColor Red
        Write-Host $_.Exception.Message
        Write-Host ""

        return @()
    }

    return @($live.data)
}

function Start-Chatterino {
    param(
        [string]$Channel
    )

    if (-not (Test-Path $chatterino)) {

        Write-Log "WARNING: Chatterino was not found."
        Write-Log "Expected path: $chatterino"

        return
    }

    Write-Log "Opening Chatterino for: $Channel"

    Start-Process `
        -FilePath $chatterino `
        -ArgumentList "--activate", $Channel
}

# ============================================================
# CHANNEL SELECTION
# ============================================================

while ($true) {

    Clear-Host

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "                 TWITCH RAID CHAIN PLAYER"
    Write-Host "============================================================"
    Write-Host ""

    Write-Log "Checking which followed channels are currently LIVE..."

    $liveChannels = Get-LiveFollowedChannels

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "              CURRENTLY LIVE CHANNELS"
    Write-Host "============================================================"
    Write-Host ""

    if ($liveChannels.Count -eq 0) {

        Write-Host "Nobody you follow is currently live." -ForegroundColor Yellow
        Write-Host ""

    }
    else {

        for ($i = 0; $i -lt $liveChannels.Count; $i++) {

            $stream = $liveChannels[$i]

            $duration = Get-ElapsedTime `
                -StartTime $stream.started_at

            Write-Host ""
            Write-Host "[$($i + 1)] $($stream.user_name)" -ForegroundColor Cyan

            Write-Host "    Viewers:  $($stream.viewer_count.ToString('N0'))"
            Write-Host "    Category: $($stream.game_name)"
            Write-Host "    Live for: $duration"
            Write-Host "    Started:  $($stream.started_at)"
            Write-Host "    Title:    $($stream.title)"
        }
    }

    # Last streamer
    $lastChannel = $null

    if (Test-Path $lastChannelFile) {
        $lastChannel = (Get-Content $lastChannelFile -Raw).Trim().ToLower()
    }

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "OPTIONS"
    Write-Host "============================================================"

    if ($lastChannel) {
        Write-Host "L - Use last streamer: $lastChannel"
    }

    Write-Host "M - Enter channel manually"
    Write-Host "R - Refresh live channels"
    Write-Host "Q - Quit"
    Write-Host ""

    $choice = Read-Host "Choose"

    # Quit
    if ($choice -match "^[Qq]$") {
        exit
    }

    # Refresh
    if ($choice -match "^[Rr]$") {
        continue
    }

    # Manual channel
    if ($choice -match "^[Mm]$") {

        $channel = Read-Host "Enter Twitch channel"

        if ([string]::IsNullOrWhiteSpace($channel)) {
            continue
        }

        break
    }

    # Last channel
    if (
        $choice -match "^[Ll]$" -and
        $lastChannel
    ) {

        $channel = $lastChannel
        break
    }

    # Number selection
    if (
        $choice -match "^\d+$" -and
        $liveChannels.Count -gt 0
    ) {

        $number = [int]$choice

        if (
            $number -ge 1 -and
            $number -le $liveChannels.Count
        ) {

            $channel = $liveChannels[$number - 1].user_login
            break
        }
    }

    Write-Host ""
    Write-Host "Invalid selection." -ForegroundColor Red
    Start-Sleep -Seconds 2
}

# ============================================================
# INITIALIZE
# ============================================================

$channel = $channel.Trim().ToLower()

$currentChannel = $channel

Set-Content `
    -Path $lastChannelFile `
    -Value $currentChannel

Write-Host ""
Write-Host "============================================================"
Write-Host "                 STARTING STREAM SESSION"
Write-Host "============================================================"
Write-Host ""

Write-Log "Selected channel: $currentChannel"

# Remove old raid target
if (Test-Path $raidFile) {

    Remove-Item `
        $raidFile `
        -Force `
        -ErrorAction SilentlyContinue

    Write-Log "Removed old raid target file."
}

# ============================================================
# START CHATTERINO
# ============================================================

Start-Chatterino `
    -Channel $currentChannel

# ============================================================
# START RAID MONITOR
# ============================================================

Write-Log "Starting Twitch raid monitor..."

$monitorProcess = Start-Process `
    -FilePath "py" `
    -ArgumentList "`"$monitor`" $currentChannel" `
    -WindowStyle Minimized `
    -PassThru

Write-Log "Raid monitor started."
Write-Log "Monitor PID: $($monitorProcess.Id)"

# ============================================================
# MAIN STREAM LOOP
# ============================================================

while ($true) {

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "                    STREAM STATUS"
    Write-Host "============================================================"
    Write-Host ""

    Write-Log "Current channel: $currentChannel"
    Write-Log "Starting Streamlink..."
    Write-Log "Quality: BEST AVAILABLE"
    Write-Log "Player: VLC"
    Write-Log "Network caching: 8000 ms"
    Write-Host ""

    # --------------------------------------------------------
    # Start Streamlink
    # --------------------------------------------------------

    # This is intentionally close to the command that worked
    $streamlinkArguments = `
        "twitch.tv/$currentChannel best " +
        "--player `"$vlc`" " +
        "--retry-streams 10 " +
        "--retry-open 10 " +
        "--stream-segment-attempts 10 " +
        "--stream-segment-timeout 30 " +
        "--hls-live-edge 10 " +
        "--player-args `"--network-caching=8000`""

    $streamlinkProcess = Start-Process `
        -FilePath "streamlink" `
        -ArgumentList $streamlinkArguments `
        -PassThru

    Write-Log "Streamlink PID: $($streamlinkProcess.Id)"
    Write-Log "VLC should now be playing: $currentChannel"

    $streamStartTime = Get-Date

    # --------------------------------------------------------
    # Monitor Streamlink
    # --------------------------------------------------------

    while (-not $streamlinkProcess.HasExited) {

        Start-Sleep -Seconds 2

        # Check for raid
        if (Test-Path $raidFile) {

            $newChannel = (
                Get-Content $raidFile -Raw
            ).Trim().ToLower()

            if (
                $newChannel -and
                $newChannel -ne $currentChannel
            ) {

                Write-Host ""
                Write-Host "============================================================"
                Write-Host "                      RAID DETECTED"
                Write-Host "============================================================"
                Write-Host ""

                Write-Log "Previous channel: $currentChannel"
                Write-Log "Raid target:      $newChannel"
                Write-Log "Switching stream..."
                Write-Host ""

                # Stop Streamlink
                if (-not $streamlinkProcess.HasExited) {

                    Write-Log "Stopping Streamlink..."

                    Stop-Process `
                        -Id $streamlinkProcess.Id `
                        -Force `
                        -ErrorAction SilentlyContinue
                }

                # Stop VLC
                Write-Log "Stopping VLC..."

                Get-Process vlc `
                    -ErrorAction SilentlyContinue |
                    Stop-Process `
                    -Force `
                    -ErrorAction SilentlyContinue

                # Update channel
                $currentChannel = $newChannel

                # Save newest channel
                Set-Content `
                    -Path $lastChannelFile `
                    -Value $currentChannel

                Write-Log "Saved last streamer: $currentChannel"

                # Remove processed raid
                Remove-Item `
                    $raidFile `
                    -Force `
                    -ErrorAction SilentlyContinue

                # Switch Chatterino
                Write-Log "Switching Chatterino to: $currentChannel"

                Start-Chatterino `
                    -Channel $currentChannel

                Write-Log "Raid handoff complete."

                break
            }
        }
    }

    # ========================================================
    # STREAM ENDED / NETWORK ERROR
    # ========================================================

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "                STREAMLINK STOPPED"
    Write-Host "============================================================"
    Write-Host ""

    $runtime = (Get-Date) - $streamStartTime

    Write-Log "Channel: $currentChannel"
    Write-Log "Session duration: $($runtime.ToString('hh\:mm\:ss'))"
    Write-Log "Possible causes:"
    Write-Log "  - Network error"
    Write-Log "  - Stream ended"
    Write-Log "  - Twitch connection dropped"
    Write-Log "  - VLC closed"
    Write-Log "Restarting in 5 seconds..."

    Start-Sleep -Seconds 5
}