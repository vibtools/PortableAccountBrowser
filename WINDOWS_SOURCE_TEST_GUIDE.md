# Windows Source and Release Test Guide — v1.3.1

## Source test

```bat
test_dev.bat
```

Expected on a symlink-capable account: `57 passed` and portable diagnostics PASS.

On a standard Windows account without Developer Mode or symlink privilege, the two symlink
integration tests report `SKIPPED` instead of failing with WinError 1314. This is an environment
limitation, not an application failure. Enable Windows Developer Mode or run from an appropriately
privileged test account when full symlink regression coverage is required.

Setup preserves the tracked `runtime\chromium\.gitkeep` placeholder while installing Chromium,
so a successful setup does not leave the Git working tree dirty.

## Source UI/icon test

```bat
run_dev.bat
```

Verify:

- The custom blue Portable Account Browser icon appears in the title bar and
  Windows taskbar.
- Existing Gmail/WhatsApp profiles remain logged in.
- Profiles remain isolated and reopen as a single tab.

## Personal production build

Close the browser and launcher, then run:

```bat
build_personal_portable.bat
```

Extract the resulting ZIP into a new writable folder and run:

```text
PortableAccountBrowser.exe
```

Verify the custom icon, existing account sessions, single-tab behavior, profile
switching, and the `Verify portability` dialog.

## Clean public build

```bat
build_publish_ready.bat
```

The public ZIP must open with no existing profiles or private session data.
