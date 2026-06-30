from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

CATEGORY_ALL = "All"
CATEGORY_MAILBOX = "Mailbox"
CATEGORY_MESSAGING = "Messaging"
CATEGORY_SOCIAL = "Social Media"
CATEGORY_WEB_APPS = "Web Apps"
CATEGORY_CUSTOM = "Custom"

CATEGORIES: tuple[str, ...] = (
    CATEGORY_MAILBOX,
    CATEGORY_MESSAGING,
    CATEGORY_SOCIAL,
    CATEGORY_WEB_APPS,
    CATEGORY_CUSTOM,
)


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    name: str
    category: str
    start_url: str
    account_hint: str = "Email, username, or phone (optional)"
    custom_url: bool = False
    account_label: str = "Account"


_SERVICE_LIST: tuple[ServiceDefinition, ...] = (
    # Mailboxes
    ServiceDefinition("Gmail", CATEGORY_MAILBOX, "https://mail.google.com/", "Email address"),
    ServiceDefinition(
        "Outlook / Microsoft 365",
        CATEGORY_MAILBOX,
        "https://outlook.office.com/mail/",
        "Email address",
    ),
    ServiceDefinition("Yahoo Mail", CATEGORY_MAILBOX, "https://mail.yahoo.com/", "Email address"),
    ServiceDefinition("AOL Mail", CATEGORY_MAILBOX, "https://mail.aol.com/", "Email address"),
    ServiceDefinition("iCloud Mail", CATEGORY_MAILBOX, "https://www.icloud.com/mail/", "Apple ID email"),
    ServiceDefinition("Proton Mail", CATEGORY_MAILBOX, "https://mail.proton.me/", "Email address"),
    ServiceDefinition("Zoho Mail", CATEGORY_MAILBOX, "https://mail.zoho.com/", "Email address"),
    ServiceDefinition("Fastmail", CATEGORY_MAILBOX, "https://app.fastmail.com/", "Email address"),
    ServiceDefinition("Tuta Mail", CATEGORY_MAILBOX, "https://app.tuta.com/", "Email address"),
    ServiceDefinition("GMX Mail", CATEGORY_MAILBOX, "https://www.gmx.com/mail/", "Email address"),
    ServiceDefinition("Mail.com", CATEGORY_MAILBOX, "https://www.mail.com/", "Email address"),
    ServiceDefinition("Yandex Mail", CATEGORY_MAILBOX, "https://mail.yandex.com/", "Email address"),
    ServiceDefinition("AT&T Mail", CATEGORY_MAILBOX, "https://currently.att.yahoo.com/", "AT&T email address"),
    ServiceDefinition("Verizon Mail (AOL)", CATEGORY_MAILBOX, "https://mail.aol.com/", "Verizon/AOL email address"),
    ServiceDefinition("Xfinity Email", CATEGORY_MAILBOX, "https://connect.xfinity.com/appsuite/", "Xfinity email address"),
    ServiceDefinition("Mail.ru", CATEGORY_MAILBOX, "https://e.mail.ru/inbox/", "Email address"),
    ServiceDefinition("Custom Webmail", CATEGORY_MAILBOX, "", "Email address", custom_url=True),
    # Messaging
    ServiceDefinition("WhatsApp Web", CATEGORY_MESSAGING, "https://web.whatsapp.com/", "Phone number or label"),
    ServiceDefinition("Telegram Web", CATEGORY_MESSAGING, "https://web.telegram.org/k/", "Phone number or username"),
    ServiceDefinition("Messenger", CATEGORY_MESSAGING, "https://www.messenger.com/", "Email, phone, or username"),
    ServiceDefinition("Discord", CATEGORY_MESSAGING, "https://discord.com/app", "Email or username"),
    ServiceDefinition("Slack", CATEGORY_MESSAGING, "https://app.slack.com/client/", "Workspace or email"),
    ServiceDefinition("Microsoft Teams", CATEGORY_MESSAGING, "https://teams.microsoft.com/v2/", "Email address"),
    ServiceDefinition("Google Chat", CATEGORY_MESSAGING, "https://chat.google.com/", "Google account"),
    ServiceDefinition("Zoom Web", CATEGORY_MESSAGING, "https://app.zoom.us/wc/", "Email address"),
    ServiceDefinition("Custom Messaging", CATEGORY_MESSAGING, "", custom_url=True),
    # Social media
    ServiceDefinition("Facebook", CATEGORY_SOCIAL, "https://www.facebook.com/", "Email, phone, or profile label"),
    ServiceDefinition("Instagram", CATEGORY_SOCIAL, "https://www.instagram.com/", "Username or email"),
    ServiceDefinition("X / Twitter", CATEGORY_SOCIAL, "https://x.com/", "Username or email"),
    ServiceDefinition("LinkedIn", CATEGORY_SOCIAL, "https://www.linkedin.com/feed/", "Email address"),
    ServiceDefinition("Reddit", CATEGORY_SOCIAL, "https://www.reddit.com/", "Username or email"),
    ServiceDefinition("TikTok", CATEGORY_SOCIAL, "https://www.tiktok.com/", "Username, email, or phone"),
    ServiceDefinition("Pinterest", CATEGORY_SOCIAL, "https://www.pinterest.com/", "Email address"),
    ServiceDefinition("Threads", CATEGORY_SOCIAL, "https://www.threads.com/", "Instagram account"),
    ServiceDefinition("Bluesky", CATEGORY_SOCIAL, "https://bsky.app/", "Handle or email"),
    ServiceDefinition("Tumblr", CATEGORY_SOCIAL, "https://www.tumblr.com/dashboard", "Email address"),
    ServiceDefinition("Snapchat Web", CATEGORY_SOCIAL, "https://web.snapchat.com/", "Username or email"),
    ServiceDefinition("Mastodon", CATEGORY_SOCIAL, "https://mastodon.social/", "Handle or instance", custom_url=True),
    ServiceDefinition("Custom Social Site", CATEGORY_SOCIAL, "", custom_url=True),
    # Common web apps
    ServiceDefinition("Google Drive", CATEGORY_WEB_APPS, "https://drive.google.com/", "Google account"),
    ServiceDefinition("Google Calendar", CATEGORY_WEB_APPS, "https://calendar.google.com/", "Google account"),
    ServiceDefinition("Google Meet", CATEGORY_WEB_APPS, "https://meet.google.com/", "Google account"),
    ServiceDefinition("OneDrive", CATEGORY_WEB_APPS, "https://onedrive.live.com/", "Microsoft account"),
    ServiceDefinition("Microsoft 365", CATEGORY_WEB_APPS, "https://www.microsoft365.com/", "Microsoft account"),
    ServiceDefinition("Notion", CATEGORY_WEB_APPS, "https://www.notion.so/", "Email address"),
    ServiceDefinition("Trello", CATEGORY_WEB_APPS, "https://trello.com/", "Email address"),
    ServiceDefinition("Canva", CATEGORY_WEB_APPS, "https://www.canva.com/", "Email address"),
    ServiceDefinition("GitHub", CATEGORY_WEB_APPS, "https://github.com/", "Username or email"),
    ServiceDefinition("Dropbox", CATEGORY_WEB_APPS, "https://www.dropbox.com/home", "Email address"),
    ServiceDefinition("Google Keep", CATEGORY_WEB_APPS, "https://keep.google.com/", "Google account"),
    ServiceDefinition("ChatGPT", CATEGORY_WEB_APPS, "https://chatgpt.com/", "Email address"),
    ServiceDefinition("Custom Web App", CATEGORY_WEB_APPS, "", custom_url=True),
    # Generic custom site
    ServiceDefinition("Custom Website", CATEGORY_CUSTOM, "", custom_url=True),
)

