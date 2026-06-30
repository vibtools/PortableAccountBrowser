from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from epb.config import DATA_DIR

SETTINGS_PATH = DATA_DIR / "ui_settings.json"
DEFAULT_GEOMETRY = "740x480"


def load_settings(path: Path = SETTINGS_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_settings(settings: dict[str, Any], path: Path = SETTINGS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(settings, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def load_window_geometry(path: Path = SETTINGS_PATH) -> str:
    geometry = load_settings(path).get("window_geometry")
    if not isinstance(geometry, str):
        return DEFAULT_GEOMETRY
    # Accept only normal Tk geometry shapes; reject arbitrary Tcl fragments.
    import re

    if not re.fullmatch(r"\d{3,4}x\d{3,4}(?:[+-]\d{1,5}[+-]\d{1,5})?", geometry):
        return DEFAULT_GEOMETRY
    return geometry


def save_window_geometry(geometry: str, path: Path = SETTINGS_PATH) -> None:
    settings = load_settings(path)
    settings["window_geometry"] = geometry
    save_settings(settings, path)
