from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from epb.config import DATABASE_PATH, PROFILES_DIR
from epb.models import EmailProfile
from epb.providers import CATEGORY_CUSTOM, category_for_provider

SCHEMA_VERSION = "2"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, database_path: Path = DATABASE_PATH, profiles_dir: Path = PROFILES_DIR):
        self.database_path = Path(database_path)
        self.profiles_dir = Path(profiles_dir)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            # DELETE + FULL is slower than WAL but safer for removable drives and
            # leaves no persistent WAL sidecar after a clean transaction.
            connection.execute("PRAGMA journal_mode = DELETE")
            connection.execute("PRAGMA synchronous = FULL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Create or migrate the database without deleting existing profiles."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    email_address TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Mailbox',
                    start_url TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_opened_at TEXT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_profiles_last_opened
                ON profiles(last_opened_at DESC);
                """
            )

            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(profiles)").fetchall()
            }
            if "category" not in columns:
                connection.execute(
                    "ALTER TABLE profiles ADD COLUMN category TEXT NOT NULL DEFAULT 'Mailbox'"
                )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_profiles_category
                ON profiles(category, display_name COLLATE NOCASE)
                """
            )

            rows = connection.execute("SELECT id, provider, category FROM profiles").fetchall()
            for row in rows:
                inferred = category_for_provider(row["provider"])
                current = (row["category"] or "").strip()
                if not current or (current == "Mailbox" and inferred != "Mailbox"):
                    connection.execute(
                        "UPDATE profiles SET category = ? WHERE id = ?",
                        (inferred or CATEGORY_CUSTOM, row["id"]),
                    )

            connection.execute(
                "INSERT OR REPLACE INTO app_meta(key, value) VALUES('schema_version', ?)",
                (SCHEMA_VERSION,),
            )

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> EmailProfile:
        keys = set(row.keys())
        provider = row["provider"]
        category = row["category"] if "category" in keys else category_for_provider(provider)
        return EmailProfile(
            id=row["id"],
            display_name=row["display_name"],
            email_address=row["email_address"],
            provider=provider,
            category=category or category_for_provider(provider),
            start_url=row["start_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_opened_at=row["last_opened_at"],
        )

    def list_profiles(self) -> list[EmailProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM profiles
                ORDER BY
                    CASE WHEN last_opened_at IS NULL THEN 1 ELSE 0 END,
                    last_opened_at DESC,
                    display_name COLLATE NOCASE ASC
                """
            ).fetchall()
        return [self._row_to_profile(row) for row in rows]

    def get_profile(self, profile_id: str) -> EmailProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM profiles WHERE id = ?", (profile_id,)
            ).fetchone()
        return self._row_to_profile(row) if row else None

    def create_profile(
        self,
        display_name: str,
        email_address: str,
        provider: str,
        start_url: str,
        category: str | None = None,
    ) -> EmailProfile:
        profile_id = uuid.uuid4().hex
        now = utc_now_iso()
        normalized_category = (category or category_for_provider(provider)).strip()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO profiles(
                    id, display_name, email_address, provider, category, start_url,
                    created_at, updated_at, last_opened_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    profile_id,
                    display_name.strip(),
                    email_address.strip(),
                    provider.strip(),
                    normalized_category,
                    start_url.strip(),
                    now,
                    now,
                ),
            )
        self.profile_data_dir(profile_id).mkdir(parents=True, exist_ok=True)
        profile = self.get_profile(profile_id)
        if profile is None:
            raise RuntimeError("Profile creation failed.")
        return profile

    def update_profile(
        self,
        profile_id: str,
        display_name: str,
        email_address: str,
        provider: str,
        start_url: str,
        category: str | None = None,
    ) -> None:
        normalized_category = (category or category_for_provider(provider)).strip()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE profiles
                SET display_name = ?, email_address = ?, provider = ?, category = ?,
                    start_url = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    display_name.strip(),
                    email_address.strip(),
                    provider.strip(),
                    normalized_category,
                    start_url.strip(),
                    utc_now_iso(),
                    profile_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown profile: {profile_id}")

    def mark_opened(self, profile_id: str) -> None:
        now = utc_now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE profiles SET last_opened_at = ?, updated_at = ? WHERE id = ?",
                (now, now, profile_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown profile: {profile_id}")

    def delete_profile_record(self, profile_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
            if cursor.rowcount != 1:
                raise KeyError(f"Unknown profile: {profile_id}")

    def profile_data_dir(self, profile_id: str) -> Path:
        if len(profile_id) != 32 or any(ch not in "0123456789abcdef" for ch in profile_id):
            raise ValueError("Invalid profile identifier.")
        path = (self.profiles_dir / profile_id).resolve()
        root = self.profiles_dir.resolve()
        if root not in path.parents:
            raise ValueError("Profile path escaped the portable data root.")
        return path
