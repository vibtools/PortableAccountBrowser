from pathlib import Path

from epb.browser import build_chromium_args, session_status
from epb.models import EmailProfile


def _profile() -> EmailProfile:
    return EmailProfile(
        id="a" * 32,
        display_name="Work",
        email_address="work@example.com",
        provider="Gmail",
        category="Mailbox",
        start_url="https://mail.google.com/",
        created_at="2026-06-28T00:00:00+00:00",
        updated_at="2026-06-28T00:00:00+00:00",
        last_opened_at=None,
    )


def test_chromium_args_force_project_local_profile_cache_and_crash_paths(tmp_path: Path) -> None:
    chromium = tmp_path / "runtime" / "chromium" / "chrome.exe"
    profile_dir = tmp_path / "data" / "profiles" / ("a" * 32)
    cache_dir = profile_dir / "Cache"
    crash_dir = tmp_path / "data" / "crash" / ("a" * 32)

    args = build_chromium_args(
        chromium=chromium,
        profile=_profile(),
        profile_dir=profile_dir,
        cache_dir=cache_dir,
        crash_dir=crash_dir,
    )

    assert str(chromium) == args[0]
    assert f"--user-data-dir={profile_dir}" in args
    assert f"--disk-cache-dir={cache_dir}" in args
    assert f"--crash-dumps-dir={crash_dir}" in args
    assert "--disable-background-mode" in args
    assert "--disable-component-update" in args
    assert "--disable-infobars" in args
    assert "--disable-sync" in args
    assert args[-1] == "https://mail.google.com/"


def test_session_status_detects_cookie_database_without_reading_it(tmp_path: Path) -> None:
    profile_dir = tmp_path / "profile"
    assert session_status(profile_dir) == "New"

    preferences = profile_dir / "Default" / "Preferences"
    preferences.parent.mkdir(parents=True)
    preferences.write_text("{}", encoding="utf-8")
    assert session_status(profile_dir) == "Browser data saved"

    cookies = profile_dir / "Default" / "Network" / "Cookies"
    cookies.parent.mkdir(parents=True)
    cookies.write_bytes(b"sqlite placeholder")
    assert session_status(profile_dir) == "Cookies saved"


def test_stale_chromium_singleton_artifacts_are_removed(tmp_path: Path) -> None:
    from epb.browser import BrowserManager

    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "SingletonLock").write_text("old path", encoding="utf-8")
    (profile_dir / "SingletonCookie").mkdir()

    BrowserManager._remove_stale_profile_locks(profile_dir)

    assert not (profile_dir / "SingletonLock").exists()
    assert not (profile_dir / "SingletonCookie").exists()
