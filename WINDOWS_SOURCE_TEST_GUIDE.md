# Windows Source and Release Test Guide — v1.3.1

## Source test

```bat
test_dev.bat
```

Expected: `41 passed` and portable diagnostics PASS.

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
build_release.bat
```

The public ZIP must open with no existing profiles or private session data.
