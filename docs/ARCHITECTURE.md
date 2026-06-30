# Architecture

Portable Account Browser uses a launcher-and-profile architecture.

## Main components

- `app.py` — application entry point
- `epb/ui.py` — compact Tkinter desktop interface
- `epb/database.py` — SQLite profile metadata
- `epb/browser.py` — Chromium discovery and profile launching
- `epb/process_control.py` — safe browser lifecycle control
- `epb/providers.py` — service catalogue and HTTPS start URLs
- `epb/diagnostics.py` — portable-root, database, runtime, and path checks
- `scripts/` — development, build, signing, and release-verification tools

## Profile isolation

Every configured account receives its own Chromium `user-data-dir`. Browser
storage is therefore separated at the profile-directory level.

## Portable storage

App-managed paths are resolved relative to the launcher root:

- `data/profiles`
- `data/downloads`
- `data/logs`
- `data/temp`
- `runtime/chromium`

## Build model

PyInstaller `onedir` packaging is used so dependencies remain inspectable and
the application does not need to extract itself into a temporary directory on
every launch.

## Public-release boundary

The public build creates empty writable data directories and rejects personal
browser data. Personal builds must never be published.
