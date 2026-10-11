"""No external sends: verify the explicit provider-test relay's boundaries."""

import json

import httpx
import pytest

from mockweb.mail_receiver import UncertainDelivery
from mockweb.resend_demo import DISCLAIMER, RECIPIENT, Relay


def relay(tmp_path, handler):
    client = httpx.Client(base_url="https://api.resend.com", transport=httpx.MockTransport(handler))
    return Relay("synthetic", "http://127.0.0.1:9511", "test-run", tmp_path, client)


def notice():
    return {"route": "copyright_notice", "page_url": "http://127.0.0.1:9511/post/0001.html",
            "image_url": "http://127.0.0.1:9511/media/0001.jpg", "body": "Fictional fixed notice",
            "evidence": {"private_path": "must-not-be-uploaded"}}


def test_test_recipient_text_only_and_persistent_deduplication(tmp_path):
    requests = []

    def accept(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "provider-demo-id"})

    demo = relay(tmp_path, accept)
    first = demo.send(notice())
    demo.close()
    restarted = relay(tmp_path, accept)
    assert restarted.send(notice()) == first
    assert len(requests) == 1
    sent = json.loads(requests[0].content)
    assert sent["to"] == [RECIPIENT]
    assert sent["text"] == DISCLAIMER + notice()["body"]
    assert set(sent) == {"from", "to", "subject", "text"}
    assert "must-not-be-uploaded" not in requests[0].content.decode()
    assert first["transport"] == "resend_demo" and first["status"] == "received"
    restarted.close()


@pytest.mark.parametrize("change", [
    {"page_url": "https://unrelated.example/post/0001.html"},
    {"image_url": "http://127.0.0.1:9512/media/0001.jpg"},
    {"route": "impersonation_report"},
])
def test_other_sites_and_routes_are_rejected(tmp_path, change):
    calls = []
    demo = relay(tmp_path, lambda request: calls.append(request))
    with pytest.raises(ValueError):
        demo.send(notice() | change)
    assert not calls
    demo.close()


@pytest.mark.parametrize("status", [401, 429, 500])
def test_provider_failures_never_claim_sent_or_retry(tmp_path, status):
    calls = []

    def reject(request):
        calls.append(request)
        return httpx.Response(status, json={"error": "synthetic"})

    demo = relay(tmp_path, reject)
    with pytest.raises(UncertainDelivery):
        demo.send(notice())
    with pytest.raises(UncertainDelivery):
        demo.send(notice())
    assert len(calls) == 1
    demo.close()
