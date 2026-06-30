# GitHub and Public Publishing Guide

## Safe release assets

Publish only:

- `PortableAccountBrowser_Windows_x64_v1.3.1_Public.zip`
- `PortableAccountBrowser_Source_v1.3.1.zip`
- their `.sha256` files
- `SHA256SUMS_v1.3.1.txt`
- `BUILD_REPORT_v1.3.1.txt`

Never publish a personal build or the working `data` directory.

## GitHub repository topics

Recommended topics:

`portable-browser`, `multi-account-browser`, `chromium-profiles`, `windows-portable-app`, `gmail`, `whatsapp-web`, `telegram-web`, `python`, `tkinter`, `privacy-tools`

## Suggested release title

`Portable Account Browser v1.3.1 — Clean Windows Portable Release`

## Signing

An Authenticode certificate is optional for open-source distribution but strongly recommended. Unsigned executables can trigger Windows SmartScreen warnings. Provide a certificate thumbprint during the build: `build_publish_ready.bat -CertificateThumbprint "YOUR_CERT_THUMBPRINT" -RequireSignature`. The certificate must exist in `Cert:\CurrentUser\My`.
