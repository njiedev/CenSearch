"""Rules, negative gates and state transitions; no real submissions or cloud writes."""

import asyncio
from datetime import timedelta
from pathlib import Path
import socket
import pytest
from censearch.case_records import CaseWorkflow, Notice
from censearch.db import Case, CrawlRun, Scan
from censearch.delivery import destination
from censearch.evidence import EvidenceStore
from censearch.notices import render
from censearch.routing import decide
from censearch.verify import Clock, classify

SAME = {
    "photo_relation": "same_photo",
    "copy_relation": "exact",
    "original_id": 1,
    "original_sha256": "a" * 64,
}
FACTS = {
    "identity_confirmed": True,
    "authorized_use": False,
    "owns_photo": True,
    "accurate": True,
    "good_faith": True,
    "authority_under_perjury": True,
    "work_description": "My original photograph",
}
CONTACT = {
    "name": "Test operator",
    "email": "operator@example.test",
    "signature": "Test operator",
    "address": "Test address",
    "phone": "555-0100",
}
RECIPIENT = {
    "id": "contact-1",
    "rung": "site",
    "channel": "http_form",
    "address": "test",
    "endpoint": "http://127.0.0.1:9999/report",
    "evidence": {"source": "unit fixture"},
}


@pytest.mark.parametrize(
    "facts,evidence,route,rule",
    [
        ({"authorized_use": True}, SAME, "leave_alone", "authorized_or_legitimate_use"),
        ({"legitimate_use": True}, SAME, "leave_alone", "authorized_or_legitimate_use"),
        ({}, SAME, "hold_for_review", "identity_not_confirmed"),
        ({"identity_confirmed": False}, SAME, "hold_for_review", "identity_not_confirmed"),
        (
            FACTS | {"intimate": True, "identifiable": True, "impersonates_me": True},
            SAME,
            "intimate_image_report",
            "attested_nonconsensual_intimate_depiction",
        ),
        (FACTS | {"impersonates_me": True}, SAME, "impersonation_report", "attested_impersonation"),
        (FACTS, SAME, "copyright_notice", "owned_verified_same_photo"),
        (
            FACTS | {"privacy_request": True},
            SAME | {"copy_relation": "uncertain", "photo_relation": "uncertain"},
            "hold_for_review",
            "unresolved_copy",
        ),
        (
            FACTS | {"privacy_request": True},
            SAME | {"photo_relation": "different_photo"},
            "privacy_request",
            "attested_privacy_request",
        ),
        (FACTS, SAME | {"photo_relation": "different_photo"}, "leave_alone", "no_attested_removal_basis"),
        (FACTS, SAME | {"original_id": None}, "leave_alone", "no_attested_removal_basis"),
        (FACTS | {"authorized_use": None}, SAME, "leave_alone", "no_attested_removal_basis"),
        (FACTS | {"owns_photo": None}, SAME, "leave_alone", "no_attested_removal_basis"),
    ],
)
def test_routing_all_rules(facts, evidence, route, rule):
    result = decide(facts, evidence)
    assert result["route"] == route
    assert result["rule_id"] == rule
    assert result["inputs"] == {"answers": facts, "evidence": evidence}


@pytest.mark.parametrize(
    "key",
    [
        "identity_confirmed",
        "owns_photo",
        "accurate",
        "good_faith",
        "authority_under_perjury",
        "work_description",
    ],
)
def test_copyright_requires_each_statement(key):
    with pytest.raises(ValueError):
        render(
            "copyright_notice",
            FACTS | {key: None},
            CONTACT,
            SAME,
            "http://localhost/a",
            "http://localhost/a.jpg",
            "site",
            "2026-10-10",
        )


@pytest.mark.parametrize("key", ["name", "email", "signature", "address", "phone"])
def test_copyright_contact_requirements(key):
    with pytest.raises(ValueError):
        render("copyright_notice", FACTS, CONTACT | {key: ""}, SAME, "page", "image", "site", "today")


