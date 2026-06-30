[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AppRoot,
    [switch]$RequireCleanPublic
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$ResolvedRoot = (Resolve-Path -LiteralPath $AppRoot).Path
$ExpectedVersion = (Get-Content -LiteralPath (Join-Path $ResolvedRoot "VERSION") -Raw).Trim()

$Required = @(
    "PortableAccountBrowser.exe", "_internal", "runtime\chromium\chrome.exe",
    "data\profiles", "data\downloads", "data\logs", "data\temp", "data\crash",
    "portable.marker", "README.md", "SECURITY.md", "PRIVACY.md", "BUILD.md",
    "LICENSE", "THIRD_PARTY_NOTICES.md", "OPEN_SOURCE.md",
    "PORTABLE_BUILD_MODE.txt", "VERSION"
)
$Missing = @()
foreach ($Relative in $Required) {
    if (-not (Test-Path -LiteralPath (Join-Path $ResolvedRoot $Relative))) { $Missing += $Relative }
}
if ($Missing.Count -gt 0) { throw "Portable verification failed. Missing: $($Missing -join ', ')" }

foreach ($Forbidden in @(".venv", "tests", "app.py", "EmailPortableBrowser.spec", "build")) {
    if (Test-Path -LiteralPath (Join-Path $ResolvedRoot $Forbidden)) {
        throw "Development-only item leaked into binary package: $Forbidden"
    }
}

if ($RequireCleanPublic) {
    $ForbiddenData = @(
        "data\profiles.sqlite3", "data\profiles.sqlite3-wal", "data\profiles.sqlite3-shm",
        "data\ui_settings.json", "data\update_backups"
    )
    foreach ($Relative in $ForbiddenData) {
        if (Test-Path -LiteralPath (Join-Path $ResolvedRoot $Relative)) {
            throw "Private data leaked into public package: $Relative"
        }
    }
    foreach ($Relative in @("profiles", "downloads", "logs", "temp", "crash")) {
        $Directory = Join-Path $ResolvedRoot "data\$Relative"
        $Unexpected = Get-ChildItem -LiteralPath $Directory -Recurse -File -Force |
            Where-Object { $_.Name -notin @(".keep", ".gitkeep") }
        if ($Unexpected) {
            throw "Public data directory is not clean: $($Unexpected[0].FullName)"
        }
    }
    $Mode = Get-Content -LiteralPath (Join-Path $ResolvedRoot "PORTABLE_BUILD_MODE.txt") -Raw
    if ($Mode -notmatch "PUBLIC CLEAN BUILD") { throw "Public build mode marker is incorrect." }
}

$Chrome = Join-Path $ResolvedRoot "runtime\chromium\chrome.exe"
$ChromeVersion = (Get-Item -LiteralPath $Chrome).VersionInfo.ProductVersion
if (-not $ChromeVersion) { throw "Chromium file-version metadata check failed." }

$Probe = Join-Path $ResolvedRoot "data\.write_test"
Set-Content -LiteralPath $Probe -Value "ok" -Encoding ascii
Remove-Item -LiteralPath $Probe -Force

$Exe = Join-Path $ResolvedRoot "PortableAccountBrowser.exe"
$VersionInfo = (Get-Item -LiteralPath $Exe).VersionInfo
if (-not $VersionInfo.ProductVersion.StartsWith($ExpectedVersion)) {
    throw "Executable version mismatch. Expected $ExpectedVersion, got $($VersionInfo.ProductVersion)."
}
if ($VersionInfo.ProductName -ne "Portable Account Browser") {
    throw "Executable ProductName metadata is missing or incorrect."
}

try {
    Add-Type -AssemblyName System.Drawing
    $ExtractedIcon = [System.Drawing.Icon]::ExtractAssociatedIcon($Exe)
    if ($null -eq $ExtractedIcon) { throw "No associated application icon was found." }
    $ExtractedIcon.Dispose()
} catch {
    throw "Executable icon verification failed: $($_.Exception.Message)"
}

$Process = Start-Process -FilePath $Exe -ArgumentList "--diagnose" -WorkingDirectory $ResolvedRoot -Wait -PassThru
if ($Process.ExitCode -ne 0) {
    throw "Built application diagnostics failed with exit code $($Process.ExitCode)."
}

Write-Host "Verified executable: PortableAccountBrowser.exe $($VersionInfo.ProductVersion)"
Write-Host "Verified application icon: PASS"
Write-Host "Verified Chromium: $ChromeVersion"
Write-Host "Built application diagnostics: PASS"
Write-Host "Portable layout verification: PASS"
if ($RequireCleanPublic) { Write-Host "Clean public-data verification: PASS" }
