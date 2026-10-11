"""Explicit demo relay: local SMTP -> Resend test recipient, with no site removal.

Only labeled fictional notice text leaves the machine. No photos or attachments.
The provider log proves API submission; its delivery event is simulated.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit

import httpx

from mockweb.mail_receiver import Handler, Server, UncertainDelivery

DISCLAIMER = (
    "CENSEARCH LOCAL DEMO — FICTIONAL COPYRIGHT SCENARIO\n"
    "This is a simulation sent to Resend's test recipient. No actual copyright "
    "ownership, infringement, or statement under penalty of perjury is asserted. "
    "All statements below belong to the fictional scenario. No photos are attached.\n\n"
)


SENDER = "onboarding@resend.dev"
RECIPIENT = "delivered+censearch-demo@resend.dev"


class Relay:
    def __init__(self, key, site, run_id, root, client=None):
        if urlsplit(site).hostname != "127.0.0.1":
            raise ValueError("The website must be literal loopback")
        self.site = site.rstrip("/")
        self.run_id, self.root = run_id, root
        root.mkdir(parents=True, exist_ok=True)
        self.client = client or httpx.Client(
            base_url="https://api.resend.com",
            headers={"Authorization": "Bearer " + key}, timeout=6,
            trust_env=False, follow_redirects=False,
        )
        self.lock = threading.Lock()

    def close(self):
        self.client.close()

    def save(self, path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2))
        temporary.replace(path)

    def send(self, payload):
        if payload.get("route") != "copyright_notice":
            raise ValueError("This demo relay only supports fictional copyright requests")
        for field, prefix in (("page_url", "/post/"), ("image_url", "/media/")):
            value = urlsplit(payload[field])
            if (f"{value.scheme}://{value.netloc}" != self.site
                    or not value.path.startswith(prefix) or ".." in value.path):
                raise ValueError("Only this local website's pages and images are accepted")
        if not isinstance(payload.get("body"), str) or len(payload["body"]) > 20000:
            raise ValueError("A bounded plain-text notice is required")
        text = DISCLAIMER + payload["body"]
        identifier = hashlib.sha256((self.run_id + text).encode()).hexdigest()
        subject = f"[CenSearch DEMO {self.run_id}] {identifier[:16]}"
        path = self.root / f"{identifier}.json"
        with self.lock:
            if path.exists():
                saved = json.loads(path.read_text())
                if saved.get("provider_id"):
                    return {"status": "received", "provider_id": saved["provider_id"],
                            "transport": "resend_demo", "recipient": RECIPIENT}
                raise UncertainDelivery("Inspect the existing uncertain attempt; do not resend")
            record = {"subject": subject, "text": text, "payload": payload, "status": "sending"}
            self.save(path, record)
            try:
                response = self.client.post("/emails", json={
                    "from": SENDER, "to": [RECIPIENT], "subject": subject, "text": text,
                }, headers={"Idempotency-Key": f"censearch-demo-{identifier}"})
                record["http_status"] = response.status_code
                if response.status_code not in (200, 201) or not response.json().get("id"):
                    record["status"] = "not_confirmed"
                    self.save(path, record)
                    raise UncertainDelivery("Provider did not confirm acceptance")
                record.update(provider_id=response.json()["id"], status="accepted")
                self.save(path, record)
            except (httpx.HTTPError, ValueError):
                record["status"] = "uncertain"
                self.save(path, record)
                raise UncertainDelivery("Provider receipt is uncertain") from None
        print(json.dumps({"event": "resend_accepted", "provider_id": record["provider_id"],
                          "recipient": RECIPIENT}), flush=True)
        return {"status": "received", "provider_id": record["provider_id"],
                "transport": "resend_demo", "recipient": RECIPIENT}
class ResendHandler(Handler):
    def deliver(self, recipient, payload):
        return json.dumps(self.server.relay.send(json.loads(payload)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--site-port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("RESEND_API_KEY", "")
    if not key:
        raise SystemExit("Resend demo relay needs RESEND_API_KEY in its private environment")
    relay = Relay(key, f"http://127.0.0.1:{args.site_port}", args.run_id, args.state_dir)
    try:
        with Server(("127.0.0.1", args.port), ResendHandler) as server:
            server.routes = {"agent@pixboard.test": "resend_demo"}
            server.relay = relay
            server.serve_forever()
    finally:
        relay.close()


if __name__ == "__main__":
    main()
