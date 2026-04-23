$ErrorActionPreference = "Stop"

$DistroName = "Ubuntu"
$ServiceName = "screen-golf.service"
$KeepAliveUnitName = "screen-golf-wsl-keepalive"
$WindowsKeepAliveMarker = "screen-golf-windows-keepalive"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogPath = Join-Path (Get-Location) "start-screen-golf-wsl-$Timestamp.log"

Start-Transcript -Path $LogPath -Append | Out-Null

function Invoke-Wsl {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    & wsl.exe -d $DistroName --user root -- @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FailureMessage (exit code: $LASTEXITCODE)"
    }
}

function Test-WslCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & wsl.exe -d $DistroName --user root -- @Arguments
    return $LASTEXITCODE -eq 0
}

function Test-WindowsKeepAliveProcess {
    $processes = Get-CimInstance Win32_Process -Filter "Name = 'wsl.exe'" |
        Where-Object {
            $_.CommandLine -like "*$WindowsKeepAliveMarker*" -and
            $_.CommandLine -like "*-d $DistroName*"
        }

    return $null -ne $processes
}

function Start-WindowsKeepAliveProcess {
    if (Test-WindowsKeepAliveProcess) {
        return
    }

    $keepAliveCommand = "while systemctl is-active --quiet ${KeepAliveUnitName}.service; do sleep 300; done # $WindowsKeepAliveMarker"
    $arguments = @(
        "-d", $DistroName,
        "--user", "root",
        "--",
        "/bin/sh",
        "-lc",
        $keepAliveCommand
    )

    Start-Process -FilePath "wsl.exe" -ArgumentList $arguments -WindowStyle Hidden | Out-Null
}

try {
    Write-Host "Logging to: $LogPath"
    Write-Host "Starting WSL distro and service: $DistroName ($ServiceName)"

    # Keep one lightweight Linux process alive before the bootstrap command exits,
    # otherwise WSL may immediately go back to Stopped.
    if (-not (Test-WslCommand -Arguments @("systemctl", "is-active", "--quiet", "${KeepAliveUnitName}.service"))) {
        if (Test-WslCommand -Arguments @("systemctl", "list-unit-files", "${KeepAliveUnitName}.service", "--no-legend")) {
            Invoke-Wsl -Arguments @("systemctl", "start", "${KeepAliveUnitName}.service") -FailureMessage "Failed to start keepalive systemd unit"
        } else {
            Invoke-Wsl -Arguments @(
                "systemd-run",
                "--unit", $KeepAliveUnitName,
                "--property", "Restart=always",
                "--service-type=simple",
                "/bin/sh",
                "-lc",
                "exec sleep infinity"
            ) -FailureMessage "Failed to create transient keepalive unit"
        }
    }

    Invoke-Wsl -Arguments @("systemctl", "is-active", "--quiet", "${KeepAliveUnitName}.service") -FailureMessage "Keepalive unit is not active"
    Start-WindowsKeepAliveProcess

    Invoke-Wsl -Arguments @("systemctl", "start", $ServiceName) -FailureMessage "Failed to start main service"
    Invoke-Wsl -Arguments @("systemctl", "is-active", "--quiet", $ServiceName) -FailureMessage "Main service is not active"

    Write-Host "WSL distro checked and service started: $DistroName ($ServiceName)"
    Write-Host "Keepalive unit active: ${KeepAliveUnitName}.service"
    Write-Host "Windows keepalive process active for distro: $DistroName"
} finally {
    Stop-Transcript | Out-Null
}
