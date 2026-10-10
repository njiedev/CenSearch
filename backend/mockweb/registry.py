"""Independent mock RDAP registry. Origin ports distinguish loopback allocations."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/robots.txt":
            payload = b"User-agent: *\nAllow: /\n"
            content_type = "text/plain"
        else:
            content_type = "application/json"
            if parsed.path == "/bootstrap":
                data = {"services": [[["127.0.0.0/8"], [f"http://127.0.0.1:{self.server.server_port}"]]]}
            elif parsed.path == "/ip/127.0.0.1":
                port = parse_qs(parsed.query).get("origin_port", [""])[0]
                hosted = port == str(self.server.customer_port)
                data = {"name": "Mock loopback allocation", "entities": [], "links": []}
                if hosted:
                    data["entities"] = [
                        {
                            "roles": ["abuse"],
                            "vcardArray": ["vcard", [["email", {}, "text", "abuse@host.test"]]],
                        }
                    ]
                    data["links"] = [
                        {"rel": "abuse", "href": f"http://127.0.0.1:{self.server.host_port}/report"}
                    ]
            else:
                self.send_error(404)
                return
            payload = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--customer-port", type=int, required=True)
    parser.add_argument("--host-port", type=int, required=True)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.customer_port = args.customer_port
        server.host_port = args.host_port
        server.serve_forever()