def test_templates_and_no_copyright_for_different_photo():
    for route, facts in [
        ("impersonation_report", FACTS | {"impersonates_me": True}),
        ("intimate_image_report", FACTS | {"intimate": True, "identifiable": True}),
        ("privacy_request", FACTS | {"privacy_request": True}),
    ]:
        body = render(route, facts, CONTACT, SAME, "page", "image", "search", "today")
        assert "Delisting does not remove" in body
        with pytest.raises(ValueError):
            render(route, facts | {"accurate": None}, CONTACT, SAME, "page", "image", "site", "today")
    with pytest.raises(ValueError):
        render(
            "copyright_notice",
            FACTS,
            CONTACT,
            SAME | {"photo_relation": "different_photo"},
            "page",
            "image",
            "site",
            "today",
        )
    with pytest.raises(ValueError):
        render(
            "copyright_notice",
            FACTS | {"authorized_use": True},
            CONTACT,
            SAME,
            "page",
            "image",
            "site",
            "today",
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/report",
        "http://127.0.0.1.evil.com/",
        "http://2130706433/",
        "smtp://mail.example.com",
        "file:///tmp/report",
        "http://user:secret@localhost/report",
        "http://10.0.0.1/report",
    ],
)
def test_delivery_gate_refuses_external(url):
    with pytest.raises(ValueError):
        destination(url)


def test_delivery_gate_localhost_resolution(monkeypatch):
    for url in ("http://127.0.0.1/report", "smtp://localhost:8818", "http://[::1]/report"):
        assert destination(url).hostname
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args: [(None, None, None, None, ("8.8.8.8", 80))])
    with pytest.raises(ValueError, match="exclusively"):
        destination("http://localhost/report")


@pytest.mark.parametrize(
    "page,image,same,control,expected",
    [
        (200, 200, True, None, "still_present"),
        (200, 200, False, None, "replaced"),
        (200, 200, None, None, "uncertain"),
        (200, 410, None, 200, "removed"),
        (404, 404, None, 200, "removed"),
        (200, 404, None, 503, "unreachable"),
        (403, 404, None, 200, "blocked"),
        (200, 403, None, 200, "blocked"),
        (429, 200, True, None, "blocked"),
        (200, 503, None, None, "unreachable"),
        (503, 410, None, 200, "unreachable"),
    ],
)
def test_verification_classes(page, image, same, control, expected):
    assert classify(page, image, same, control) == expected


def test_clock_gate_and_nonimages():
    with pytest.raises(ValueError):
        Clock().advance(100)
    clock = Clock(True)
    before = clock.now()
    clock.advance(172800)
    assert clock.now() - before >= timedelta(hours=48)
    assert classify(200, 200, True, 200, is_image=False) == "blocked"


@pytest.fixture
def workflow_case(client, enrolled):
    store = client.app.state.store
    with store.session.begin() as session:
        run = CrawlRun(config={}, identity_version="test")
        session.add(run)
        session.flush()
        scan = Scan(
            run_id=run.id,
            page_url="http://localhost/page",
            image_url="http://localhost/image",
            identity_version="test",
            status="matched",
        )
        session.add(scan)
        session.flush()
        image = enrolled["originals"][0]
        case = Case(
            person_id=enrolled["id"],
            scan_id=scan.id,
            original_id=image["id"],
            page_url=scan.page_url,
            image_url=scan.image_url,
            match_type="both",
            band="match",
            score=0.8,
            face_band="match",
            face_score=0.8,
            copy_relation="exact",
            photo_relation="same_photo",
            evidence={"image": image},
            recipients=[RECIPIENT],
        )
        session.add(case)
        session.flush()
        case_id = case.id
    return client, case_id


def post(client, cid, action, payload=None, expected=200):
    response = client.post(f"/api/cases/{cid}/{action}", **({"json": payload} if payload is not None else {}))
    assert response.status_code == expected, response.text
    return response.json()


def prepare(client, cid):
    view = post(client, cid, "answers", {"answered_by": "Operator", "answers": FACTS, "contact": CONTACT})
    post(
        client,
        cid,
        "approve-draft",
        {"approved_by": "Operator", "revision": view["revision"], "rung": "site"},
    )
    # Unit isolation only: browser capture is separately tested in the real HTTP scenario.
    with client.app.state.store.session.begin() as session:
        session.get(CaseWorkflow, cid).bundle = {"bundle_file": {"sha256": "a" * 64}}
    return post(client, cid, "draft", {"recipient_id": "contact-1"})


