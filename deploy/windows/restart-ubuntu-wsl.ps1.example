$ErrorActionPreference = "Stop"

$DistroName = "Ubuntu"
$StartupCommand = "/bin/true"

Write-Host "Stopping WSL distro: $DistroName"
wsl.exe --terminate $DistroName

Start-Sleep -Seconds 2

Write-Host "Starting WSL distro: $DistroName"
wsl.exe -d $DistroName --exec $StartupCommand

Write-Host "WSL distro restarted: $DistroName"
