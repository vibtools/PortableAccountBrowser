from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes

from epb.config import BASE_DIR, DATA_DIR

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self) -> None:
        digest = hashlib.sha256(str(BASE_DIR.resolve()).encode("utf-8")).hexdigest()[:20]
        self.name = f"Local\\EmailPortableBrowser_{digest}"
        self._handle: int | None = None
        self._lock_file = DATA_DIR / ".instance.lock"
        self._lock_fd: int | None = None

    @staticmethod
    def _windows_kernel32():
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32

    def acquire(self) -> bool:
        if os.name == "nt":
            kernel32 = self._windows_kernel32()
            ctypes.set_last_error(0)
            handle = kernel32.CreateMutexW(None, False, self.name)
            last_error = ctypes.get_last_error()
            if not handle:
                return False
            if last_error == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(handle)
                return False
            self._handle = handle
            return True

        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._lock_fd = os.open(
                self._lock_file,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
            os.write(self._lock_fd, str(os.getpid()).encode("ascii"))
            return True
        except FileExistsError:
            return False

    def release(self) -> None:
        if os.name == "nt" and self._handle:
            self._windows_kernel32().CloseHandle(self._handle)
            self._handle = None
            return

        if self._lock_fd is not None:
            os.close(self._lock_fd)
            self._lock_fd = None
            self._lock_file.unlink(missing_ok=True)
