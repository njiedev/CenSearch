"""Text-only notices through Resend. Research never controls the provider endpoint."""

from email.headerregistry import Address
from email.errors import HeaderParseError
import re
from urllib.parse import urlsplit

import httpx


EMAIL_CHANNELS = {"email", "manual_email"}
API_URL = "https://api.resend.com/emails"


def mailbox(value):
    """Accept one bare ASCII mailbox, never lists, display names or headers."""
    if not isinstance(value, str) or not value or len(value) > 254:
        raise ValueError("Enter one valid email address")
    if not value.isascii() or any(ord(char) <= 32 or ord(char) == 127 for char in value):
        raise ValueError("Enter one valid email address")
    try:
        address = Address(addr_spec=value)
    except (ValueError, HeaderParseError) as error:
        raise ValueError("Enter one valid email address") from error
    if (
        not address.username
        or not address.domain
        or not re.fullmatch(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}", address.domain)
        or address.addr_spec != value
        or any(char in value for char in '<>,;:"[]\\')
    ):
        raise ValueError("Enter one valid email address")
    return value


def check_email(recipient, settings):
    if not settings.email_enabled:
        raise ValueError("Automatic email sending is not enabled. Request saved as a draft.")
    if not settings.email_configured:
        raise ValueError("Connect the sending account and sender address. Request saved as a draft.")
    mailbox(settings.email_from)
    address = mailbox(recipient["address"])
    if recipient.get("endpoint") != "mailto:" + address:
        raise ValueError("Email destination does not match the researched recipient")
    evidence = recipient.get("evidence") or {}
    if not evidence.get("source") or not evidence.get("method"):
        raise ValueError("Email recipient needs recorded contact evidence")
    if urlsplit(evidence["source"]).scheme not in ("http", "https"):
        raise ValueError("Email recipient needs a published source URL")


def email_status(settings):
    ready = settings.email_enabled and settings.email_configured
    if ready:
        try:
            mailbox(settings.email_from)
        except ValueError:
            ready = False
    return {
        "enabled": settings.email_enabled,
        "configured": settings.email_configured,
        "ready": ready,
        "provider": "resend",
        "demo_test_recipient": settings.demo_clock and settings.demo_resend,
    }


def send_email(recipient, payload, settings, notice_sha256):
    check_email(recipient, settings)
    reply_to = mailbox(payload["contact"]["email"])
    body = {
        "from": settings.email_from,
        "to": [recipient["address"]],
        "reply_to": reply_to,
        "subject": "Removal request: " + payload["route"].replace("_", " "),
        "text": payload["body"],
    }
    # No photos, evidence bundles, attachments, model prompts or internal paths.
    try:
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                API_URL,
                headers={
                    "Authorization": "Bearer " + settings.resend_api_key.get_secret_value(),
                    "Idempotency-Key": "censearch-notice-" + notice_sha256,
                },
                json=body,
            )
    except httpx.HTTPError as error:
        return {
            "status": "uncertain", "transport": "resend", "error": type(error).__name__,
            "may_have_been_received": True,
        }
    result = {"transport": "resend", "http_status": response.status_code}
    if 400 <= response.status_code < 500 and response.status_code not in (408, 409):
        # Provider rejection is not a reasoned refusal from a website administrator.
        return result | {"status": "failed", "error": "Email provider rejected the request"}
    try:
        data = response.json()
    except ValueError:
        data = None
    if response.is_success and isinstance(data, dict) and isinstance(data.get("id"), str) and data["id"]:
        return result | {"status": "awaiting_response", "provider_id": data["id"]}
    return result | {"status": "uncertain", "may_have_been_received": True}
