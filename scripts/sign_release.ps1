[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,

    [Parameter(Mandatory = $true)]
    [string]$CertificateThumbprint,

    [string]$TimestampServer = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ResolvedExe = (Resolve-Path -LiteralPath $ExePath).Path
$Certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint"
$Signature = Set-AuthenticodeSignature `
    -FilePath $ResolvedExe `
    -Certificate $Certificate `
    -HashAlgorithm SHA256 `
    -TimestampServer $TimestampServer

if ($Signature.Status -ne "Valid") {
    throw "Authenticode signing failed: $($Signature.Status) $($Signature.StatusMessage)"
}

Write-Host "PASS: Authenticode signature is valid."
Write-Host "Signed: $ResolvedExe"
