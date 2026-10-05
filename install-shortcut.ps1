# Install the portable package to %LOCALAPPDATA%\Programs and create the desktop shortcut.
$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "dist\PDF-JA-Translator"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\PDF-JA-Translator"
$running = Get-Process -Name "pythonw" -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$installDir*" }
if ($running) { $running | Stop-Process -Force }
if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
New-Item -ItemType Directory -Force -Path (Split-Path $installDir) | Out-Null
Copy-Item -Recurse -Force $source $installDir

$pythonw = Join-Path $installDir "python\pythonw.exe"
$appDir = Join-Path $installDir "app"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = Join-Path $desktop "PDF日本語化ツール.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $pythonw
$link.Arguments = "main.py"
$link.WorkingDirectory = $appDir
$link.Description = "英語のPDF・PowerPointを、レイアウトを保ったまま日本語にします"
$link.Save()
Write-Host "installed: $installDir"
Write-Host "shortcut:  $shortcut"
