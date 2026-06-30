from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from epb.config import ASSETS_DIR


class TkIconWindow(Protocol):
    def iconbitmap(self, *args, **kwargs): ...
    def iconphoto(self, *args, **kwargs): ...


def icon_paths() -> tuple[Path, Path]:
    """Return the bundled Windows ICO and cross-platform PNG paths."""
    return ASSETS_DIR / "app_icon.ico", ASSETS_DIR / "app_icon_64.png"


def apply_window_icon(window: TkIconWindow) -> bool:
    """Apply the application icon to a Tk root or top-level window.

    The executable carries the same ICO resource. This runtime application is
    still needed in Python source mode and for Tk child windows. Failures are
    cosmetic and never prevent startup.
    """
    ico_path, png_path = icon_paths()
    applied = False

    if os.name == "nt" and ico_path.is_file():
        try:
            window.iconbitmap(default=str(ico_path))
            applied = True
        except Exception:
            pass

    if png_path.is_file():
        try:
            import tkinter as tk

            photo = tk.PhotoImage(file=str(png_path))
            window.iconphoto(True, photo)
            # Tk images are reference-counted by Python. Keep the image alive
            # for as long as the window exists.
            setattr(window, "_portable_account_browser_icon", photo)
            applied = True
        except Exception:
            pass

    return applied
