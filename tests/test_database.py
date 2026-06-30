import sqlite3
from pathlib import Path

from epb.database import Database


def test_profile_crud_with_category(tmp_path: Path) -> None:
    database = Database(
        database_path=tmp_path / "profiles.sqlite3",
        profiles_dir=tmp_path / "profiles",
    )
    database.initialize()

    profile = database.create_profile(
        display_name="Work",
        email_address="work@example.com",
        provider="Custom Webmail",
        category="Mailbox",
        start_url="https://mail.example.com/",
    )

    assert database.get_profile(profile.id) is not None
    assert database.profile_data_dir(profile.id).is_dir()
    assert len(database.list_profiles()) == 1
    assert profile.category == "Mailbox"

    database.update_profile(
        profile.id,
        display_name="Work Updated",
        email_address="work@example.com",
        provider="Slack",
        category="Messaging",
        start_url="https://app.slack.com/client/",
    )
    updated = database.get_profile(profile.id)
    assert updated is not None
    assert updated.display_name == "Work Updated"
    assert updated.category == "Messaging"

    database.mark_opened(profile.id)
    opened = database.get_profile(profile.id)
    assert opened is not None
    assert opened.last_opened_at is not None

    database.delete_profile_record(profile.id)
    assert database.get_profile(profile.id) is None


def test_v1_database_migrates_without_losing_profiles(tmp_path: Path) -> None:
    database_path = tmp_path / "profiles.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE profiles (
                id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                email_address TEXT NOT NULL,
                provider TEXT NOT NULL,
                start_url TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_opened_at TEXT NULL
            );
            INSERT INTO profiles VALUES (
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                'My Telegram',
                '+8801',
                'Telegram Web',
                'https://web.telegram.org/k/',
                '2026-06-28T00:00:00+00:00',
                '2026-06-28T00:00:00+00:00',
                NULL
            );
            """
        )

    database = Database(database_path, tmp_path / "profiles")
    database.initialize()
    profile = database.get_profile("a" * 32)

    assert profile is not None
    assert profile.display_name == "My Telegram"
    assert profile.category == "Messaging"
    with sqlite3.connect(database_path) as connection:
        version = connection.execute(
            "SELECT value FROM app_meta WHERE key = 'schema_version'"
        ).fetchone()
    assert version == ("2",)


def test_profile_id_rejects_path_traversal(tmp_path: Path) -> None:
    database = Database(tmp_path / "db.sqlite3", tmp_path / "profiles")
    try:
        database.profile_data_dir("../escape")
    except ValueError:
        pass
    else:
        raise AssertionError("Path traversal identifier should be rejected")
