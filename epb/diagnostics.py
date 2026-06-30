from __future__ import annotations

import json
import os
import platform
import sqlite3
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from epb.browser import discover_chromium
from epb.config import (
    APP_NAME,
    APP_VERSION,
    BASE_DIR,
    CHROMIUM_DIR,
    CRASH_DIR,
    DATABASE_PATH,
    DATA_DIR,
    DOWNLOADS_DIR,
    LOGS_DIR,
    PROFILES_DIR,
    TEMP_DIR,
    assert_portable_root_writable,
    ensure_runtime_directories,
    is_within_base,
)


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    app_name: str
    app_version: str
    operating_system: str
    python_version: str
    python_executable: str
    source_mode: bool
    base_dir: str
    data_dir: str
    chromium_dir: str
    chromium_executable: str | None
    chromium_version: str | None
    database_path: str
    database_ok: bool
    portable_paths_ok: bool
    writable: bool
    temp_environment_ok: bool
    profile_count: int
    session_profiles: int
    errors: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return (
            self.writable
            and self.portable_paths_ok
            and self.temp_environment_ok
            and self.database_ok
            and self.chromium_executable is not None
            and not self.errors
        )


def _windows_file_version(executable: Path) -> str | None:
    """Read a Windows executable's version resource without launching it."""
    if sys.platform != "win32":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        class VS_FIXEDFILEINFO(ctypes.Structure):
            _fields_ = [
                ("dwSignature", wintypes.DWORD),
                ("dwStrucVersion", wintypes.DWORD),
                ("dwFileVersionMS", wintypes.DWORD),
                ("dwFileVersionLS", wintypes.DWORD),
                ("dwProductVersionMS", wintypes.DWORD),
                ("dwProductVersionLS", wintypes.DWORD),
                ("dwFileFlagsMask", wintypes.DWORD),
                ("dwFileFlags", wintypes.DWORD),
                ("dwFileOS", wintypes.DWORD),
                ("dwFileType", wintypes.DWORD),
                ("dwFileSubtype", wintypes.DWORD),
                ("dwFileDateMS", wintypes.DWORD),
                ("dwFileDateLS", wintypes.DWORD),
            ]

        version_dll = ctypes.WinDLL("version", use_last_error=True)
        version_dll.GetFileVersionInfoSizeW.argtypes = [
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        version_dll.GetFileVersionInfoSizeW.restype = wintypes.DWORD
        version_dll.GetFileVersionInfoW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
        ]
        version_dll.GetFileVersionInfoW.restype = wintypes.BOOL
        version_dll.VerQueryValueW.argtypes = [
            wintypes.LPCVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.UINT),
        ]
        version_dll.VerQueryValueW.restype = wintypes.BOOL

        unused = wintypes.DWORD(0)
        size = version_dll.GetFileVersionInfoSizeW(str(executable), ctypes.byref(unused))
        if not size:
            return None

        buffer = ctypes.create_string_buffer(size)
        if not version_dll.GetFileVersionInfoW(str(executable), 0, size, buffer):
            return None

        value_pointer = wintypes.LPVOID()
        value_length = wintypes.UINT(0)
        if not version_dll.VerQueryValueW(
            buffer,
            "\\",
            ctypes.byref(value_pointer),
            ctypes.byref(value_length),
        ):
            return None

        info = ctypes.cast(value_pointer, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
        if info.dwSignature != 0xFEEF04BD:
            return None

        return ".".join(
            str(part)
            for part in (
                info.dwFileVersionMS >> 16,
                info.dwFileVersionMS & 0xFFFF,
                info.dwFileVersionLS >> 16,
                info.dwFileVersionLS & 0xFFFF,
            )
        )
    except (AttributeError, OSError, ValueError):
        return None


def _chromium_version(executable: Path) -> str | None:
    windows_version = _windows_file_version(executable)
    if windows_version:
        return windows_version

    try:
        completed = subprocess.run(
            [str(executable), "--version"],
            cwd=str(executable.parent),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        output = (completed.stdout or completed.stderr).strip()
        return output or None
    except (OSError, subprocess.SubprocessError):
        return None


def _session_profile_count() -> int:
    if not PROFILES_DIR.exists():
        return 0
    count = 0
    for profile_dir in PROFILES_DIR.iterdir():
        if not profile_dir.is_dir():
            continue
        candidates = (
            profile_dir / "Default" / "Network" / "Cookies",
            profile_dir / "Default" / "Cookies",
            profile_dir / "Default" / "Local Storage",
            profile_dir / "Default" / "IndexedDB",
            profile_dir / "Default" / "Session Storage",
        )
        if any(path.exists() for path in candidates):
            count += 1
    return count


def _database_status() -> tuple[bool, int]:
    if not DATABASE_PATH.exists():
        return True, 0
    try:
        with sqlite3.connect(DATABASE_PATH, timeout=5) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                return False, 0
            row = connection.execute("SELECT COUNT(*) FROM profiles").fetchone()
            return True, int(row[0]) if row else 0
    except sqlite3.Error:
        return False, 0


def collect_diagnostics() -> DiagnosticReport:
    ensure_runtime_directories()
    errors: list[str] = []

    writable = True
    try:
        assert_portable_root_writable()
    except PermissionError as exc:
        writable = False
        errors.append(str(exc))

    managed_paths = (
        DATA_DIR,
        PROFILES_DIR,
        DOWNLOADS_DIR,
        LOGS_DIR,
        TEMP_DIR,
        CRASH_DIR,
        DATABASE_PATH,
        CHROMIUM_DIR,
    )
    portable_paths_ok = all(is_within_base(path) for path in managed_paths)
    if not portable_paths_ok:
        errors.append("One or more managed paths escape the portable application root.")

    temp_environment_ok = all(
        Path(os.environ.get(name, "")).resolve() == TEMP_DIR.resolve()
        for name in ("TEMP", "TMP", "TMPDIR")
    )
    if not temp_environment_ok:
        errors.append("TEMP/TMP/TMPDIR are not redirected to data/temp.")

    chromium_executable: Path | None = None
    chromium_version: str | None = None
    try:
        chromium_executable = discover_chromium()
        chromium_version = _chromium_version(chromium_executable)
        if not chromium_version:
            errors.append("Chromium was found but its version could not be read.")
    except FileNotFoundError as exc:
        errors.append(str(exc))

    database_ok, profile_count = _database_status()
    if not database_ok:
        errors.append("SQLite quick_check failed or the database could not be opened.")

    return DiagnosticReport(
        app_name=APP_NAME,
        app_version=APP_VERSION,
        operating_system=f"{platform.system()} {platform.release()} ({platform.machine()})",
        python_version=sys.version.split()[0],
        python_executable=sys.executable,
        source_mode=not getattr(sys, "frozen", False),
        base_dir=str(BASE_DIR),
        data_dir=str(DATA_DIR),
        chromium_dir=str(CHROMIUM_DIR),
        chromium_executable=str(chromium_executable) if chromium_executable else None,
        chromium_version=chromium_version,
        database_path=str(DATABASE_PATH),
        database_ok=database_ok,
        portable_paths_ok=portable_paths_ok,
        writable=writable,
        temp_environment_ok=temp_environment_ok,
        profile_count=profile_count,
        session_profiles=_session_profile_count(),
        errors=tuple(errors),
    )


def report_as_text(report: DiagnosticReport) -> str:
    status = "PASS" if report.passed else "FAIL"
    lines = [
        f"{report.app_name} {report.app_version} diagnostics: {status}",
        f"OS: {report.operating_system}",
        f"Python: {report.python_version}",
        f"Python executable: {report.python_executable}",
        f"Mode: {'source' if report.source_mode else 'frozen executable'}",
        f"Portable root: {report.base_dir}",
        f"Data root: {report.data_dir}",
        f"Chromium: {report.chromium_executable or 'NOT FOUND'}",
        f"Chromium version: {report.chromium_version or 'UNKNOWN'}",
        f"Database: {'PASS' if report.database_ok else 'FAIL'} ({report.profile_count} profiles)",
        f"Portable paths: {'PASS' if report.portable_paths_ok else 'FAIL'}",
        f"Writable root: {'PASS' if report.writable else 'FAIL'}",
        f"Portable TEMP: {'PASS' if report.temp_environment_ok else 'FAIL'}",
        f"Profiles with browser session data: {report.session_profiles}",
    ]
    if report.errors:
        lines.append("Errors:")
        lines.extend(f"- {error}" for error in report.errors)
    return "\n".join(lines)


def report_as_json(report: DiagnosticReport) -> str:
    payload = asdict(report)
    payload["passed"] = report.passed
    return json.dumps(payload, indent=2, ensure_ascii=False)