def test_answers_are_individual_attributed_and_revisions_revoke(workflow_case):
    client, cid = workflow_case
    empty = client.get(f"/api/cases/{cid}/workflow").json()
    assert all(value is None for value in empty["answers"].values())
    post(client, cid, "draft", {"recipient_id": "contact-1"}, expected=422)
    post(client, cid, "send", expected=422)
    draft = prepare(client, cid)
    view = client.get(f"/api/cases/{cid}/workflow").json()
    assert len(view["attestations"]) == len(FACTS)
    assert all(row["answered_by"] == "Operator" and row["answered_at"] for row in view["attestations"])
    post(
        client,
        cid,
        "approve",
        {"notice_id": draft["id"], "sha256": "b" * 64, "approved_by": "Operator"},
        expected=422,
    )
    post(client, cid, "answers", {"answered_by": "Operator", "answers": FACTS | {"authorized_use": True}})
    post(
        client,
        cid,
        "approve",
        {"notice_id": draft["id"], "sha256": draft["sha256"], "approved_by": "Operator"},
        expected=422,
    )
    post(client, cid, "approve-draft", {"approved_by": "Operator", "revision": 2}, expected=422)


def test_approval_duplicate_send_and_escalation(workflow_case, monkeypatch):
    import censearch.workflow as module

    client, cid = workflow_case
    draft = prepare(client, cid)
    post(client, cid, "send", expected=422)
    post(
        client,
        cid,
        "approve",
        {"notice_id": draft["id"], "sha256": draft["sha256"], "approved_by": "Operator"},
    )
    monkeypatch.setattr(
        module, "send", lambda *args: {"status": "awaiting_response", "reply": {"status": "received"}}
    )
    sent = post(client, cid, "send")
    assert sent["status"] == "awaiting_response"
    post(client, cid, "send", expected=422)
    post(client, cid, "draft", {"recipient_id": "contact-1"}, expected=422)
    post(client, cid, "draft", {"recipient_id": "contact-1", "rung": "host"}, expected=422)
    post(client, cid, "answers", {"answered_by": "Operator", "answers": FACTS}, expected=422)
    monkeypatch.setattr(
        module, "check",
        lambda *args, **kwargs: {"outcome": "still_present", "source_removed": False},
    )
    client.app.state.workflow.clock.offset = 172801
    tick = client.post("/api/scheduler/tick").json()
    assert tick[0]["next_rung"] == "host"
    assert client.get(f"/api/cases/{cid}/workflow").json()["state"] == "escalation_approval_required"
    post(client, cid, "draft", {"recipient_id": "contact-1", "rung": "host"}, expected=422)
    assert len(client.get(f"/api/cases/{cid}/workflow").json()["deliveries"]) == 1


def test_reasoned_refusal_does_not_escalate(workflow_case, monkeypatch):
    import censearch.workflow as module

    client, cid = workflow_case
    draft = prepare(client, cid)
    post(
        client,
        cid,
        "approve",
        {"notice_id": draft["id"], "sha256": draft["sha256"], "approved_by": "Operator"},
    )
    monkeypatch.setattr(
        module, "send", lambda *args: {"status": "reasoned_refusal", "reply": {"reason": "Licensed use"}}
    )
    result = post(client, cid, "send")
    assert result["processed"] is True
    client.app.state.workflow.clock.offset = 1_000_000
    assert client.post("/api/scheduler/tick").json() == []
    view = client.get(f"/api/cases/{cid}/workflow").json()
    assert view["state"] == "decision_required"
    assert view["next_rung"] == "site"
    assert len(view["deliveries"]) == 1


def test_missing_evidence_refused(workflow_case):
    client, cid = workflow_case
    post(client, cid, "answers", {"answered_by": "Operator", "answers": FACTS, "contact": CONTACT})
    post(client, cid, "approve-draft", {"approved_by": "Operator", "revision": 1})
    response = post(client, cid, "draft", {"recipient_id": "contact-1"}, expected=422)
    assert "Capture" in response["error"]["message"]


