from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class EmailProfile:
    """One isolated web-account profile.

    The historical class name is retained for backward compatibility with the
    v1.0/v1.1 source API, although v1.2 supports mailboxes, messaging, social
    media, web apps, and custom HTTPS sites.
    """

    id: str
    display_name: str
    email_address: str
    provider: str
    category: str
    start_url: str
    created_at: str
    updated_at: str
    last_opened_at: Optional[str]
