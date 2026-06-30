import json
from pathlib import Path

from epb.browser import BrowserManager


def test_download_preferences_stay_inside_portable_folder(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profiles" / ("a" * 32)
    download_dir = tmp_path / "downloads" / ("a" * 32)
    download_dir.mkdir(parents=True)

    BrowserManager._configure_profile_preferences(profile_dir, download_dir)

    preferences_path = profile_dir / "Default" / "Preferences"
    preferences = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert preferences["download"]["default_directory"] == str(download_dir.resolve())
    assert preferences["download"]["prompt_for_download"] is False


def test_existing_preferences_are_preserved(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    default_dir = profile_dir / "Default"
    default_dir.mkdir(parents=True)
    preferences_path = default_dir / "Preferences"
    preferences_path.write_text('{"homepage":"https://example.com"}', encoding="utf-8")

    download_dir = tmp_path / "downloads"
    download_dir.mkdir()
    BrowserManager._configure_profile_preferences(profile_dir, download_dir)

    preferences = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert preferences["homepage"] == "https://example.com"
    assert preferences["download"]["default_directory"] == str(download_dir.resolve())


def test_single_tab_startup_preferences_are_forced(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    download_dir = tmp_path / "downloads"
    download_dir.mkdir()

    BrowserManager._configure_profile_preferences(profile_dir, download_dir)

    preferences_path = profile_dir / "Default" / "Preferences"
    preferences = json.loads(preferences_path.read_text(encoding="utf-8"))
    assert preferences["session"]["restore_on_startup"] == 0
    assert preferences["session"]["startup_urls"] == []
    assert preferences["profile"]["exited_cleanly"] is True
    assert preferences["profile"]["exit_type"] == "Normal"


def test_clear_previous_tab_session_preserves_cookie_and_storage_data(
    tmp_path: Path,
) -> None:
    profile_dir = tmp_path / "profile"
    default_dir = profile_dir / "Default"
    sessions_dir = default_dir / "Sessions"
    network_dir = default_dir / "Network"
    local_storage_dir = default_dir / "Local Storage"
    indexed_db_dir = default_dir / "IndexedDB"

    sessions_dir.mkdir(parents=True)
    network_dir.mkdir(parents=True)
    local_storage_dir.mkdir(parents=True)
    indexed_db_dir.mkdir(parents=True)

    (sessions_dir / "Tabs_123").write_bytes(b"tabs")
    (default_dir / "Last Session").write_bytes(b"legacy")

    cookie_file = network_dir / "Cookies"
    storage_file = local_storage_dir / "state"
    indexed_file = indexed_db_dir / "state"
    cookie_file.write_bytes(b"cookies")
    storage_file.write_bytes(b"storage")
    indexed_file.write_bytes(b"indexed")

    BrowserManager._clear_previous_tab_session(profile_dir)

    assert not sessions_dir.exists()
    assert not (default_dir / "Last Session").exists()
    assert cookie_file.read_bytes() == b"cookies"
    assert storage_file.read_bytes() == b"storage"
    assert indexed_file.read_bytes() == b"indexed"
