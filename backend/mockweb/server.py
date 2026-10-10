"""Independent loopback site administrator; state is private to this server."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(
            json.dumps(
                {"path": self.path, "user_agent": self.headers.get("User-Agent"), "message": fmt % args}
            ),
            flush=True,
        )

    def respond(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/.") or path == "/admin":
            self.send_error(404)
            return
        if path == "/policy":
            if self.server.site == "pixboard":
                body = (
                    "<h1>DMCA and privacy agent</h1>"
                    '<a href="mailto:agent@pixboard.test">Copyright and privacy contact</a>'
                )
            else:
                body = (
                    '<h1>Report content</h1><form method="post" action="/report">'
                    '<label>Notice<input name="notice"></label><button>Submit report</button></form>'
                )
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())
            return
        if path == "/receipts":
            self.respond(200, self.server.receipts)
            return
        if path == "/search-results" and self.server.site == "search":
            self.respond(200, {"delisted": self.server.delisted})
            return
        mode = self.server.modes.get(path)
        if mode in ("blocked", "unreachable", "timeout"):
            if mode == "timeout":
                time.sleep(4)
            self.send_error({"blocked": 403, "unreachable": 503, "timeout": 504}[mode])
            return
        if path in self.server.removed:
            self.send_error(410, "Content removed")
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.respond(400, {"error": "Invalid content length"})
            return
        if not 0 < length <= 200000:
            self.respond(413, {"error": "Notice size invalid"})
            return
        payload = self.rfile.read(length)
        if path == "/admin":
            if self.headers.get("X-Mock-Admin") != self.server.token:
                self.respond(403, {"error": "Admin token required"})
                return
            try:
                body = json.loads(payload)
                target = body["path"]
                action = body["action"]
                if not target.startswith("/media/") or ".." in target:
                    raise ValueError("Invalid admin target")
                if action == "removed":
                    self.server.removed.add(target)
                elif action in ("blocked", "unreachable", "timeout"):
                    self.server.modes[target] = action
                elif action == "restore":
                    self.server.modes.pop(target, None)
                    self.server.removed.discard(target)
                elif action == "ignore":
                    self.server.ignored.add(target)
                elif action == "replace":
                    from PIL import Image

                    destination = Path(self.directory) / target.lstrip("/")
                    self.server.originals[target] = destination.read_bytes()
                    Image.new("RGB", (250, 250), "steelblue").save(destination, "JPEG")
                elif action == "restore_bytes":
                    (Path(self.directory) / target.lstrip("/")).write_bytes(self.server.originals[target])
                else:
                    raise ValueError("Unknown admin operation")
                self.respond(200, {"status": action, "path": target})
            except (ValueError, KeyError) as error:
                self.respond(422, {"error": str(error)})
            return
        if path not in ("/report", "/mail-inbox"):
            self.respond(404, {"error": "Unknown channel"})
            return
        if self.server.site == "pixboard" and (
            path != "/mail-inbox" or self.headers.get("X-Mock-Mail") != self.server.token
        ):
            self.respond(405, {"error": "Use the published agent email"})
            return
        try:
            body = (
                json.loads(payload)
                if path == "/mail-inbox"
                else json.loads(parse_qs(payload.decode())["notice"][0])
            )
            route = body["route"]
            facts = body["facts"]
            contact = body["contact"]
            if route not in (
                "copyright_notice",
                "impersonation_report",
                "intimate_image_report",
                "privacy_request",
            ):
                raise ValueError("Unsupported route")
            required = ["name", "email", "signature"]
            if route == "copyright_notice":
                required.extend(["address", "phone"])
            missing = [key for key in required if not contact.get(key)]
            if route == "copyright_notice":
                missing.extend(
                    key
                    for key in (
                        "owns_photo",
                        "identity_confirmed",
                        "good_faith",
                        "accurate",
                        "authority_under_perjury",
                        "work_description",
                    )
                    if not facts.get(key)
                )
            if route == "intimate_image_report":
                missing.extend(
                    key
                    for key in ("identity_confirmed", "intimate", "identifiable", "good_faith")
                    if not facts.get(key)
                )
            if facts.get("authorized_use") is not False or facts.get("accurate") is not True:
                missing.append("explicit lack of consent and accuracy")
            if route == "impersonation_report" and facts.get("impersonates_me") is not True:
                missing.append("impersonation attestation")
            if route == "privacy_request" and facts.get("privacy_request") is not True:
                missing.append("privacy attestation")
            if missing or not body.get("body"):
                raise ValueError("Missing " + ", ".join(missing or ["body"]))
            image_url = body["image_url"]
            page_url = body["page_url"]
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.respond(422, {"status": "rejected", "reason": str(error)})
            return
        receipt = {
            "id": len(self.server.receipts) + 1,
            "route": route,
            "page_url": page_url,
            "image_url": image_url,
            "received_at": time.time(),
            "received_recipient": (self.headers.get("X-Mock-Recipient") if path == "/mail-inbox"
                                   else f"http://127.0.0.1:{self.server.server_port}{path}"),
            "received_channel": "smtp" if path == "/mail-inbox" else "http_form",
        }
        site = self.server.site
        status = 200
        if site in ("localnews", "editorial"):
            receipt.update(status="reasoned_refusal", reason="Licensed editorial use")
            status = 422
        elif site == "shadygallery" or urlsplit(image_url).path in self.server.ignored:
            receipt["status"] = "received"
            status = 202
        elif site == "search":
            self.server.delisted.append(page_url)
            receipt["status"] = "delisted"
        elif site == "host":
            customer = f"127.0.0.1:{self.server.customer_port}"
            if any(urlsplit(url).netloc != customer for url in (page_url, image_url)):
                self.respond(422, {"reason": "Not our hosted customer"})
                return
            request = Request(
                f"http://{customer}/admin",
                json.dumps({"action": "removed", "path": urlsplit(image_url).path}).encode(),
                headers={"X-Mock-Admin": self.server.token, "Content-Type": "application/json"},
            )
            with urlopen(request, timeout=5) as response:
                response.read()
            receipt["status"] = "acted"
        else:
            if urlsplit(image_url).netloc != f"127.0.0.1:{self.server.server_port}":
                self.respond(422, {"reason": "Not our image"})
                return
            self.server.removed.add(urlsplit(image_url).path)
            receipt["status"] = "acted"
        self.server.receipts.append(receipt)
        self.respond(status, receipt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--site", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--customer-port", type=int, default=8814)
    parser.add_argument("--token", default="local-mock-admin")
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=str(args.root))) as server:
        server.site = args.site
        server.customer_port = args.customer_port
        server.token = args.token
        server.removed = set()
        server.modes = {}
        server.originals = {}
        server.ignored = set()
        server.receipts = []
        server.delisted = []
        server.serve_forever()


if __name__ == "__main__":
    main()
