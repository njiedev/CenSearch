"""Email requests intercepted in process. No provider calls or real messages."""

import json

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from censearch import email_delivery
from censearch.case_records import Delivery
from censearch.db import Case, Person
from censearch.email_delivery import check_email, mailbox, send_email
from test_round2 import workflow_case as workflow_case
from test_round3 import await_batch, isolated_workflow, payload


RECIPIENT = {
    "id": "contact-email", "rung": "site", "rank": 1, "channel": "email",
    "address": "privacy@publisher.example", "endpoint": "mailto:privacy@publisher.example",
    "evidence": {"source": "https://publisher.example/privacy", "method": "published_email"},
}
NOTICE = {
    "route": "privacy_request", "body": "A synthetic fixed notice.",
    "contact": {"email": "owner@example.com"},
    "private_evidence": "DO_NOT_SEND", "image_bytes": "DO_NOT_SEND",
}


def enable(settings):
    settings.email_enabled = True
    settings.email_from = "requests@censearch.example"
    settings.resend_api_key = SecretStr("synthetic-key-for-tests")


def intercept(monkeypatch, handler):
    client_type = httpx.Client
    calls = []

    def handle(request):
        calls.append(request)
        return handler(request)

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False and kwargs["trust_env"] is False
        return client_type(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(email_delivery.httpx, "Client", client)
    return calls


@pytest.mark.parametrize("address", [
    "a@example.com,b@elsewhere.com", "a@example.com\r\nBcc: b@elsewhere.com",
    "Name <a@example.com>", "a@example.com?bcc=b@elsewhere.com", "a@localhost",
    "a@-invalid.com", "", "a@x.com ", "a@x.com;", "a@[127.0.0.1]",
])
def test_mailbox_rejects_multiple_addresses_headers_and_invalid_domains(address):
    with pytest.raises(ValueError):
        mailbox(address)


def test_resend_exact_text_fixed_endpoint_reply_to_and_idempotency(settings, monkeypatch):
    enable(settings)
    calls = intercept(monkeypatch, lambda request: httpx.Response(200, json={"id": "email-123"}))
    result = send_email(RECIPIENT, NOTICE, settings, "a" * 64)
    assert result == {
        "status": "awaiting_response", "transport": "resend", "http_status": 200,
        "provider_id": "email-123",
    }
    assert len(calls) == 1 and str(calls[0].url) == "https://api.resend.com/emails"
    assert calls[0].headers["Authorization"] == "Bearer synthetic-key-for-tests"
    assert calls[0].headers["Idempotency-Key"] == "censearch-notice-" + "a" * 64
    assert json.loads(calls[0].content) == {
        "from": settings.email_from, "to": [RECIPIENT["address"]],
        "reply_to": "owner@example.com", "text": NOTICE["body"],
        "subject": "Removal request: privacy request",
    }
    assert "DO_NOT_SEND" not in calls[0].content.decode()
    assert "synthetic-key" not in json.dumps(result)


@pytest.mark.parametrize("status,data,expected", [
    (401, {"message": "SECRET MUST NOT BE RECORDED"}, "failed"),
    (403, {}, "failed"), (422, {}, "failed"), (429, {}, "failed"),
    (500, {}, "uncertain"), (408, {}, "uncertain"), (409, {}, "uncertain"),
    (302, {}, "uncertain"), (200, {}, "uncertain"), (200, [], "uncertain"),
])
def test_provider_failures_never_count_as_sent_or_trigger_retry(settings, monkeypatch, status, data, expected):
    enable(settings)
    calls = intercept(monkeypatch, lambda request: httpx.Response(status, json=data))
    result = send_email(RECIPIENT, NOTICE, settings, "b" * 64)
    assert result["status"] == expected and len(calls) == 1
    assert "SECRET" not in json.dumps(result)


def test_timeout_is_uncertain_and_not_retried(settings, monkeypatch):
    enable(settings)

    def timeout(request):
        raise httpx.ReadTimeout("secret provider detail", request=request)

    calls = intercept(monkeypatch, timeout)
    result = send_email(RECIPIENT, NOTICE, settings, "c" * 64)
    assert result["status"] == "uncertain" and result["may_have_been_received"]
    assert len(calls) == 1 and "secret provider" not in json.dumps(result)


@pytest.mark.parametrize("change", [
    {"endpoint": "https://attacker.example/collect"},
    {"address": "other@example.com"},
    {"evidence": {}},
    {"evidence": {"source": "file:///private", "method": "invented"}},
])
def test_recipient_gate(settings, change):
    enable(settings)
    with pytest.raises(ValueError):
        check_email(RECIPIENT | change, settings)


def setup_email_case(client, cid, monkeypatch, agent=True, fixture=False):
    workflow = client.app.state.workflow
    isolated_workflow(client, monkeypatch)
    enable(workflow.settings)
    # Synthetic request metadata only; captured evidence and outbound HTTP are stubbed.
    with workflow.store.session.begin() as session:
        case = session.get(Case, cid)
        session.get(Person, case.person_id).development_fixture = fixture
        case.page_url = "https://publisher.example/photo"
        case.image_url = "https://publisher.example/photo.jpg"
        case.evidence = {"context": {"discovery": {"draft_only": True}}}

    async def recipients(case_id):
        with workflow.store.session.begin() as session:
            session.get(Case, case_id).recipients = [RECIPIENT]
        return {"recipients": [RECIPIENT]}

    async def decision(*args):
        return {
            "route": "privacy_request", "label": "Privacy request", "reason": "Synthetic review",
            "source": "agent" if agent else "rule_fallback",
            "model_status": "completed" if agent else "model_error",
            "inputs": {"evidence": {}},
        }

    monkeypatch.setattr(workflow, "recipients", recipients)
    monkeypatch.setattr("censearch.batches.pick_route", decision)
    return workflow


def test_auto_batch_records_exact_notice_and_never_sends_twice(workflow_case, monkeypatch):
    client, cid = workflow_case
    setup_email_case(client, cid, monkeypatch)
    calls = intercept(monkeypatch, lambda request: httpx.Response(200, json={"id": "provider-1"}))
    response = client.post("/api/batches", json=payload([cid]) | {"mode": "send"})
    assert response.status_code == 202
    batch = await_batch(client, response.json()["id"])
    assert batch["phase"] == "done" and batch["items"][0]["status"] == "sent"
    view = client.get(f"/api/cases/{cid}/workflow").json()
    assert json.loads(calls[0].content)["text"] == view["notices"][0]["payload"]["body"]
    assert view["deliveries"][0]["response"]["provider_id"] == "provider-1"
    assert view["deliveries"][0]["status"] == "awaiting_response"
    assert client.post(f"/api/cases/{cid}/send").status_code == 422
    second = client.post("/api/batches", json=payload([cid]))
    assert await_batch(client, second.json()["id"])["items"][0]["status"] == "failed"
    assert len(calls) == 1


@pytest.mark.parametrize("change,expected", [
    ("disabled", "drafted_not_sent"), ("unconfigured", "drafted_not_sent"),
    ("fixture", "drafted_not_sent"), ("fallback", "held_for_review"),
    ("possible", "drafted_not_sent"),
])
def test_auto_email_stops_before_transport(workflow_case, monkeypatch, change, expected):
    client, cid = workflow_case
    workflow = setup_email_case(client, cid, monkeypatch, agent=change != "fallback", fixture=change == "fixture")
    if change == "disabled":
        workflow.settings.email_enabled = False
    elif change == "unconfigured":
        workflow.settings.resend_api_key = SecretStr("")
    elif change == "possible":
        with workflow.store.session.begin() as session:
            case = session.get(Case, cid)
            case.band = "possible"
    calls = intercept(monkeypatch, lambda request: pytest.fail("Unexpected email transport"))
    response = client.post("/api/batches", json=payload([cid]))
    batch = await_batch(client, response.json()["id"])
    assert batch["items"][0]["status"] == expected and not calls
    with workflow.store.session() as session:
        assert session.scalar(select(Delivery)) is None


@pytest.mark.parametrize("score,expected", [(87.99, "drafted_not_sent"), (88, "sent"), (90, "sent"), (99, "sent"), (101, "drafted_not_sent")])
def test_facecheck_email_uses_provider_score_without_local_check(workflow_case, monkeypatch, score, expected):
    client, cid = workflow_case
    workflow = setup_email_case(client, cid, monkeypatch)
    with workflow.store.session.begin() as session:
        case = session.get(Case, cid)
        case.match_type = "facecheck"
        case.band = "possible"
        case.score = score
        case.image_url = ""
        case.original_id = None
        case.photo_relation = "uncertain"
        case.copy_relation = "uncertain"
        # Previously saved results must also work without a second image check.
        case.evidence = {"locally_verified": False}
    calls = intercept(monkeypatch, lambda request: httpx.Response(200, json={"id": "provider-facecheck"}))
    response = client.post("/api/batches", json=payload([cid]) | {"mode": "send"})
    assert response.status_code == 202
    batch = await_batch(client, response.json()["id"])
    assert batch["items"][0]["status"] == expected, batch
    assert len(calls) == (1 if expected == "sent" else 0)


def test_prepare_does_not_send_and_disable_is_rechecked(workflow_case, monkeypatch):
    client, cid = workflow_case
    workflow = setup_email_case(client, cid, monkeypatch)
    calls = intercept(monkeypatch, lambda request: pytest.fail("Unexpected email transport"))
    response = client.post("/api/batches", json=payload([cid]) | {"mode": "prepare"})
    batch = await_batch(client, response.json()["id"])
    assert batch["items"][0]["status"] == "ready_to_send" and not calls
    workflow.settings.email_enabled = False
    response = client.post(f"/api/batches/{batch['id']}/send")
    assert response.status_code == 202
    assert await_batch(client, batch["id"])["items"][0]["status"] == "failed"
    assert not calls


@pytest.mark.parametrize("status,expected", [(403, "failed"), (500, "failed")])
def test_batch_provider_failure_is_not_sent(workflow_case, monkeypatch, status, expected):
    client, cid = workflow_case
    setup_email_case(client, cid, monkeypatch)
    calls = intercept(monkeypatch, lambda request: httpx.Response(status, json={}))
    response = client.post("/api/batches", json=payload([cid]))
    batch = await_batch(client, response.json()["id"])
    assert batch["items"][0]["status"] == expected and len(calls) == 1
    assert client.post(f"/api/cases/{cid}/send").status_code == 422
    assert len(calls) == 1


def test_health_exposes_readiness_without_credentials(client, settings):
    enable(settings)
    for path in ("/api/batches/warning", "/api/health"):
        result = client.get(path).json()
        assert result["email_delivery"]["ready"] is True
        assert "synthetic-key" not in json.dumps(result)