SERVICES: "OrderedDict[str, ServiceDefinition]" = OrderedDict(
    (service.name, service) for service in _SERVICE_LIST
)


_ACCOUNT_LABEL_OVERRIDES: dict[str, str] = {
    "WhatsApp Web": "Phone / profile label",
    "Telegram Web": "Phone / username",
    "Messenger": "Email / phone / username",
    "Discord": "Email / username",
    "Slack": "Workspace / email",
    "Microsoft Teams": "Email address",
    "Google Chat": "Google account",
    "Zoom Web": "Email address",
    "Facebook": "Email / phone / label",
    "Instagram": "Username / email",
    "X / Twitter": "Username / email",
    "LinkedIn": "Email address",
    "Reddit": "Username / email",
    "TikTok": "Username / email / phone",
    "Pinterest": "Email address",
    "Threads": "Instagram account",
    "Bluesky": "Handle / email",
    "Tumblr": "Email address",
    "Snapchat Web": "Username / email",
    "Mastodon": "Handle / instance",
    "GitHub": "Username / email",
}

# Backward-compatible mapping retained for older imports/tests.
PROVIDERS: "OrderedDict[str, str]" = OrderedDict(
    (service.name, service.start_url) for service in _SERVICE_LIST
)


def service_for(name: str) -> ServiceDefinition | None:
    return SERVICES.get(name)


def services_for_category(category: str) -> tuple[ServiceDefinition, ...]:
    if category == CATEGORY_ALL:
        return _SERVICE_LIST
    return tuple(service for service in _SERVICE_LIST if service.category == category)


def service_names_for_category(category: str) -> tuple[str, ...]:
    return tuple(service.name for service in services_for_category(category))


def category_for_provider(provider: str) -> str:
    service = service_for(provider)
    return service.category if service else CATEGORY_CUSTOM


def default_url_for(provider: str) -> str:
    service = service_for(provider)
    return service.start_url if service else ""


def account_hint_for(provider: str) -> str:
    service = service_for(provider)
    return service.account_hint if service else "Email, username, or phone (optional)"


def account_label_for(provider: str) -> str:
    service = service_for(provider)
    if service is None:
        return "Account label"
    if provider in _ACCOUNT_LABEL_OVERRIDES:
        return _ACCOUNT_LABEL_OVERRIDES[provider]
    if service.account_label != "Account":
        return service.account_label
    if service.category == CATEGORY_MAILBOX:
        return "Email address"
    if service.category == CATEGORY_MESSAGING:
        return "Account / workspace"
    if service.category == CATEGORY_SOCIAL:
        return "Username / account"
    if service.category == CATEGORY_CUSTOM:
        return "Account label"
    return "Account"


def default_service_for_category(category: str) -> str:
    names = service_names_for_category(category)
    if names:
        return names[0]
    return "Custom Website"


def provider_allows_custom_url(provider: str) -> bool:
    service = service_for(provider)
    return bool(service and service.custom_url)


def validate_start_url(value: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > 2048:
        raise ValueError("Enter a valid HTTPS website URL.")
    if any(ord(character) < 32 or ord(character) == 127 for character in normalized):
        raise ValueError("Website URL contains an invalid control character.")

    parsed = urlparse(normalized)

    if parsed.scheme.lower() != "https":
        raise ValueError("Website URL must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("Enter a valid website URL.")
    if parsed.username or parsed.password:
        raise ValueError("Do not place usernames or passwords inside the URL.")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Website URL contains an invalid port.") from exc

    return normalized
