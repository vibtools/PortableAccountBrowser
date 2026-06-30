from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "Portable Account Browser"
APP_VERSION = "1.3.1"
MIN_PYTHON = (3, 10)
RECOMMENDED_PYTHON = "3.12 x64"
APP_EXECUTABLE_NAME = "PortableAccountBrowser.exe"
APP_USER_MODEL_ID = "OpenSource.PortableAccountBrowser"


def get_base_dir() -> Path:
    """Return the portable application root.

    * PyInstaller onedir: directory containing the executable.
    * Source mode: repository root containing ``app.py``.

    All application-managed persistent paths are derived from this directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


BASE_DIR = get_base_dir()
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", BASE_DIR)).resolve()
ASSETS_DIR = RESOURCE_ROOT / "assets"
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
DOWNLOADS_DIR = DATA_DIR / "downloads"
LOGS_DIR = DATA_DIR / "logs"
TEMP_DIR = DATA_DIR / "temp"
CRASH_DIR = DATA_DIR / "crash"
DATABASE_PATH = DATA_DIR / "profiles.sqlite3"
RUNTIME_DIR = BASE_DIR / "runtime"
CHROMIUM_DIR = RUNTIME_DIR / "chromium"
PORTABLE_MARKER = BASE_DIR / "portable.marker"

MANAGED_DIRECTORIES = (
    DATA_DIR,
    PROFILES_DIR,
    DOWNLOADS_DIR,
    LOGS_DIR,
    TEMP_DIR,
    CRASH_DIR,
    RUNTIME_DIR,
    CHROMIUM_DIR,
)


def ensure_supported_python() -> None:
    if sys.version_info < MIN_PYTHON:
        minimum = ".".join(map(str, MIN_PYTHON))
        raise RuntimeError(
            f"Python {minimum} or newer is required. "
            f"Python {sys.version.split()[0]} is currently running."
        )


def ensure_runtime_directories() -> None:
    ensure_supported_python()
    for path in MANAGED_DIRECTORIES:
        path.mkdir(parents=True, exist_ok=True)

    # Chromium child processes inherit these values. This keeps temporary files
    # created by the browser process under the application root rather than the
    # host user's normal TEMP directory.
    os.environ["TEMP"] = str(TEMP_DIR)
    os.environ["TMP"] = str(TEMP_DIR)
    os.environ["TMPDIR"] = str(TEMP_DIR)


def assert_portable_root_writable() -> None:
    probe = DATA_DIR / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        raise PermissionError(
            f"The portable folder is not writable: {BASE_DIR}. "
            "Move the project to a writable folder or USB drive. Do not run it "
            "from Program Files, inside the ZIP, or from a read-only location."
        ) from exc


def is_within_base(path: Path) -> bool:
    """Return True when ``path`` resolves inside the portable application root."""
    base = BASE_DIR.resolve()
    resolved = Path(path).resolve()
    return resolved == base or base in resolved.parents
