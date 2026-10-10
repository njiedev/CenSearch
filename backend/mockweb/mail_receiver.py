"""Loopback SMTP receiver forwarding JSON MIME attachments to independent admins."""

import argparse
from email import policy
from email.parser import BytesParser
import socketserver
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class Handler(socketserver.StreamRequestHandler):
    def reply(self, code, message):
        self.wfile.write(f"{code} {message}\r\n".encode())
        self.wfile.flush()

    def handle(self):
        self.connection.settimeout(20)
        self.reply(220, "mock mail ESMTP")
        sender = False
        recipient = None
        while line := self.rfile.readline(65536):
            command = line.decode(errors="replace").strip()
            upper = command.upper()
            if upper.startswith(("EHLO", "HELO")):
                self.reply(250, "localhost")
            elif upper.startswith("MAIL FROM:"):
                sender = True
                self.reply(250, "Sender accepted")
            elif upper.startswith("RCPT TO:"):
                address = command.split(":", 1)[1].strip().strip("<>").lower()
                recipient = address if address in self.server.routes else None
                self.reply(
                    250 if recipient else 550, "Recipient accepted" if recipient else "Unknown recipient"
                )
            elif upper == "DATA" and sender and recipient:
                self.reply(354, "End with dot")
                chunks = []
                size = 0
                while data := self.rfile.readline(65536):
                    if data == b".\r\n":
                        break
                    size += len(data)
                    if size > 250000:
                        self.reply(552, "Message too large")
                        return
                    chunks.append(data[1:] if data.startswith(b"..") else data)
                try:
                    message = BytesParser(policy=policy.default).parsebytes(b"".join(chunks))
                    part = next(
                        part for part in message.walk() if part.get_content_type() == "application/json"
                    )
                    request = Request(
                        self.server.routes[recipient],
                        part.get_payload(decode=True),
                        headers={"Content-Type": "application/json", "X-Mock-Mail": self.server.token,
                                 "X-Mock-Recipient": recipient},
                    )
                    with urlopen(request, timeout=5) as response:
                        result = response.read().decode()
                    self.reply(250, "Notice accepted " + result)
                except HTTPError as error:
                    self.reply(550, error.read().decode())
                except Exception:
                    self.reply(550, "Invalid notice or administrator unavailable")
                sender = False
                recipient = None
            elif upper == "RSET":
                sender = False
                recipient = None
                self.reply(250, "Reset")
            elif upper == "QUIT":
                self.reply(221, "Bye")
                break
            else:
                self.reply(502, "Unsupported command")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--site-port", type=int, required=True)
    parser.add_argument("--host-port", type=int)
    parser.add_argument("--token", default="local-mock-admin")
    args = parser.parse_args()
    with Server(("127.0.0.1", args.port), Handler) as server:
        server.routes = {"agent@pixboard.test": f"http://127.0.0.1:{args.site_port}/mail-inbox"}
        if args.host_port:
            server.routes["abuse@host.test"] = f"http://127.0.0.1:{args.host_port}/mail-inbox"
        server.token = args.token
        server.serve_forever()
