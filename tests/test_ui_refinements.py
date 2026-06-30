from epb.providers import (
    CATEGORY_ALL,
    CATEGORY_CUSTOM,
    CATEGORY_MAILBOX,
    CATEGORY_MESSAGING,
    CATEGORY_SOCIAL,
)
from epb.ui import (
    empty_state_messages,
    normalize_add_category,
    search_placeholder_visible,
)


def test_add_dialog_inherits_selected_category() -> None:
    assert normalize_add_category(CATEGORY_SOCIAL) == CATEGORY_SOCIAL
    assert normalize_add_category(CATEGORY_MESSAGING) == CATEGORY_MESSAGING
    assert normalize_add_category(CATEGORY_CUSTOM) == CATEGORY_CUSTOM


def test_add_dialog_uses_mailbox_when_all_or_invalid_is_selected() -> None:
    assert normalize_add_category(CATEGORY_ALL) == CATEGORY_MAILBOX
    assert normalize_add_category("invalid") == CATEGORY_MAILBOX


def test_empty_state_messages_reflect_group_and_search() -> None:
    assert empty_state_messages(CATEGORY_SOCIAL, "") == (
        "No Social Media profiles",
        "Click + Add to create a social media profile.",
    )
    assert empty_state_messages(CATEGORY_ALL, "gmail") == (
        "No matching profiles",
        "Try a different search term.",
    )


def test_search_placeholder_visibility() -> None:
    assert search_placeholder_visible("", False) is True
    assert search_placeholder_visible("", True) is False
    assert search_placeholder_visible("mail", False) is False
