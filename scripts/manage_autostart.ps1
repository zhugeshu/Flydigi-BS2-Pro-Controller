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
        Write-Host "[状态] 开机自启动已启用: $shortcutPath" -ForegroundColor Green
    } else {
        Write-Host "[状态] 开机自启动未启用" -ForegroundColor Yellow
    }
    exit 0
}

if ($Disable) {
    if (Test-Path $shortcutPath) {
        Remove-Item -Path $shortcutPath -Force
        Write-Host "[成功] 已取消开机自启动快捷方式。" -ForegroundColor Yellow
    } else {
        Write-Host "[提示] 开机自启快捷方式不存在。" -ForegroundColor Gray
    }
    exit 0
}

# Default: Enable autostart
if (-not (Test-Path $exePath)) {
    Write-Host "[错误] 未找到可执行文件: $exePath" -ForegroundColor Red
    exit 1
}

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $exePath
$Shortcut.Arguments = "--tray"
$Shortcut.WorkingDirectory = $distDir
$Shortcut.Description = "Flydigi BS2 Pro Lightweight Fan Speed Controller"
$Shortcut.Save()

Write-Host "[成功] 已成功设置开机自启动！" -ForegroundColor Green
Write-Host "快捷方式位置: $shortcutPath" -ForegroundColor Gray
Write-Host "启动参数: --tray (开机静默常驻托盘，不弹窗打扰)" -ForegroundColor Cyan
