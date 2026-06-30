from app import _safe_print


def test_safe_print_accepts_missing_windowed_console_stream() -> None:
    _safe_print("diagnostic", None)
