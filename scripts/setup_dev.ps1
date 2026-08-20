[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipBrowserDownload
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Development setup must run on Windows 10/11."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$Venv = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$DownloadRoot = Join-Path $ProjectRoot "runtime\.playwright-download"
$ChromiumRoot = Join-Path $ProjectRoot "runtime\chromium"

Write-Host "[1/7] Verifying 64-bit Python..."
& $Python -c "import struct,sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; assert struct.calcsize('P')*8 == 64, '64-bit Python required'; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw "Python verification failed." }

Write-Host "[2/7] Creating project-local .venv..."
if (-not (Test-Path $VenvPython)) {
    & $Python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}

Write-Host "[3/7] Installing development dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $VenvPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (-not $SkipBrowserDownload) {
    Write-Host "[4/7] Downloading the pinned Chromium runtime..."
    Remove-Item -Recurse -Force $DownloadRoot -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $DownloadRoot -Force | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = $DownloadRoot
    $env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"
    & $VenvPython -m playwright install chromium --no-shell
    if ($LASTEXITCODE -ne 0) { throw "Chromium download failed." }

    $ChromeExe = Get-ChildItem -Path $DownloadRoot -Filter "chrome.exe" -File -Recurse |
        Where-Object { $_.FullName -match "chromium-" } |
        Select-Object -First 1

    if (-not $ChromeExe) {
        throw "Downloaded Chromium executable was not found under $DownloadRoot"
    }

    Write-Host "[5/7] Installing Chromium inside runtime\chromium..."
    $Staging = Join-Path $ProjectRoot "runtime\chromium.staging"
    Remove-Item -Recurse -Force $Staging -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $Staging -Force | Out-Null
    Copy-Item -Path (Join-Path $ChromeExe.Directory.FullName "*") -Destination $Staging -Recurse -Force

    Remove-Item -Recurse -Force $ChromiumRoot -ErrorAction SilentlyContinue
    Move-Item -Path $Staging -Destination $ChromiumRoot
    New-Item -ItemType File -Path (Join-Path $ChromiumRoot ".gitkeep") -Force | Out-Null
    Remove-Item -Recurse -Force $DownloadRoot -ErrorAction SilentlyContinue
} else {
    Write-Host "[4/7] Chromium download skipped."
    Write-Host "[5/7] Existing runtime\chromium will be used."
}

Write-Host "[6/7] Running source audit and automated tests..."
& (Join-Path $PSScriptRoot "test_dev.ps1")
if ($LASTEXITCODE -ne 0) { throw "Development verification failed." }

Write-Host "[7/7] Setup complete."
Write-Host ""
Write-Host "PASS: Python source environment is ready."
Write-Host "Run the app with:"
Write-Host "  .\run_dev.bat"
Write-Host "or:"
Write-Host "  .\.venv\Scripts\python.exe .\app.py"
