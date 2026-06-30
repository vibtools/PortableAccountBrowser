# Portability Model

Portable Account Browser stores application-managed state beside the executable:

- `data/profiles/<id>` — Chromium cookies, storage, preferences, and site sessions
- `data/downloads/<id>` — per-profile downloads
- `data/profiles.sqlite3` — launcher profile metadata
- `runtime/chromium` — bundled Chromium runtime

The application itself is installation-free. Existing authenticated cookies may still require
reauthentication after moving to another Windows account or device because Chromium and web
providers can bind secrets to the operating-system user, device, network, or risk environment.
No security control is bypassed.
