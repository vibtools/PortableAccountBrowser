# Build Guide — v1.3.1

## Source test

```bat
setup_dev.bat -Python "D:\App\python312\python.exe"
test_dev.bat
```

## Publish-ready build

Close the launcher and all profile Chromium processes, then run:

```bat
build_publish_ready.bat
```

Default release directory:

```text
D:\Project\Python\Mailbox
elease
```

Outputs:

```text
PortableAccountBrowser_Windows_x64_v1.3.1_Public.zip
PortableAccountBrowser_Source_v1.3.1.zip
PortableAccountBrowser_Windows_x64_v1.3.1_Public.zip.sha256
PortableAccountBrowser_Source_v1.3.1.zip.sha256
SHA256SUMS_v1.3.1.txt
BUILD_REPORT_v1.3.1.txt
```

Custom output directory:

```bat
build_publish_ready.bat -ReleaseRoot "E:\Releases\PortableAccountBrowser"
```

Sign with a certificate in `Cert:\CurrentUser\My` and require a valid signature:

```bat
build_publish_ready.bat -CertificateThumbprint "YOUR_CERT_THUMBPRINT" -RequireSignature
```

You can also set `PAB_SIGNING_CERT_THUMBPRINT` before running the build.

The public build contains no saved profile/session data. `build_personal_portable.bat` remains available for private use only.
