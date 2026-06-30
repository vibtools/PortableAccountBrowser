[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$SkipTests,
    [switch]$IncludeExistingData
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "This release script must run on Windows 10/11."
}
if ([IntPtr]::Size -ne 8) {
    throw "Use 64-bit PowerShell and 64-bit Python for the Windows x64 release."
}

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot "VERSION") -Raw).Trim()
if ($Version -ne "1.3.1") {
    throw "Unexpected project version '$Version'. This build script requires v1.3.1."
}

$Venv = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$ChromiumSource = Join-Path $ProjectRoot "runtime\chromium"
$PyInstallerDistRoot = Join-Path $ProjectRoot "dist\PortableAccountBrowser"
$DistRoot = Join-Path $ProjectRoot "pab"
$PortableRuntime = Join-Path $DistRoot "runtime\chromium"
$ReleaseRoot = Join-Path $ProjectRoot "release"
$Mode = if ($IncludeExistingData) { "personal" } else { "public" }
$ModeTitle = if ($IncludeExistingData) { "Personal" } else { "Public" }
$ZipName = "PortableAccountBrowser_Windows_x64_v${Version}_${Mode}.zip"
$ZipPath = Join-Path $ReleaseRoot $ZipName
$SourceZipName = "PortableAccountBrowser_Source_v${Version}.zip"
$SourceZipPath = Join-Path $ReleaseRoot $SourceZipName
$BuildStage = Join-Path $ProjectRoot "build\source-release"

function Copy-DirectoryContents {
    param([string]$Source, [string]$Destination)
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    if (Test-Path -LiteralPath $Source) {
        Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
        }
    }
}

function Write-HashManifest {
    param([string]$Root, [string]$OutputFile)
    $Resolved = (Resolve-Path -LiteralPath $Root).Path
    $Lines = Get-ChildItem -LiteralPath $Resolved -Recurse -File -Force |
        Where-Object { $_.FullName -ne $OutputFile } |
        Sort-Object FullName |
        ForEach-Object {
            $Relative = $_.FullName.Substring($Resolved.Length).TrimStart('\') -replace '\\', '/'
            $Hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
            "$Hash  $Relative"
        }
    Set-Content -LiteralPath $OutputFile -Value $Lines -Encoding ascii
}

Write-Host "[1/11] Verifying the source environment..."
if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Path -LiteralPath (Join-Path $ChromiumSource "chrome.exe"))) {
    & (Join-Path $PSScriptRoot "setup_dev.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) { throw "Source environment setup failed." }
}

& $VenvPython (Join-Path $PSScriptRoot "assert_app_closed.py") --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw "Application/browser process check failed." }

Write-Host "[2/11] Installing pinned build dependency..."
& $VenvPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

if (-not $SkipTests) {
    Write-Host "[3/11] Running the complete source test gate..."
    & (Join-Path $PSScriptRoot "test_dev.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Source test gate failed." }
} else {
    Write-Host "[3/11] Tests skipped by explicit request."
}

Write-Host "[4/11] Cleaning previous build output..."
Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $ProjectRoot "dist") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $DistRoot -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null

Write-Host "[5/11] Building the Windows onedir executable with icon and version resources..."
& $VenvPython -m PyInstaller --noconfirm --clean EmailPortableBrowser.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
if (-not (Test-Path -LiteralPath $PyInstallerDistRoot)) { throw "PyInstaller output directory was not created." }
Move-Item -LiteralPath $PyInstallerDistRoot -Destination $DistRoot

Write-Host "[6/11] Copying the tested Chromium runtime..."
if (-not (Test-Path -LiteralPath (Join-Path $ChromiumSource "chrome.exe"))) {
    throw "The tested Chromium runtime is missing from runtime\chromium."
}
Copy-DirectoryContents -Source $ChromiumSource -Destination $PortableRuntime

Write-Host "[7/11] Creating the portable data layout ($Mode mode)..."
foreach ($Relative in @("profiles", "downloads", "logs", "temp", "crash")) {
    $Directory = Join-Path $DistRoot "data\$Relative"
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $Directory ".keep") -Value "portable data directory" -Encoding ascii
}

if ($IncludeExistingData) {
    Copy-DirectoryContents -Source (Join-Path $ProjectRoot "data\profiles") -Destination (Join-Path $DistRoot "data\profiles")
    Copy-DirectoryContents -Source (Join-Path $ProjectRoot "data\downloads") -Destination (Join-Path $DistRoot "data\downloads")
    foreach ($FileName in @("profiles.sqlite3", "ui_settings.json")) {
        $SourceFile = Join-Path $ProjectRoot "data\$FileName"
        if (Test-Path -LiteralPath $SourceFile) {
            Copy-Item -LiteralPath $SourceFile -Destination (Join-Path $DistRoot "data\$FileName") -Force
        }
    }
}

$BuildModeText = if ($IncludeExistingData) {
@"
PERSONAL PORTABLE BUILD

This package includes the source project's saved browser profiles and may
contain authenticated cookies, local storage, history, account metadata, and
downloads. Keep it private. Do not upload or publicly distribute this ZIP.
"@
} else {
@"
PUBLIC CLEAN BUILD

This package contains no saved account profiles or authenticated sessions.
Users create their own portable profiles after launch.
"@
}
Set-Content -LiteralPath (Join-Path $DistRoot "PORTABLE_BUILD_MODE.txt") -Value $BuildModeText -Encoding utf8

