# scripts/manage_autostart.ps1
param(
    [switch]$Disable,
    [switch]$Status
)

$startupPath = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupPath "FlydigiBS2Controller.lnk"
$exePath = "D:\py\REA_Q-Dir\dist\FlydigiBS2Controller.exe"
$distDir = "D:\py\REA_Q-Dir\dist"

if ($Status) {
    if (Test-Path $shortcutPath) {
        Write-Host "[STATUS] Autostart is ENABLED: $shortcutPath" -ForegroundColor Green
    } else {
        Write-Host "[STATUS] Autostart is DISABLED" -ForegroundColor Yellow
    }
    exit 0
}

if ($Disable) {
    if (Test-Path $shortcutPath) {
        Remove-Item -Path $shortcutPath -Force
        Write-Host "[OK] Autostart shortcut removed." -ForegroundColor Yellow
    } else {
        Write-Host "[INFO] Autostart shortcut does not exist." -ForegroundColor Gray
    }
    exit 0
}

# Default: Enable autostart
if (-not (Test-Path $exePath)) {
    Write-Host "[ERROR] Executable not found: $exePath" -ForegroundColor Red
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $exePath
$Shortcut.Arguments = "--tray"
$Shortcut.WorkingDirectory = $distDir
$Shortcut.Description = "Flydigi BS2 Pro Lightweight Fan Speed Controller"
$Shortcut.Save()

Write-Host "[OK] Autostart shortcut successfully created!" -ForegroundColor Green
Write-Host "Shortcut Path: $shortcutPath" -ForegroundColor Gray
Write-Host "Arguments: --tray (starts silently in notification tray on boot)" -ForegroundColor Cyan
