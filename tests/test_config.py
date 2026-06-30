from epb.config import (
    BASE_DIR,
    CHROMIUM_DIR,
    CRASH_DIR,
    DATABASE_PATH,
    DATA_DIR,
    DOWNLOADS_DIR,
    LOGS_DIR,
    PROFILES_DIR,
    TEMP_DIR,
    is_within_base,
)


def test_all_managed_paths_are_inside_portable_root() -> None:
    for path in (
        DATA_DIR,
        PROFILES_DIR,
        DOWNLOADS_DIR,
        LOGS_DIR,
        TEMP_DIR,
        CRASH_DIR,
        DATABASE_PATH,
        CHROMIUM_DIR,
    ):
        assert is_within_base(path), f"{path} escaped {BASE_DIR}"
