from __future__ import annotations

import os
from typing import Protocol


class TkWindow(Protocol):
    def after(self, milliseconds: int, callback) -> str: ...

    def update_idletasks(self) -> None: ...

    def winfo_id(self) -> int: ...


def set_process_app_user_model_id(app_id: str) -> bool:
    """Assign a stable Windows taskbar identity to the current process.

    This must run before the first Tk window is created. It is safe to call in
    source mode and degrades to a no-op on non-Windows systems.
    """
    if os.name != "nt" or not app_id.strip():
        return False

    try:
        import ctypes

        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        setter = shell32.SetCurrentProcessExplicitAppUserModelID
        setter.argtypes = [ctypes.c_wchar_p]
        setter.restype = ctypes.c_long
        return setter(app_id) == 0
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def apply_dark_title_bar(window: TkWindow) -> bool:
    """Request a dark native title bar for a Tk top-level window on Windows.

    Windows 10 1809+ and Windows 11 expose the immersive dark-mode DWM
    attribute. The function intentionally degrades to a no-op when the API is
    unavailable so source mode remains compatible with other platforms.
    """
    if os.name != "nt":
        return False

    try:
        import ctypes
        from ctypes import wintypes

        window.update_idletasks()
        child_hwnd = wintypes.HWND(int(window.winfo_id()))

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND
        parent_hwnd = user32.GetParent(child_hwnd)
        hwnd = parent_hwnd or child_hwnd

        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
        dwmapi.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND,
            wintypes.DWORD,
            wintypes.LPCVOID,
            wintypes.DWORD,
        ]
        dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long

        enabled = ctypes.c_int(1)
        for attribute in (20, 19):
            result = dwmapi.DwmSetWindowAttribute(
                hwnd,
                attribute,
                ctypes.byref(enabled),
                ctypes.sizeof(enabled),
            )
            if result == 0:
                return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False

    return False


def schedule_dark_title_bar(window: TkWindow, delay_ms: int = 25) -> None:
    """Apply the native dark title bar after Tk creates the real HWND."""

    def apply() -> None:
        try:
            apply_dark_title_bar(window)
        except Exception:
            # Window decoration is cosmetic and must never prevent app startup.
            pass

    try:
        window.after(delay_ms, apply)
    except Exception:
        pass
