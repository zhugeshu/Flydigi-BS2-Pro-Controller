# scripts/install_to_permanent_location.ps1
param(
    [string]$TargetDir = "$env:LOCALAPPDATA\Programs\FlydigiBS2Controller"
)

Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "   Flydigi BS2 Pro Controller 永久迁移与部署   " -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# 1. 确保源文件存在
$srcExe = "D:\py\REA_Q-Dir\dist\FlydigiBS2Controller.exe"
$srcCfg = "D:\py\REA_Q-Dir\dist\config.json"
if (-not (Test-Path $srcCfg)) {
    $srcCfg = "D:\py\REA_Q-Dir\config.json"
}

if (-not (Test-Path $srcExe)) {
    Write-Host "[错误] 未找到源可执行程序: $srcExe" -ForegroundColor Red
    exit 1
}

# 2. 创建目标目录
if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    Write-Host "[创建目录] $TargetDir" -ForegroundColor Green
}

# 3. 复制独立程序和配置文件
$dstExe = Join-Path $TargetDir "FlydigiBS2Controller.exe"
$dstCfg = Join-Path $TargetDir "config.json"

Copy-Item -Path $srcExe -Destination $dstExe -Force
Write-Host "[已复制] 程序主体 -> $dstExe" -ForegroundColor Green

if (Test-Path $srcCfg) {
    Copy-Item -Path $srcCfg -Destination $dstCfg -Force
    Write-Host "[已复制] 配置文件 -> $dstCfg" -ForegroundColor Green
}

# 4. 更新开机自启动快捷方式
$startupPath = [Environment]::GetFolderPath('Startup')
$startupLnk = Join-Path $startupPath "FlydigiBS2Controller.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($startupLnk)
$Shortcut.TargetPath = $dstExe
$Shortcut.Arguments = "--tray"
$Shortcut.WorkingDirectory = $TargetDir
$Shortcut.Description = "Flydigi BS2 Pro Lightweight Fan Speed Controller"
$Shortcut.Save()
Write-Host "[已更新自启] 开机自启动快捷方式已指向新路径: $startupLnk" -ForegroundColor Green

# 5. 创建桌面快捷方式方便手动打开
$desktopPath = [Environment]::GetFolderPath('Desktop')
$desktopLnk = Join-Path $desktopPath "飞智BS2散热控制器.lnk"
$DesktopShortcut = $WshShell.CreateShortcut($desktopLnk)
$DesktopShortcut.TargetPath = $dstExe
$DesktopShortcut.WorkingDirectory = $TargetDir
$DesktopShortcut.Description = "飞智 BS2 Pro 极简散热控制台"
$DesktopShortcut.Save()
Write-Host "[已创建桌面图标] $desktopLnk" -ForegroundColor Green

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "🎉 迁移完成！程序已独立部署在: $TargetDir" -ForegroundColor Green
Write-Host "现在您可以放心删除当前开发目录 (D:\py\REA_Q-Dir) 了！" -ForegroundColor Yellow
Write-Host "=============================================" -ForegroundColor Cyan
