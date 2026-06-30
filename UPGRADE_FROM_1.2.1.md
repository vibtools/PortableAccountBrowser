# Upgrade from v1.2.1 to v1.3.1

1. Close the launcher and its managed Chromium window.
2. Extract the v1.2.1 → v1.3.1 update folder inside the project root.
3. Run:

```bat
EmailPortableBrowser_Update_v1.2.1_to_v1.3.1\apply_update.bat
```

The updater replaces source/build files only. It preserves:

- `data` including profiles, cookies, sessions, database, and downloads
- `runtime` including the tested Chromium build
- `.venv`

After updating:

```bat
test_dev.bat
run_dev.bat
```

To create a personal EXE package with the currently saved sessions:

```bat
build_personal_portable.bat
```