def test_storage_health_requires_success(settings):
    storage = EvidenceStore(settings)
    assert storage.remote_verified is False

    class FakeS3:
        def put_object(self, **kwargs):
            raise RuntimeError("network failure")

    storage.client = FakeS3()
    with pytest.raises(RuntimeError):
        storage.put("test", "evidence.png", b"bytes")
    assert storage.remote_verified is False
    storage.client.put_object = lambda **kwargs: {"ETag": "test"}
    storage.put("test", "evidence.png", b"bytes")
    assert storage.remote_verified is True


def test_text_only_no_model_description(settings):
    from censearch.agent.describe import describe

    result = asyncio.run(describe("news", settings))
    assert result == {"status": "model_not_configured", "description": None, "advisory": True}


def test_workflow_deletion_cascades(workflow_case):
    client, cid = workflow_case
    prepare(client, cid)
    person = client.get(f"/api/cases/{cid}").json()["person_id"]
    assert client.delete("/api/people/" + person).status_code == 200
    with client.app.state.store.session() as session:
        assert session.get(CaseWorkflow, cid) is None
        assert session.query(Notice).count() == 0


def test_hash_script_and_fixture_guard():
    import importlib.util
    import bcrypt
    from unittest.mock import patch

    path = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("guard", path / "deploy/guard_photos.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    with pytest.raises(ValueError):
        guard.validate(path / "data/lfw-fixtures")
    spec = importlib.util.spec_from_file_location("hash_password", path / "scripts/hash_password.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with (
        patch.object(module.getpass, "getpass", return_value="test-only-password"),
        patch("builtins.print") as output,
    ):
        module.main()
    assert bcrypt.checkpw(b"test-only-password", output.call_args.args[0].encode())


@pytest.mark.parametrize(
    "route,field",
    [
        ("intimate_image_report", "intimate"),
        ("intimate_image_report", "identifiable"),
        ("intimate_image_report", "good_faith"),
        ("impersonation_report", "impersonates_me"),
        ("privacy_request", "privacy_request"),
    ],
)
def test_non_copyright_template_each_attestation(route, field):
    facts = FACTS | {"intimate": True, "identifiable": True, "impersonates_me": True, "privacy_request": True}
    with pytest.raises(ValueError):
        render(route, facts | {field: None}, CONTACT, SAME, "page", "image", "site", "today")


def test_http_delivery_never_follows_redirect_or_environment_proxy(monkeypatch):
    import httpx
    import censearch.delivery as module

    requests = []
    original = httpx.Client

    def transport(request):
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://example.com/do-not-send"})

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        return original(**kwargs, transport=httpx.MockTransport(transport))

    monkeypatch.setattr(module.httpx, "Client", client)
    monkeypatch.setenv("HTTP_PROXY", "http://example.com/proxy")
    result = module.send(RECIPIENT, {"body": "approved unit fixture"})
    assert result["status"] == "uncertain"
    assert len(requests) == 1 and requests[0].url.host == "127.0.0.1"


def test_clock_api_disabled(client):
    assert client.post("/api/clock/advance", json={"seconds": 100}).status_code == 422


def test_module_boundaries():
    import ast
    from censearch.config import ROOT

    for name in ("routing.py", "notices.py"):
        tree = ast.parse((ROOT / "censearch" / name).read_text())
        modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any("agent" in (name or "") for name in modules)
    for path in (ROOT / "censearch").rglob("*.py"):
        assert "ground_truth" not in path.read_text()


def test_provision_storage_reuses_scoped_remote_secret(monkeypatch, capsys):
    import importlib.util
    import json
    import sys
    from censearch.config import ROOT

    spec = importlib.util.spec_from_file_location("provision", ROOT / "deploy/provision_storage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scope = [{"region": "us-ord", "bucket_name": "test-bucket", "permissions": "read_write"}]
    existing = {
        "OBJ_BUCKET": "test-bucket",
        "OBJ_ACCESS_KEY": "test-access",
        "OBJ_SECRET_KEY": "test-secret-only",
    }
    written = []
    cli_calls = []

    def command(args, input=None):
        if input is None:
            return json.dumps(existing)
        written.append(json.loads(input))
        return ""

    def cli(*args):
        cli_calls.append(args)
        assert args[0] == "keys-list"
        return [
            {"label": "test-bucket-app", "access_key": "test-access", "limited": True, "bucket_access": scope}
        ]

    def create_bucket(label, region):
        assert (label, region) == ("test-bucket", "us-ord")
        cli_calls.append(("create_bucket", label, region))
        return {"s3_endpoint": "us-ord-10.linodeobjects.com"}

    monkeypatch.setattr(module, "create_bucket", create_bucket)
    monkeypatch.setattr(module, "command", command)
    monkeypatch.setattr(module, "cli", cli)
    monkeypatch.setattr(
        sys, "argv", ["provision", "--host", "root@test", "--ssh-key", "/test/key", "--bucket", "test-bucket"]
    )
    module.main()
    module.main()
    assert len(written) == 2 and written[0] == written[1]
    assert written[0]["OBJ_SECRET_KEY"] == "test-secret-only"
    assert "test-secret-only" not in capsys.readouterr().out
    assert all(call[0] != "keys-create" for call in cli_calls)


def test_provision_storage_creates_bucket_scoped_key(monkeypatch, capsys):
    import importlib.util
    import json
    import sys
    from censearch.config import ROOT

    spec = importlib.util.spec_from_file_location("provision_new", ROOT / "deploy/provision_storage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    written = []

    def command(args, input=None):
        if input is not None:
            written.append(json.loads(input))
        return "{}"

    def cli(*args):
        calls.append(args)
        if args[0] == "keys-list":
            return []
        assert args[0] == "keys-create"
        assert json.loads(args[args.index("--bucket_access") + 1]) == [
            {"region": "us-ord", "bucket_name": "test-bucket", "permissions": "read_write"}
        ]
        return [{"access_key": "access-fixture", "secret_key": "secret-fixture"}]

    def create_bucket(label, region):
        assert (label, region) == ("test-bucket", "us-ord")
        calls.append(("create_bucket", label, region))
        return {"s3_endpoint": "us-ord-10.linodeobjects.com"}

    monkeypatch.setattr(module, "create_bucket", create_bucket)
    monkeypatch.setattr(module, "command", command)
    monkeypatch.setattr(module, "cli", cli)
    monkeypatch.setattr(
        sys, "argv", ["provision", "--host", "root@test", "--ssh-key", "/test/key", "--bucket", "test-bucket"]
    )
    module.main()
    assert [call[0] for call in calls] == ["create_bucket", "keys-list", "keys-create"]
    assert written[0]["OBJ_SECRET_KEY"] == "secret-fixture"
    assert "secret-fixture" not in capsys.readouterr().out


def test_reply_analysis_is_advisory_only(workflow_case):
    client, cid = workflow_case
    before = client.get(f"/api/cases/{cid}/workflow").json()
    result = post(client, cid, "reply-analysis", {"text": "Licensed editorial use"})
    assert result["status"] == "model_not_configured" and result["category"] is None
    after = client.get(f"/api/cases/{cid}/workflow").json()
    for key in ("state", "decision", "next_rung", "deliveries"):
        assert before[key] == after[key]


def test_background_scheduler_uses_persisted_deadlines(workflow_case, monkeypatch):
    from datetime import datetime, timezone
    import time
    from fastapi.testclient import TestClient
    from censearch.api import create_app
    from censearch.case_records import Delivery
    import censearch.workflow as module

    client, cid = workflow_case
    notice = prepare(client, cid)
    post(
        client,
        cid,
        "approve",
        {"notice_id": notice["id"], "sha256": notice["sha256"], "approved_by": "Operator"},
    )
    monkeypatch.setattr(module, "send", lambda *args: {"status": "awaiting_response"})
    monkeypatch.setattr(
        module, "check",
        lambda *args, **kwargs: {"outcome": "still_present", "source_removed": False},
    )
    delivery = post(client, cid, "send")
    with client.app.state.store.session.begin() as session:
        session.get(Delivery, delivery["id"]).deadline = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()
    settings = client.app.state.settings.model_copy(update={"scheduler_poll": 0.1})
    with TestClient(create_app(settings)) as restarted:
        deadline = time.monotonic() + 3
        view = {}
        while time.monotonic() < deadline:
            view = restarted.get(f"/api/cases/{cid}/workflow").json()
            if view["next_rung"] == "host":
                break
            time.sleep(0.05)
        assert view["next_rung"] == "host"
        assert view["state"] == "escalation_approval_required" and len(view["deliveries"]) == 1
