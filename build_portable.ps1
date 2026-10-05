# Build the portable package (no exe is created; the signed Python runtime runs the app).
# Output: dist\PDF-JA-Translator\ (python\ = embeddable Python, lib\ = libraries, app\ = this code)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$version = "3.14.6"
$cache = Join-Path $root "dist-cache"
$embedZip = Join-Path $cache "python-$version-embed-amd64.zip"
$out = Join-Path $root "dist\PDF-JA-Translator"

New-Item -ItemType Directory -Force -Path $cache | Out-Null
if (-not (Test-Path $embedZip)) {
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$version/python-$version-embed-amd64.zip" -OutFile $embedZip
}

if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force -Path $out | Out-Null
Expand-Archive -Path $embedZip -DestinationPath (Join-Path $out "python")

& $venvPython -m pip install --target (Join-Path $out "lib") -r (Join-Path $root "requirements-runtime.txt") --only-binary=:all: --no-compile
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$appDir = Join-Path $out "app"
New-Item -ItemType Directory -Force -Path $appDir | Out-Null
Copy-Item -Recurse (Join-Path $root "ja_translator") (Join-Path $appDir "ja_translator")
Copy-Item (Join-Path $root "main.py") (Join-Path $appDir "main.py")

# Let the embedded Python see the bundled libraries (and pywin32's folders).
$major = $version.Split(".")[0]; $minor = $version.Split(".")[1]
$pth = Get-ChildItem (Join-Path $out "python") -Filter "python$major$minor._pth" | Select-Object -First 1
Set-Content -Path $pth.FullName -Encoding ASCII -Value @(
    "python$major$minor.zip",
    ".",
    "..\app",
    "..\lib",
    "..\lib\win32",
    "..\lib\win32\lib",
    "..\lib\pythonwin",
    "..\lib\pywin32_system32"
)

$zip = Join-Path $root "dist\PDF-JA-Translator-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
& "$env:SystemRoot\System32\tar.exe" -a -c -f $zip -C (Join-Path $root "dist") PDF-JA-Translator
Write-Host "built: $zip"
