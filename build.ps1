# Windows 用の配布フォルダを作る: dist\PDF-JA-Translator\PDF-JA-Translator.exe
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --name PDF-JA-Translator --hidden-import keyring.backends.Windows `
    --exclude-module PySide6.QtWebEngineCore `
    --exclude-module PySide6.QtWebEngineWidgets `
    --exclude-module PySide6.QtWebChannel `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtMultimedia `
    --exclude-module PySide6.QtPdf `
    --exclude-module PySide6.QtPdfWidgets `
    --exclude-module PySide6.QtCharts `
    --exclude-module PySide6.QtDataVisualization `
    --exclude-module PySide6.QtNetworkAuth `
    --exclude-module PySide6.QtSvg `
    --exclude-module PySide6.QtSql `
    main.py
$zip = "dist\PDF-JA-Translator-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
tar.exe -a -c -f $zip -C dist PDF-JA-Translator
Write-Host "built: $zip"
