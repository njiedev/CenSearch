"""Batch gates, isolation and simulated Strands provider tests. No external I/O."""

import asyncio
import json
import time
import pytest
from sqlalchemy import select
from censearch.agent.route import pick_route, possible_action
from censearch.batches import Batches
from censearch.case_records import Attestation, Batch, BatchItem, Delivery, Notice
from censearch.db import Case, record
from test_recipient_tools import completion, simulated_model
from test_round2 import CONTACT, RECIPIENT, workflow_case as workflow_case


@pytest.mark.parametrize(
    "change,route",
    [
        ({}, "copyright_notice"),
        ({"copy_relation": "derived"}, "copyright_notice"),
        ({"copy_relation": "uncertain"}, "hold_for_review"),
        ({"original_id": None}, "hold_for_review"),
        ({"match_type": "facecheck", "score": 88, "original_id": None}, "privacy_request"),
        ({"match_type": "facecheck", "score": 87.99, "original_id": None}, "hold_for_review"),
        (
            {"photo_relation": "different_photo", "match_type": "face", "face_band": "possible"},
            "privacy_request",
        ),
    ],
)
def test_immediate_possible_action(change, route):
    result = possible_action(
        {"photo_relation": "same_photo", "copy_relation": "exact", "original_id": 1} | change
    )
    assert result["route"] == route
    assert result["source"] == "rule_fallback" and result["possible"]


@pytest.mark.parametrize(
    "answer,status,route",
    [
        (
            '{"route":"copyright_notice","reason":"Owner claim"}',
            "guard_downgraded",
            "privacy_request",
        ),
        (
            '{"route":"leave_alone","reason":"Licensed editorial context"}',
            "completed",
            "leave_alone",
        ),
        (
            '{"route":"privacy_request","reason":"Privacy only","extra":true}',
            "model_error",
            "privacy_request",
        ),
        ('{"route":"invented","reason":"No"}', "model_error", "privacy_request"),
        ('{"route":"privacy_request","reason":" "}', "model_error", "privacy_request"),
        ('{"route":"privacy_request","reason":42}', "model_error", "privacy_request"),
        ("not json", "model_error", "privacy_request"),
    ],
)
def test_simulated_route_provider_strict_and_text_only(settings, answer, status, route):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return completion({"role": "assistant", "content": answer})

    result = asyncio.run(
        pick_route(
            {
                "page_url": "http://localhost/page",
                "photo_relation": "different_photo",
                "copy_relation": "none",
                "original_id": None,
                "match_type": "face",
                "face_band": "match",
                "image_bytes": "MUST_NOT_REACH_MODEL",
                "evidence": {"private": "MUST_NOT_REACH_MODEL"},
            },
            "Untrusted page text",
            settings,
            simulated_model(respond),
        )
    )
    assert result["model_status"] == status
    assert result["route"] == route
    assert calls and "MUST_NOT_REACH_MODEL" not in json.dumps(calls)
    assert "Untrusted page text" in json.dumps(calls)
    assert result["source"] == ("agent" if status == "completed" else "rule_fallback")


def test_model_failure_falls_back(settings):
    def unavailable(request):
        raise RuntimeError("simulated provider outage")

    value = asyncio.run(
        pick_route(
            {"page_url": "http://localhost/page"}, "", settings, simulated_model(unavailable)
        )
    )
    assert value["source"] == "rule_fallback" and value["model_status"] == "model_error"


def payload(ids):
    return {
        "case_ids": ids,
        "accepted_by": "Batch operator",
        "contact": CONTACT,
        "accepted_warning": True,
    }


