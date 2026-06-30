from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Literal

from epb.config import (
    CHROMIUM_DIR,
    CRASH_DIR,
    DOWNLOADS_DIR,
    PROFILES_DIR,
    TEMP_DIR,
    is_within_base,
)
from epb.models import EmailProfile
from epb.process_control import close_orphaned_portable_chromium, close_process_tree

BrowserExitCallback = Callable[[str, int], None]
SessionStatus = Literal["New", "Browser data saved", "Cookies saved"]


def discover_chromium(chromium_root: Path = CHROMIUM_DIR) -> Path:
    root = chromium_root.resolve()
    candidates = [
        root / "chrome.exe",
        root / "chromium.exe",
        root / "chrome",
        root / "chromium",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    executable_names = {"chrome.exe", "chromium.exe", "chrome", "chromium"}
    for candidate in sorted(root.rglob("*")) if root.exists() else []:
        if candidate.is_file() and candidate.name.casefold() in executable_names:
            resolved = candidate.resolve()
            if root == resolved.parent or root in resolved.parents:
                return resolved

    raise FileNotFoundError(
        "Portable Chromium was not found under runtime/chromium. "
        "On Windows run scripts\\setup_dev.ps1 before starting the app."
    )


def session_status(profile_dir: Path) -> SessionStatus:
    """Report whether Chromium has written local profile/session artifacts.

    Only existence is checked; the app never opens or reads cookie contents.
    """
    default_dir = Path(profile_dir) / "Default"
    cookie_candidates = (
        default_dir / "Network" / "Cookies",
        default_dir / "Cookies",
    )
    if any(path.is_file() for path in cookie_candidates):
        return "Cookies saved"

    browser_data_candidates = (
        default_dir / "Local Storage",
        default_dir / "IndexedDB",
        default_dir / "Session Storage",
        default_dir / "Service Worker",
        default_dir / "History",
        default_dir / "Preferences",
    )
    if any(path.exists() for path in browser_data_candidates):
        return "Browser data saved"
    return "New"


def build_chromium_args(
    chromium: Path,
    profile: EmailProfile,
    profile_dir: Path,
    cache_dir: Path,
    crash_dir: Path,
) -> list[str]:
    """Build a direct Chromium command line for one isolated portable profile."""
    return [
        str(chromium),
        f"--user-data-dir={profile_dir}",
        "--profile-directory=Default",
        f"--disk-cache-dir={cache_dir}",
        "--disk-cache-size=268435456",
        f"--crash-dumps-dir={crash_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        # Chrome for Testing explicitly supports this switch. It removes the
        # non-interactive testing disclaimer bar without modifying browser files.
        "--disable-infobars",
        "--disable-background-mode",
        "--disable-default-apps",
        "--disable-component-update",
        "--disable-breakpad",
        "--disable-crash-reporter",
        "--disable-sync",
        "--noerrdialogs",
        "--disable-search-engine-choice-screen",
        "--hide-crash-restore-bubble",
        "--new-window",
        profile.start_url,
    ]


class BrowserManager:
    def __init__(self, logger: logging.Logger, on_exit: BrowserExitCallback | None = None):
        self.logger = logger
        self.on_exit = on_exit
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._profile_id: str | None = None
        self._monitor_thread: threading.Thread | None = None
        self._expected_exit_pids: set[int] = set()

    @property
    def active_profile_id(self) -> str | None:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self._profile_id
            return None

    def cleanup_orphans(self) -> int:
        count = close_orphaned_portable_chromium(PROFILES_DIR)
        if count:
            self.logger.warning("Closed %s orphaned portable Chromium process tree(s)", count)
        return count

    def open_profile(self, profile: EmailProfile, profile_dir: Path) -> int:
        with self._lock:
            self._close_current_locked()

            # Close only Chromium trees whose command line points at this app's
            # profiles root. Normal Chrome installations are never targeted.
            self.cleanup_orphans()

            chromium = discover_chromium()
            profile_dir = Path(profile_dir).resolve()
            download_dir = (DOWNLOADS_DIR / profile.id).resolve()
            cache_dir = (profile_dir / "Cache").resolve()
            crash_dir = (CRASH_DIR / profile.id).resolve()

            for managed_path in (profile_dir, download_dir, cache_dir, crash_dir):
                if not is_within_base(managed_path):
                    raise ValueError(f"Portable path escaped the application root: {managed_path}")
                managed_path.mkdir(parents=True, exist_ok=True)

            self._remove_stale_profile_locks(profile_dir)
            self._clear_previous_tab_session(profile_dir)
            self._configure_profile_preferences(profile_dir, download_dir)

            args = build_chromium_args(
                chromium=chromium,
                profile=profile,
                profile_dir=profile_dir,
                cache_dir=cache_dir,
                crash_dir=crash_dir,
            )

            environment = os.environ.copy()
            environment["TEMP"] = str(TEMP_DIR)
            environment["TMP"] = str(TEMP_DIR)
            environment["TMPDIR"] = str(TEMP_DIR)

            creation_flags = 0
            if os.name == "nt":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            self.logger.info(
                "Opening profile %s (%s) with Chromium at %s",
                profile.id,
                profile.provider,
                chromium,
            )
            process = subprocess.Popen(
                args,
                cwd=str(chromium.parent),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            time.sleep(0.6)
            early_exit = process.poll()
            if early_exit is not None:
                raise RuntimeError(
                    f"Portable Chromium exited during startup with code {early_exit}. "
                    "Check that runtime/chromium contains the complete Chromium folder."
                )

            self._process = process
            self._profile_id = profile.id
            self._monitor_thread = threading.Thread(
                target=self._monitor_process,
                args=(process, profile.id),
                name=f"ChromiumMonitor-{profile.id[:8]}",
                daemon=True,
            )
            self._monitor_thread.start()
            return process.pid

    @staticmethod
    def _remove_stale_profile_locks(profile_dir: Path) -> None:
        """Remove Chromium singleton artifacts after owned processes are closed."""
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = profile_dir / name
            if not os.path.lexists(path):
                continue
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            except OSError as exc:
                raise RuntimeError(f"Could not remove stale Chromium lock: {path}") from exc

    @staticmethod
    def _clear_previous_tab_session(profile_dir: Path) -> None:
        """Clear only prior tab/window restore state before a new launch.

        Cookies, Local Storage, IndexedDB, Service Workers, history, saved site
        permissions, and login state remain untouched. This prevents duplicate
        tabs when the launcher supplies the profile's start URL again.
        """
        default_dir = Path(profile_dir) / "Default"
        session_dir = default_dir / "Sessions"

        if session_dir.exists():
            try:
                shutil.rmtree(session_dir)
            except OSError as exc:
                raise RuntimeError(
                    f"Could not clear previous Chromium tab session: {session_dir}"
                ) from exc

        for name in ("Current Session", "Current Tabs", "Last Session", "Last Tabs"):
            path = default_dir / name
            if not path.exists():
                continue
            try:
                path.unlink()
            except OSError as exc:
                raise RuntimeError(
                    f"Could not clear previous Chromium tab state: {path}"
                ) from exc

    @staticmethod
    def _configure_profile_preferences(profile_dir: Path, download_dir: Path) -> None:
        """Keep downloads and browser-managed state inside the portable root."""
        default_dir = profile_dir / "Default"
        default_dir.mkdir(parents=True, exist_ok=True)
        preferences_path = default_dir / "Preferences"
        preferences: dict = {}

        if preferences_path.exists():
            try:
                loaded = json.loads(preferences_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    preferences = loaded
            except (OSError, json.JSONDecodeError):
                backup_path = preferences_path.with_name(
                    f"Preferences.corrupt-{time.time_ns()}"
                )
                try:
                    preferences_path.replace(backup_path)
                except OSError:
                    pass
                preferences = {}

        download_preferences = preferences.setdefault("download", {})
        if not isinstance(download_preferences, dict):
            download_preferences = {}
            preferences["download"] = download_preferences
        download_preferences["default_directory"] = str(download_dir.resolve())
        download_preferences["prompt_for_download"] = False
        download_preferences["directory_upgrade"] = True

        browser_preferences = preferences.setdefault("browser", {})
        if not isinstance(browser_preferences, dict):
            browser_preferences = {}
            preferences["browser"] = browser_preferences
        browser_preferences["check_default_browser"] = False

        session_preferences = preferences.setdefault("session", {})
        if not isinstance(session_preferences, dict):
            session_preferences = {}
            preferences["session"] = session_preferences
        session_preferences["restore_on_startup"] = 0
        session_preferences["startup_urls"] = []

        profile_preferences = preferences.setdefault("profile", {})
        if not isinstance(profile_preferences, dict):
            profile_preferences = {}
            preferences["profile"] = profile_preferences
        profile_preferences["exited_cleanly"] = True
        profile_preferences["exit_type"] = "Normal"

        temp_path = preferences_path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(preferences, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temp_path, preferences_path)

    def _monitor_process(self, process: subprocess.Popen[bytes], profile_id: str) -> None:
        exit_code = process.wait()
        with self._lock:
            expected_exit = process.pid in self._expected_exit_pids
            self._expected_exit_pids.discard(process.pid)
            if self._process is process:
                self._process = None
                self._profile_id = None
        self.logger.info("Chromium exited for profile %s with code %s", profile_id, exit_code)
        if self.on_exit and not expected_exit:
            try:
                self.on_exit(profile_id, exit_code)
            except Exception:
                self.logger.exception("Browser exit callback failed")

    def close_current(self) -> None:
        with self._lock:
            self._close_current_locked()

    def _close_current_locked(self) -> None:
        process = self._process
        profile_id = self._profile_id
        if process is None:
            self._profile_id = None
            return

        if process.poll() is None:
            self.logger.info("Closing Chromium gracefully for profile %s", profile_id)
            self._expected_exit_pids.add(process.pid)
            close_process_tree(process.pid, graceful_timeout=12.0)

        self._process = None
        self._profile_id = None

    def shutdown(self) -> None:
        self.close_current()
