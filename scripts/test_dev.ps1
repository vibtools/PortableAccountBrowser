[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
Set-Location $ProjectRoot

if (-not (Test-Path $VenvPython)) {
    throw ".venv was not found. Run scripts\setup_dev.ps1 first."
}
if (-not (Test-Path (Join-Path $ProjectRoot "runtime\chromium\chrome.exe"))) {
    throw "runtime\chromium\chrome.exe was not found. Run scripts\setup_dev.ps1 first."
}

Write-Host "[1/5] Verifying Tkinter..."
& $VenvPython -c "import tkinter; print('Tkinter', tkinter.TkVersion, 'PASS')"
if ($LASTEXITCODE -ne 0) { throw "Tkinter verification failed." }

Write-Host "[2/5] Compiling Python source..."
& $VenvPython -m compileall -q app.py epb tests
if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }

Write-Host "[3/5] Running automated tests..."
& $VenvPython -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw "Automated tests failed." }

Write-Host "[4/5] Running portable diagnostics..."
& $VenvPython app.py --diagnose
if ($LASTEXITCODE -ne 0) { throw "Portable diagnostics failed." }

Write-Host "[5/5] Verifying Chromium executable..."
$ChromePath = Join-Path $ProjectRoot "runtime\chromium\chrome.exe"
$ChromeVersion = (Get-Item -LiteralPath $ChromePath).VersionInfo.ProductVersion
if (-not $ChromeVersion) { throw "Chromium file-version metadata check failed." }
Write-Host "Chromium $ChromeVersion"
Write-Host "PASS: Source-mode test gate completed."
