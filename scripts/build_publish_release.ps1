[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$ReleaseRoot = "D:\Project\Python\Mailbox\release",
    [string]$CertificateThumbprint = $env:PAB_SIGNING_CERT_THUMBPRINT,
    [string]$TimestampServer = "http://timestamp.digicert.com",
    [switch]$SkipTests,
    [switch]$RequireSignature
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

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ChromiumSource = Join-Path $ProjectRoot "runtime\chromium"
$PyInstallerRoot = Join-Path $ProjectRoot "dist\PortableAccountBrowser"
$PublicStage = Join-Path $ProjectRoot "pab_public"
$PortableRuntime = Join-Path $PublicStage "runtime\chromium"
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)

function Invoke-RobocopyTree {
    param([string]$Source, [string]$Destination)
    if (-not (Test-Path -LiteralPath $Source)) {
        throw "Copy source does not exist: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    & robocopy.exe $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
    $Code = $LASTEXITCODE
    $global:LASTEXITCODE = 0
    if ($Code -gt 7) {
        throw "Robocopy failed with exit code $Code while copying '$Source'."
    }
}

function Grant-ReleaseRootAccess {
    param([string]$Path)
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $Path "/inheritance:e" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not enable ACL inheritance on release folder." }
    & icacls.exe $Path "/grant:r" "${Identity}:(OI)(CI)F" "/T" "/C" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not grant full control to '$Identity' on release folder." }

    Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not $_.PSIsContainer -and $_.IsReadOnly) { $_.IsReadOnly = $false }
    }
    $Probe = Join-Path $Path ".release_write_test"
    Set-Content -LiteralPath $Probe -Value "ok" -Encoding ascii
    Remove-Item -LiteralPath $Probe -Force
}

Write-Host "[1/13] Verifying source environment and closed processes..."
if (-not (Test-Path -LiteralPath $VenvPython) -or -not (Test-Path -LiteralPath (Join-Path $ChromiumSource "chrome.exe"))) {
    & (Join-Path $PSScriptRoot "setup_dev.ps1") -Python $Python
    if ($LASTEXITCODE -ne 0) { throw "Source environment setup failed." }
}
& $VenvPython (Join-Path $PSScriptRoot "assert_app_closed.py") --project-root $ProjectRoot
if ($LASTEXITCODE -ne 0) { throw "Application/browser process check failed." }

Write-Host "[2/13] Preparing external release folder with full current-user access..."
Grant-ReleaseRootAccess -Path $ReleaseRoot

Write-Host "[3/13] Installing pinned build dependencies..."
& $VenvPython -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Build dependency installation failed." }

if (-not $SkipTests) {
    Write-Host "[4/13] Running complete source test gate..."
    & (Join-Path $PSScriptRoot "test_dev.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Source test gate failed." }
} else {
    Write-Host "[4/13] Tests skipped by explicit request."
}

Write-Host "[5/13] Cleaning previous public build output..."
Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $ProjectRoot "dist") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force $PublicStage -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $ProjectRoot "pab_source_stage") -ErrorAction SilentlyContinue

Write-Host "[6/13] Building Windows onedir executable with icon/version/manifest..."
& $VenvPython -m PyInstaller --noconfirm --clean EmailPortableBrowser.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
if (-not (Test-Path -LiteralPath $PyInstallerRoot)) {
    throw "PyInstaller output was not created: $PyInstallerRoot"
}
Move-Item -LiteralPath $PyInstallerRoot -Destination $PublicStage

Write-Host "[7/13] Copying tested Chromium runtime..."
Invoke-RobocopyTree -Source $ChromiumSource -Destination $PortableRuntime

Write-Host "[8/13] Creating clean portable data layout..."
foreach ($Relative in @("profiles", "downloads", "logs", "temp", "crash")) {
    $Directory = Join-Path $PublicStage "data\$Relative"
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $Directory ".keep") -Value "clean public data directory" -Encoding ascii
}
$BuildMode = @"
PUBLIC CLEAN BUILD

