import json
from pathlib import Path

from epb.settings import DEFAULT_GEOMETRY, load_window_geometry, save_window_geometry


def test_window_geometry_is_saved_in_project_local_json(tmp_path: Path) -> None:
    path = tmp_path / "ui_settings.json"
    save_window_geometry("800x540+50+60", path)
    assert load_window_geometry(path) == "800x540+50+60"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["window_geometry"] == "800x540+50+60"


def test_invalid_window_geometry_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "ui_settings.json"
    path.write_text('{"window_geometry":"bad;destroy ."}', encoding="utf-8")
    assert load_window_geometry(path) == DEFAULT_GEOMETRY
