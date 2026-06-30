# Upgrade from v1.3.0 to v1.3.1

1. Close Portable Account Browser and its profile Chromium windows.
2. Extract the v1.3.0 → v1.3.1 updater inside the existing project root.
3. Run `EmailPortableBrowser_Update_v1.3.0_to_v1.3.1\apply_update.bat`.
4. Run `test_dev.bat`.
5. Run `build_publish_ready.bat`.

The updater preserves `data`, `runtime`, `.venv`, cookies, sessions, downloads, and the existing SQLite database.
