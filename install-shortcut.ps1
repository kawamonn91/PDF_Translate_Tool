# dist の配布フォルダを %LOCALAPPDATA%\Programs にコピーし、デスクトップにショートカットを作る
$ErrorActionPreference = "Stop"
$source = Join-Path $PSScriptRoot "dist\PDF-JA-Translator"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\PDF-JA-Translator"
if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir }
New-Item -ItemType Directory -Force -Path (Split-Path $installDir) | Out-Null
Copy-Item -Recurse -Force $source $installDir

$exe = Join-Path $installDir "PDF-JA-Translator.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = Join-Path $desktop "PDF日本語化ツール.lnk"
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $exe
$link.WorkingDirectory = $installDir
$link.IconLocation = "$exe,0"
$link.Description = "英語のPDF・PowerPointを、レイアウトを保ったまま日本語にします"
$link.Save()
Write-Host "installed: $installDir"
Write-Host "shortcut:  $shortcut"
