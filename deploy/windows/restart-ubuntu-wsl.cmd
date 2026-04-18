@echo off
setlocal

powershell.exe -ExecutionPolicy Bypass -File "%~dp0restart-ubuntu-wsl.ps1"

endlocal
