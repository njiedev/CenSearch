"""SMTP acceptance must be checked after DATA, including final 550 responses."""

import json
import threading

import pytest

from censearch.delivery import send
from mockweb.mail_receiver import Handler, Server


@pytest.mark.parametrize("reply, expected", [
    ("Invalid notice or administrator unavailable", "failed"),
    (json.dumps({"status": "reasoned_refusal", "reason": "Licensed use"}), "reasoned_refusal"),
])
def test_final_data_rejection_is_not_acceptance(reply, expected):
    class Reject(Handler):
        def deliver(self, recipient, payload):
            return "unused"

        def reply(self, code, message):
            if code == 250 and message.startswith("Notice accepted"):
                code, message = 550, reply
            super().reply(code, message)

    result = exercise(Reject)
    assert result["status"] == expected
    assert result["code"] == 550
    assert result["may_have_been_received"] is False
    assert not result.get("provider_id")


def exercise(handler):
    with Server(("127.0.0.1", 0), handler) as server:
        server.routes = {"agent@pixboard.test": "test"}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            return send({
                "channel": "smtp", "endpoint": f"smtp://127.0.0.1:{server.server_address[1]}",
                "address": "agent@pixboard.test",
            }, {
                "route": "privacy_request", "body": "Fictional privacy request",
                "contact": {"email": "operator@example.test"},
                "page_url": "http://127.0.0.1:9511/post/0001.html",
                "image_url": "http://127.0.0.1:9511/media/0001.jpg",
            })
        finally:
            server.shutdown()
            thread.join(timeout=3)
