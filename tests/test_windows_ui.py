import os

from epb.windows_ui import apply_dark_title_bar, set_process_app_user_model_id


class FakeWindow:
    def update_idletasks(self) -> None:
        pass

    def winfo_id(self) -> int:
        return 1


def test_dark_title_bar_is_safe_outside_windows() -> None:
    if os.name != "nt":
        assert apply_dark_title_bar(FakeWindow()) is False


def test_app_user_model_id_is_safe_outside_windows() -> None:
    if os.name != "nt":
        assert set_process_app_user_model_id("OpenSource.PortableAccountBrowser") is False