This package contains no saved profiles, cookies, authenticated sessions,
account metadata, browser history, or personal downloads. Users create their
own isolated portable profiles after launching the application.
"@
Set-Content -LiteralPath (Join-Path $PublicStage "PORTABLE_BUILD_MODE.txt") -Value $BuildMode -Encoding utf8

Write-Host "[9/13] Copying public documentation..."
$Docs = @(
    "README.md", "SECURITY.md", "PRIVACY.md", "SUPPORT.md", "BUILD.md",
    "PUBLISHING.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "OPEN_SOURCE.md",
    "CHANGELOG.md", "RELEASE_NOTES.md", "VERSION", "portable.marker"
)
foreach ($Doc in $Docs) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Doc) -Destination $PublicStage -Force
}

Write-Host "[10/13] Verifying portable executable and clean layout..."
& (Join-Path $PSScriptRoot "verify_portable.ps1") -AppRoot $PublicStage -RequireCleanPublic
if ($LASTEXITCODE -ne 0) { throw "Portable package verification failed." }

$Exe = Join-Path $PublicStage "PortableAccountBrowser.exe"
if ($CertificateThumbprint) {
    Write-Host "Signing executable with the supplied CurrentUser certificate..."
    & (Join-Path $PSScriptRoot "sign_release.ps1") `
        -ExePath $Exe `
        -CertificateThumbprint $CertificateThumbprint `
        -TimestampServer $TimestampServer
    if ($LASTEXITCODE -ne 0) { throw "Authenticode signing step failed." }
}
$Signature = Get-AuthenticodeSignature -FilePath $Exe
$SignatureStatus = [string]$Signature.Status
if ($Signature.Status -eq [System.Management.Automation.SignatureStatus]::Valid) {
    $SignatureStatus = "Valid ($($Signature.SignerCertificate.Subject))"
} elseif ($RequireSignature) {
    throw "Authenticode signature is required, but executable status is '$($Signature.Status)'."
} else {
    Write-Warning "EXE is not Authenticode-signed. GitHub publication is possible, but Windows SmartScreen may warn users."
}

Write-Host "[11/13] Creating and validating the two publish ZIPs..."
& $VenvPython (Join-Path $PSScriptRoot "package_publish_release.py") `
    --project-root $ProjectRoot `
    --binary-root $PublicStage `
    --release-root $ReleaseRoot `
    --version $Version `
    --signature-status $SignatureStatus
if ($LASTEXITCODE -ne 0) { throw "Release packaging failed." }

Write-Host "[12/13] Running independent ZIP/checksum/security verification..."
& $VenvPython (Join-Path $PSScriptRoot "verify_publish_release.py") `
    --release-root $ReleaseRoot `
    --version $Version
if ($LASTEXITCODE -ne 0) { throw "Publish release verification failed." }

Write-Host "[13/13] Finalizing permissions and release report..."
Grant-ReleaseRootAccess -Path $ReleaseRoot

$BinaryZip = Join-Path $ReleaseRoot "PortableAccountBrowser_Windows_x64_v${Version}_Public.zip"
$SourceZip = Join-Path $ReleaseRoot "PortableAccountBrowser_Source_v${Version}.zip"
if ((Get-Item -LiteralPath $BinaryZip).Length -lt 50MB) {
    throw "Public binary ZIP is unexpectedly small."
}
if ((Get-Item -LiteralPath $SourceZip).Length -lt 50KB) {
    throw "Source ZIP is unexpectedly small."
}

Write-Host ""
Write-Host "PASS: Publish-ready release created and verified."
Write-Host "RELEASE ROOT: $ReleaseRoot"
Write-Host "PUBLIC ZIP:   $BinaryZip"
Write-Host "SOURCE ZIP:   $SourceZip"
Write-Host "SIGNATURE:    $SignatureStatus"
Write-Host "PRIVACY:      No personal profiles, cookies, or sessions included."
