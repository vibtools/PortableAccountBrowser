from pathlib import Path

from epb.app_icon import apply_window_icon, icon_paths
from epb.config import (
    APP_EXECUTABLE_NAME,
    APP_USER_MODEL_ID,
    APP_VERSION,
    ASSETS_DIR,
    RESOURCE_ROOT,
)


class FakeWindow:
    def iconbitmap(self, *args, **kwargs):
        return None

    def iconphoto(self, *args, **kwargs):
        return None


def test_release_version_and_identity() -> None:
    assert APP_VERSION == "1.3.1"
    assert APP_EXECUTABLE_NAME == "PortableAccountBrowser.exe"
    assert APP_USER_MODEL_ID == "OpenSource.PortableAccountBrowser"


def test_icon_assets_are_bundled_and_valid() -> None:
    ico_path, png_path = icon_paths()
    assert ico_path == ASSETS_DIR / "app_icon.ico"
    assert png_path == ASSETS_DIR / "app_icon_64.png"
    assert ico_path.is_file()
    assert png_path.is_file()
    assert ico_path.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert png_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert RESOURCE_ROOT in ico_path.parents


def test_window_icon_application_is_failure_tolerant() -> None:
    assert apply_window_icon(FakeWindow()) in {True, False}


def test_pyinstaller_spec_contains_production_resources() -> None:
    spec_path = Path(__file__).resolve().parents[1] / "EmailPortableBrowser.spec"
    source = spec_path.read_text(encoding="utf-8")
    assert 'name="PortableAccountBrowser"' in source
    assert 'icon=str(assets_root / "app_icon.ico")' in source
    assert 'version=str(assets_root / "windows_version_info.txt")' in source
    assert 'manifest=str(assets_root / "windows_app.manifest")' in source
    assert "upx=False" in source


def test_open_source_release_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in (
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "OPEN_SOURCE.md",
        "CONTRIBUTING.md",
        "build_release.bat",
        "build_personal_portable.bat",
        "build_publish_ready.bat",
        "PRIVACY.md",
        "PUBLISHING.md",
    ):
        assert (root / name).is_file(), name
