"""Specific approved notices only; delivery defaults to literal loopback targets."""

from email.message import EmailMessage
import ipaddress
import json
import smtplib
import socket
from urllib.parse import urlsplit
import httpx


def destination(url, allow_external=False):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https", "smtp")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Invalid delivery endpoint")
    if not allow_external:
        try:
            literal_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            literal_loopback = parsed.hostname == "localhost"
        if not literal_loopback:
            raise ValueError("External delivery disabled; the person sends real-site drafts themselves")
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 25)
        if not addresses or any(not ipaddress.ip_address(row[4][0]).is_loopback for row in addresses):
            raise ValueError("Destination must resolve exclusively to loopback")
    return parsed


def outcome(result):
    status = result.get("status")
    if status in ("reasoned_refusal", "rejected") and result.get("reason"):
        return "reasoned_refusal"
    if status in ("acted", "delisted", "needs_more_information"):
        return status
    # Transport acceptance / a received receipt is not an administrator's substantive reply.
    return "awaiting_response"


def send(recipient, payload, allow_external=False):
    parsed = destination(recipient["endpoint"], allow_external)
    channel = recipient["channel"]
    try:
        if channel == "smtp":
            if parsed.scheme != "smtp":
                raise ValueError("SMTP channel requires SMTP endpoint")
            message = EmailMessage()
            message["From"] = payload["contact"]["email"]
            message["To"] = recipient["address"]
            message["Subject"] = "Approved " + payload["route"] + " request"
            message.set_content(payload["body"])
            message.add_attachment(
                json.dumps(payload).encode(), maintype="application", subtype="json", filename="notice.json"
            )
            with smtplib.SMTP(parsed.hostname, parsed.port or 25, timeout=8) as client:
                client.ehlo_or_helo_if_needed()
                code, response = client.mail(payload["contact"]["email"])
                if code != 250:
                    raise smtplib.SMTPResponseException(code, response)
                code, response = client.rcpt(recipient["address"])
                if code != 250:
                    raise smtplib.SMTPResponseException(code, response)
                code, response = client.data(message.as_bytes())
                if code != 250:
                    raise smtplib.SMTPDataError(code, response)
            text = response.decode(errors="replace")
            result = json.loads(text[text.index("{") :]) if "{" in text else {}
            return {"status": outcome(result), "transport": "smtp", "code": code, "reply": result}
        if channel != "http_form" or parsed.scheme not in ("http", "https"):
            raise ValueError("Recipient requires manual delivery")
        with httpx.Client(timeout=8, follow_redirects=False, trust_env=False) as client:
            response = client.post(recipient["endpoint"], data={"notice": json.dumps(payload)})
        try:
            result = response.json()
        except ValueError:
            result = {}
        # Redirects and opaque errors require review, never another POST.
        status = outcome(result) if isinstance(result, dict) else "uncertain"
        if response.is_redirect or (response.status_code >= 400 and not result.get("reason")):
            status = "uncertain"
        return {
            "status": status,
            "transport": "http_form",
            "http_status": response.status_code,
            "reply": result,
        }
    except smtplib.SMTPDataError as error:
        try:
            result = json.loads(error.smtp_error.decode())
        except ValueError:
            result = {"reason": error.smtp_error.decode(errors="replace")[:500]}
        refused = isinstance(result, dict) and outcome(result) == "reasoned_refusal"
        return {
            "status": "reasoned_refusal" if refused else "failed",
            "transport": "smtp", "reply": result, "code": error.smtp_code,
            "may_have_been_received": False,
        }
    except (httpx.HTTPError, OSError, smtplib.SMTPException) as error:
        return {"status": "uncertain", "error": type(error).__name__, "may_have_been_received": True}