Write-Host "[8/11] Copying open-source and release documentation..."
$ReleaseDocs = @(
    "README.md",
    "SECURITY.md",
    "BUILD.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "OPEN_SOURCE.md",
    "CHANGELOG.md",
    "VERSION",
    "portable.marker"
)
foreach ($Doc in $ReleaseDocs) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Doc) -Destination $DistRoot -Force
}

$ManifestPath = Join-Path $DistRoot "RELEASE_MANIFEST.sha256"
Write-HashManifest -Root $DistRoot -OutputFile $ManifestPath

Write-Host "[9/11] Verifying executable metadata, icon, diagnostics, and layout..."
& (Join-Path $PSScriptRoot "verify_portable.ps1") -AppRoot $DistRoot
if ($LASTEXITCODE -ne 0) { throw "Portable package verification failed." }

Write-Host "[10/11] Creating the open-source archive..."
Remove-Item -Recurse -Force $BuildStage -ErrorAction SilentlyContinue
$SourceRoot = Join-Path $BuildStage "PortableAccountBrowser_Source_v$Version"
New-Item -ItemType Directory -Path $SourceRoot -Force | Out-Null

$SourceFiles = @(
    ".gitignore",
    "app.py",
    "EmailPortableBrowser.spec",
    "portable.marker",
    "pytest.ini",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-build.txt",
    "run_dev.bat",
    "setup_dev.bat",
    "test_dev.bat",
    "build_release.bat",
    "build_personal_portable.bat",
    "README.md",
    "SECURITY.md",
    "BUILD.md",
    "PROJECT_ANALYSIS.md",
    "AUDIT_REPORT.md",
    "TEST_RESULTS.md",
    "FINAL_DELIVERY_STATUS.md",
    "CHANGELOG.md",
    "WINDOWS_SOURCE_TEST_GUIDE.md",
    "UPGRADE_FROM_1.2.1.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "OPEN_SOURCE.md",
    "CONTRIBUTING.md",
    "VERSION"
)
foreach ($File in $SourceFiles) {
    $Source = Join-Path $ProjectRoot $File
    if (Test-Path -LiteralPath $Source) {
        Copy-Item -LiteralPath $Source -Destination $SourceRoot -Force
    }
}
foreach ($Directory in @("epb", "scripts", "tests", "assets")) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Directory) -Destination $SourceRoot -Recurse -Force
}
foreach ($Relative in @("data\profiles", "data\downloads", "data\logs", "data\temp", "data\crash", "runtime\chromium")) {
    $Directory = Join-Path $SourceRoot $Relative
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $Directory ".gitkeep") -Value "" -Encoding ascii
}
Get-ChildItem -LiteralPath $SourceRoot -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $SourceRoot -Recurse -File -Include "*.pyc","*.bak" | Remove-Item -Force
Write-HashManifest -Root $SourceRoot -OutputFile (Join-Path $SourceRoot "SOURCE_MANIFEST.sha256")

Remove-Item -LiteralPath $SourceZipPath -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $SourceRoot "*") -DestinationPath $SourceZipPath -CompressionLevel Optimal

Write-Host "[11/11] Creating the $ModeTitle portable ZIP and checksums..."
Remove-Item -LiteralPath $ZipPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$ZipPath.sha256" -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$SourceZipPath.sha256" -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $DistRoot "*") -DestinationPath $ZipPath -CompressionLevel Optimal

$BinaryHash = Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256
$SourceHash = Get-FileHash -LiteralPath $SourceZipPath -Algorithm SHA256
Set-Content -LiteralPath "$ZipPath.sha256" -Value "$($BinaryHash.Hash.ToLower())  $ZipName" -Encoding ascii
Set-Content -LiteralPath "$SourceZipPath.sha256" -Value "$($SourceHash.Hash.ToLower())  $SourceZipName" -Encoding ascii

$BuildReport = @"
Portable Account Browser v$Version
Build mode: $Mode
Built: $([DateTime]::Now.ToString("yyyy-MM-dd HH:mm:ss zzz"))
Python: $(& $VenvPython --version 2>&1)
PyInstaller: $(& $VenvPython -m PyInstaller --version 2>&1)
Chromium: $((Get-Item -LiteralPath (Join-Path $ChromiumSource "chrome.exe")).VersionInfo.ProductVersion)
Executable: PortableAccountBrowser.exe
Binary ZIP SHA-256: $($BinaryHash.Hash.ToLower())
Source ZIP SHA-256: $($SourceHash.Hash.ToLower())
Authenticode: Not signed by the automated build. Use scripts\sign_release.ps1 with your code-signing certificate before public distribution.
"@
Set-Content -LiteralPath (Join-Path $ReleaseRoot "BUILD_REPORT_v$Version.txt") -Value $BuildReport -Encoding utf8

Write-Host ""
Write-Host "PASS: Production portable package created"
Write-Host "MODE:   $ModeTitle"
Write-Host "EXE:    $(Join-Path $DistRoot 'PortableAccountBrowser.exe')"
Write-Host "ZIP:    $ZipPath"
Write-Host "SHA256: $($BinaryHash.Hash)"
Write-Host "SOURCE: $SourceZipPath"
Write-Host ""
if ($IncludeExistingData) {
    Write-Warning "This personal ZIP contains saved sessions. Keep it private."
}
