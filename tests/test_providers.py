import pytest

from epb.providers import (
    CATEGORIES,
    CATEGORY_CUSTOM,
    CATEGORY_MAILBOX,
    CATEGORY_MESSAGING,
    CATEGORY_SOCIAL,
    CATEGORY_WEB_APPS,
    account_label_for,
    category_for_provider,
    default_service_for_category,
    default_url_for,
    service_names_for_category,
    services_for_category,
    validate_start_url,
)


def test_known_provider_url() -> None:
    assert default_url_for("Gmail") == "https://mail.google.com/"
    assert default_url_for("WhatsApp Web") == "https://web.whatsapp.com/"


def test_requested_service_groups_are_available() -> None:
    assert CATEGORIES == (
        CATEGORY_MAILBOX,
        CATEGORY_MESSAGING,
        CATEGORY_SOCIAL,
        CATEGORY_WEB_APPS,
        CATEGORY_CUSTOM,
    )
    assert "AOL Mail" in service_names_for_category(CATEGORY_MAILBOX)
    assert "AT&T Mail" in service_names_for_category(CATEGORY_MAILBOX)
    assert "Verizon Mail (AOL)" in service_names_for_category(CATEGORY_MAILBOX)
    assert "iCloud Mail" in service_names_for_category(CATEGORY_MAILBOX)
    assert "Telegram Web" in service_names_for_category(CATEGORY_MESSAGING)
    assert "WhatsApp Web" in service_names_for_category(CATEGORY_MESSAGING)
    assert "Facebook" in service_names_for_category(CATEGORY_SOCIAL)


def test_every_service_has_a_valid_category() -> None:
    for category in CATEGORIES:
        for service in services_for_category(category):
            assert service.category == category


def test_unknown_provider_migrates_to_custom() -> None:
    assert category_for_provider("Unknown Internal Portal") == CATEGORY_CUSTOM


def test_https_url_is_accepted() -> None:
    assert validate_start_url(" https://mail.example.com/inbox ") == (
        "https://mail.example.com/inbox"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://mail.example.com",
        "javascript:alert(1)",
        "https://user:secret@mail.example.com",
        "not-a-url",
        "https://mail.example.com\n--new-window",
        "https://mail.example.com:99999/",
        "",
    ],
)
def test_unsafe_or_invalid_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_start_url(url)


def test_dynamic_account_labels_match_service_type() -> None:
    assert account_label_for("Gmail") == "Email address"
    assert account_label_for("Telegram Web") == "Phone / username"
    assert account_label_for("WhatsApp Web") == "Phone / profile label"
    assert account_label_for("Facebook") == "Email / phone / label"
    assert account_label_for("Custom Website") == "Account label"


def test_each_category_has_a_deterministic_default_service() -> None:
    assert default_service_for_category(CATEGORY_MAILBOX) == "Gmail"
    assert default_service_for_category(CATEGORY_MESSAGING) == "WhatsApp Web"
    assert default_service_for_category(CATEGORY_SOCIAL) == "Facebook"
    assert default_service_for_category(CATEGORY_WEB_APPS) == "Google Drive"
    assert default_service_for_category(CATEGORY_CUSTOM) == "Custom Website"