def await_batch(client, batch_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        response = client.get(f"/api/batches/{batch_id}")
        assert response.status_code == 200
        result = response.json()
        if result["status"] not in ("queued", "running"):
            return result
        time.sleep(0.01)
    pytest.fail("Batch did not finish")


@pytest.mark.parametrize("flag", [None, False, "true", 1])
def test_warning_refused_before_any_work(workflow_case, flag):
    client, cid = workflow_case
    body = payload([cid])
    if flag is None:
        body.pop("accepted_warning")
    else:
        body["accepted_warning"] = flag
    assert client.post("/api/batches", json=body).status_code == 422
    with client.app.state.store.session() as session:
        for model in (Batch, BatchItem, Notice, Delivery, Attestation):
            assert session.scalar(select(model)) is None


def isolated_workflow(client, monkeypatch, fail_id=None, external_id=None, manual_id=None):
    workflow = client.app.state.workflow
    sent = []

    async def capture(cid):
        with workflow.store.session.begin() as session:
            _, state = workflow.context(session, cid)
            state.bundle = {"bundle_file": {"sha256": "a" * 64}}

    async def lookup(cid):
        if cid == fail_id:
            raise RuntimeError("Simulated recipient lookup failure")
        recipient = dict(RECIPIENT, rank=1)
        if cid == external_id:
            recipient["endpoint"] = "https://external.invalid/report"
        if cid == manual_id:
            recipient["channel"] = "manual_form"
        # Lower ranked recipient appears first: rank, not list order, must win.
        rows = [dict(recipient, id="wrong", rank=10), recipient]
        with workflow.store.session.begin() as session:
            session.get(Case, cid).recipients = rows
        return {"recipients": rows}

    def send(recipient, notice, allow_external):
        assert recipient["endpoint"] == RECIPIENT["endpoint"]
        assert recipient["id"] == RECIPIENT["id"]
        sent.append(notice)
        return {"status": "acted", "transport": "simulated"}

    monkeypatch.setattr(workflow, "capture", capture)
    monkeypatch.setattr(workflow, "recipients", lookup)
    monkeypatch.setattr("censearch.workflow.send", send)
    return sent


def clone(client, cid, **changes):
    with client.app.state.store.session.begin() as session:
        values = record(session.get(Case, cid))
        values.pop("id")
        row = Case(**(values | changes))
        session.add(row)
        session.flush()
        return row.id


def test_batch_isolation_draft_gate_progress_and_attestation(workflow_case, monkeypatch):
    client, cid = workflow_case
    fail = clone(client, cid)
    external = clone(client, cid)
    manual = clone(client, cid)
    held = clone(
        client, cid, copy_relation="uncertain", photo_relation="uncertain", band="possible"
    )
    sent = isolated_workflow(
        client, monkeypatch, fail_id=fail, external_id=external, manual_id=manual
    )
    # Batch real-site gate remains in force even if the legacy setting is enabled.
    client.app.state.settings.allow_external_delivery = True
    response = client.post("/api/batches", json=payload([fail, cid, external, manual, held]))
    assert response.status_code == 202, response.text
    result = await_batch(client, response.json()["id"])
    assert result["completed"] == result["total"] == 5
    assert [item["status"] for item in result["items"]] == [
        "failed",
        "sent",
        "drafted_not_sent",
        "drafted_not_sent",
        "held_for_review",
    ]
    assert "Simulated recipient lookup failure" in result["items"][0]["reason"]
    assert "External delivery disabled" in result["items"][2]["reason"]
    assert "manual submission" in result["items"][3]["reason"]
    assert len(sent) == 1
    view = client.get(f"/api/cases/{cid}/workflow").json()
    assert view["notices"][0]["payload"]["body"] == sent[0]["body"]
    assert all(row["value"]["batch_id"] == result["id"] for row in view["attestations"])
    assert all(row["value"]["accepted_by"] == "Batch operator" for row in view["attestations"])
    assert "batch_notice_authorized" in [row["kind"] for row in view["timeline"]]
    assert "exact_notice_approved" not in [row["kind"] for row in view["timeline"]]
    assert client.get(f"/api/cases/{held}").json()["band"] == "possible"
    duplicate = client.post("/api/batches", json=payload([cid]))
    assert await_batch(client, duplicate.json()["id"])["items"][0]["status"] == "failed"
    assert len(sent) == 1


def test_simulated_copyright_downgrade_reaches_privacy_template(workflow_case, monkeypatch):
    client, cid = workflow_case
    different = clone(
        client, cid, photo_relation="different_photo", copy_relation="none", original_id=None
    )
    sent = isolated_workflow(client, monkeypatch)

    async def simulated_pick(case, text, settings):
        model = simulated_model(
            lambda request: completion(
                {
                    "role": "assistant",
                    "content": '{"route":"copyright_notice","reason":"Incorrect simulated pick"}',
                }
            )
        )
        return await pick_route(case, text, settings, model)

    monkeypatch.setattr("censearch.batches.pick_route", simulated_pick)
    response = client.post("/api/batches", json=payload([different]))
    result = await_batch(client, response.json()["id"])
    assert result["items"][0]["status"] == "sent"
    assert result["items"][0]["decision"]["model_status"] == "guard_downgraded"
    assert sent[0]["route"] == "privacy_request"
    assert "penalty of perjury" not in sent[0]["body"]


def test_poll_during_work_and_busy_gate(workflow_case, monkeypatch):
    import threading

    client, cid = workflow_case
    entered, release = threading.Event(), threading.Event()
    isolated_workflow(client, monkeypatch)
    original = client.app.state.workflow.capture

    async def slow_capture(cid):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        await original(cid)

    monkeypatch.setattr(client.app.state.workflow, "capture", slow_capture)
    response = client.post("/api/batches", json=payload([cid]))
    try:
        assert entered.wait(2)
        progress = client.get(f"/api/batches/{response.json()['id']}").json()
        assert progress["status"] == "running"
        assert progress["items"][0]["status"] == "capturing"
        assert client.post("/api/batches", json=payload([cid])).status_code == 409
        assert (
            client.delete(
                f"/api/people/{client.get('/api/cases').json()[0]['person_id']}"
            ).status_code
            == 409
        )
    finally:
        release.set()
    assert await_batch(client, response.json()["id"])["completed"] == 1


def test_restart_marks_interrupted_without_retry(workflow_case):
    from censearch.workflow_api import BatchRequest

    client, cid = workflow_case
    batches = client.app.state.batches
    batch = batches.create(BatchRequest(**payload([cid])))
    Batches(client.app.state.workflow).recover()
    result = batches.view(batch["id"])
    assert result["status"] == "interrupted"
    assert result["items"][0]["status"] == "failed"
    assert "Interrupted" in result["items"][0]["reason"]


def test_agent_leave_alone_skips_capture_and_sending(workflow_case, monkeypatch):
    client, cid = workflow_case

    async def no_capture(cid):
        pytest.fail("Leave alone must not capture, draft or send")

    async def simulated_pick(case, text, settings):
        model = simulated_model(
            lambda request: completion(
                {
                    "role": "assistant",
                    "content": '{"route":"leave_alone","reason":"Authorized use in page text"}',
                }
            )
        )
        return await pick_route(case, text, settings, model)

    monkeypatch.setattr("censearch.batches.pick_route", simulated_pick)
    monkeypatch.setattr(client.app.state.workflow, "capture", no_capture)
    response = client.post("/api/batches", json=payload([cid]))
    result = await_batch(client, response.json()["id"])
    assert result["items"][0]["status"] == "left_alone"
    assert result["items"][0]["decision"]["source"] == "agent"
    with client.app.state.store.session() as session:
        assert session.scalar(select(Notice)) is None
        assert session.scalar(select(Delivery)) is None


@pytest.mark.parametrize(
    "change,status",
    [
        ({"case_ids": []}, 422),
        ({"case_ids": [99999]}, 404),
        ({"contact": CONTACT | {"signature": " "}}, 422),
        ({"accepted_by": " "}, 422),
    ],
)
def test_invalid_batch_is_atomic(workflow_case, change, status):
    client, cid = workflow_case
    assert client.post("/api/batches", json=payload([cid]) | change).status_code == status
    with client.app.state.store.session() as session:
        assert session.scalar(select(Batch)) is None


def test_case_list_uncapped_and_deletion_cascades_batch(workflow_case, monkeypatch):
    client, cid = workflow_case
    for _ in range(55):
        clone(client, cid, band="possible")
    cases = client.get("/api/cases").json()
    assert len(cases) == 56
    assert sum(row["band"] == "possible" for row in cases) == 55
    assert all(row["possible_action"]["route"] == "copyright_notice" for row in cases)
    isolated_workflow(client, monkeypatch)
    response = client.post("/api/batches", json=payload([cid]))
    assert await_batch(client, response.json()["id"])["completed"] == 1
    assert client.delete(f"/api/people/{cases[0]['person_id']}").status_code == 200
    with client.app.state.store.session() as session:
        for model in (Batch, BatchItem, Notice, Delivery, Attestation):
            assert session.scalar(select(model)) is None
