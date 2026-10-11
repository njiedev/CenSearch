"""App workflow contracts using local fixtures and recorded simulated deliveries."""

import asyncio
import threading
import time

import pytest
from sqlalchemy import select, text

from censearch.batches import Batches
from censearch.case_records import Attestation, Batch, BatchItem, Delivery, Notice
from censearch.crawl import Crawler
from censearch.db import Case, CrawlRun, Person, Scan, Store, WhitelistDomain
from censearch.public_crawl import PublicCrawler
from censearch.whitelist import matches
from censearch.workflow_api import BatchRequest
from test_public_search import mock_site as mock_site
from test_round2 import workflow_case as workflow_case
from test_round3 import await_batch, clone, isolated_workflow, payload


def person_id(client, cid):
    return client.get(f"/api/cases/{cid}").json()["person_id"]


def put_domains(client, pid, domains):
    return client.put(f"/api/people/{pid}/whitelist", json={"domains": domains})


def prepare(client, ids):
    response = client.post("/api/batches", json=payload(ids) | {"mode": "prepare"})
    assert response.status_code == 202, response.text
    return await_batch(client, response.json()["id"])


def delivery_rows(client):
    with client.app.state.store.session() as session:
        return list(session.scalars(select(Delivery)))


def test_whitelist_normalization_matching_and_validation(client, enrolled):
    pid = enrolled["id"]
    response = put_domains(
        client,
        pid,
        [
            " HTTPS://WWW.Example.COM:443/path?x=1 ",
            "example.com",
            "LOCALHOST:8123",
            "http://127.0.0.1:9999/page",
            "[::1]:8000",
        ],
    )
    expected = {"domains": ["127.0.0.1", "::1", "example.com", "localhost"]}
    assert response.status_code == 200 and response.json() == expected
    assert client.get(f"/api/people/{pid}/whitelist").json() == expected
    for url in ("https://example.com", "https://www.example.com/a", "https://news.example.com:443"):
        assert matches(url, expected["domains"])
    for url in (
        "https://notexample.com",
        "https://example.com.evil.test",
        "http://sub.localhost",
        "http://sub.127.0.0.1",
    ):
        assert not matches(url, expected["domains"])
    assert matches("http://localhost:1234", expected["domains"])
    assert matches("http://127.0.0.1:9876", expected["domains"])
    assert matches("http://[::1]:9876", expected["domains"])
    for entry in (
        "bad host",
        "-bad.example",
        "example..com",
        "https:///",
        "",
        "a@b.com",
        "example.com:bad",
        "999.0.0.1",
        "example_.com",
        "exa\nmple.com",
        "example.com..",
    ):
        response = put_domains(client, pid, [entry])
        assert response.status_code == 422
        assert repr(entry) in response.json()["error"]["message"]
    assert client.get(f"/api/people/{pid}/whitelist").json() == expected
    assert put_domains(client, pid, ["example.com"] * 201).status_code == 422
    for path in ("whitelist", "scans"):
        assert client.get(f"/api/people/missing/{path}").status_code == 404
    assert put_domains(client, "missing", []).status_code == 404


def test_whitelist_live_cases_atomic_batch_rejection_and_delete(workflow_case):
    client, cid = workflow_case
    pid = person_id(client, cid)
    assert client.get(f"/api/cases/{cid}").json()["whitelisted"] is False
    put_domains(client, pid, ["localhost"])
    assert client.get(f"/api/cases/{cid}").json()["whitelisted"] is True
    assert client.get("/api/cases", params={"person_id": pid}).json()[0]["whitelisted"] is True
    response = client.post("/api/batches", json=payload([cid]))
    assert response.status_code == 422
    assert str(cid) in response.json()["error"]["message"]
    assert "on the whitelist" in response.json()["error"]["message"]
    with client.app.state.store.session() as session:
        assert session.scalar(select(Batch)) is None
        assert session.scalar(select(BatchItem)) is None
    put_domains(client, pid, [])
    assert client.get(f"/api/cases/{cid}").json()["whitelisted"] is False
    put_domains(client, pid, ["localhost"])
    assert client.delete(f"/api/people/{pid}").status_code == 200
    with client.app.state.store.session() as session:
        assert session.scalar(select(WhitelistDomain)) is None


def test_prepare_reviews_exact_notice_then_sends_once(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    assert batch["mode"] == "prepare" and batch["phase"] == "awaiting_review"
    assert batch["completed"] == batch["total"] == 1
    assert batch["items"][0]["status"] == "ready_to_send"
    assert not sent and not delivery_rows(client)
    case = client.get(f"/api/cases/{cid}").json()
    draft = case["drafted_request"]
    assert draft["payload"]["body"] and draft["recipient"]["id"]
    assert case["batch_outcome"]["decision"]["route"] == case["route"]
    assert draft["approved_by"] is None
    with client.app.state.store.session() as session:
        before = [row.id for row in session.scalars(select(Attestation))]
    response = client.post(f"/api/batches/{batch['id']}/send")
    assert response.status_code == 202, response.text
    assert response.json()["phase"] == "sending"
    assert response.json()["completed"] == 0
    done = await_batch(client, batch["id"])
    assert done["phase"] == "done" and done["completed"] == 1
    assert done["items"][0]["status"] == "sent"
    assert len(sent) == len(delivery_rows(client)) == 1
    assert sent[0] == draft["payload"]
    assert client.post(f"/api/batches/{batch['id']}/send").status_code == 409
    assert len(sent) == len(delivery_rows(client)) == 1
    with client.app.state.store.session() as session:
        assert [row.id for row in session.scalars(select(Attestation))] == before
        notice = session.get(Notice, draft["id"])
        assert notice.approved_by == batch["accepted_by"]


def test_send_subset_and_invalid_selection_are_atomic(workflow_case, monkeypatch):
    client, cid = workflow_case
    other = clone(client, cid)
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid, other])
    endpoint = f"/api/batches/{batch['id']}/send"
    assert client.post(endpoint, json={"case_ids": [cid, 999999]}).status_code == 422
    assert client.get(f"/api/batches/{batch['id']}").json()["phase"] == "awaiting_review"
    assert not sent and not delivery_rows(client)
    assert client.post(endpoint, json={"case_ids": [cid]}).status_code == 202
    done = await_batch(client, batch["id"])
    assert done["phase"] == "done" and done["completed"] == 2
    assert [item["status"] for item in done["items"]] == ["sent", "drafted_not_sent"]
    assert done["items"][1]["reason"] == "Not sent. You left this one out."
    assert len(sent) == len(delivery_rows(client)) == 1
    assert client.post("/api/batches/missing/send").status_code == 404


def test_whitelisted_after_prepare_is_never_delivered(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    put_domains(client, person_id(client, cid), ["localhost"])
    assert client.post(f"/api/batches/{batch['id']}/send").status_code == 202
    done = await_batch(client, batch["id"])
    assert done["phase"] == "done"
    assert done["items"][0]["status"] == "left_alone"
    assert done["items"][0]["reason"] == "Site is on your whitelist."
    assert not sent and not delivery_rows(client)


def test_whitelisted_after_create_or_during_research_is_not_drafted(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batches = client.app.state.batches
    batch = batches.create(BatchRequest(**payload([cid])))
    put_domains(client, person_id(client, cid), ["localhost"])
    asyncio.run(batches.run(batch["id"]))
    assert batches.view(batch["id"])["items"][0]["status"] == "left_alone"
    with client.app.state.store.session() as session:
        assert session.scalar(select(Notice)) is None
    put_domains(client, person_id(client, cid), [])
    original = client.app.state.workflow.recipients

    async def whitelist_during_lookup(case_id):
        result = await original(case_id)
        with client.app.state.store.session.begin() as session:
            case = session.get(Case, case_id)
            session.add(WhitelistDomain(person_id=case.person_id, domain="localhost"))
        return result

    monkeypatch.setattr(client.app.state.workflow, "recipients", whitelist_during_lookup)
    batch = prepare(client, [cid])
    assert batch["phase"] == "done" and batch["items"][0]["status"] == "left_alone"
    with client.app.state.store.session() as session:
        assert session.scalar(select(Notice)) is None
    assert not sent


@pytest.mark.parametrize("kind", ["external", "real_source", "manual", "held"])
def test_prepare_with_no_sendable_items_finishes(workflow_case, monkeypatch, kind):
    client, cid = workflow_case
    sent = isolated_workflow(
        client,
        monkeypatch,
        external_id=cid if kind == "external" else None,
        manual_id=cid if kind == "manual" else None,
    )
    with client.app.state.store.session.begin() as session:
        case = session.get(Case, cid)
        if kind == "real_source":
            case.evidence = case.evidence | {"context": {"discovery": {"draft_only": True}}}
        elif kind == "held":
            case.copy_relation = "uncertain"
    client.app.state.settings.allow_external_delivery = True
    batch = prepare(client, [cid])
    assert batch["phase"] == "done" and batch["completed"] == 1
    assert batch["items"][0]["status"] == (
        "held_for_review" if kind == "held" else "drafted_not_sent"
    )
    assert not sent and not delivery_rows(client)


def test_recovery_preserves_review_and_never_retries_interrupted_send(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    batches = Batches(client.app.state.workflow)
    batches.recover()
    assert batches.view(batch["id"])["phase"] == "awaiting_review"
    batches.start_send(batch["id"])
    with client.app.state.store.session.begin() as session:
        session.get(BatchItem, batch["items"][0]["id"]).status = "sending"
        session.add(
            Delivery(
                case_id=cid,
                notice_id=batch["items"][0]["notice_id"],
                rung="site",
                status="attempting",
                response={},
                sent_at="now",
                deadline="later",
            )
        )
    batches.recover()
    result = batches.view(batch["id"])
    assert result["phase"] == "done" and result["items"][0]["status"] == "failed"
    assert client.post(f"/api/batches/{batch['id']}/send").status_code == 409
    retry = client.post("/api/batches", json=payload([cid]))
    assert await_batch(client, retry.json()["id"])["items"][0]["status"] == "failed"
    assert not sent and len(delivery_rows(client)) == 1


def test_history_uses_person_run_cases_and_current_whitelist(workflow_case):
    client, cid = workflow_case
    pid = person_id(client, cid)
    other = clone(client, cid, band="possible", page_url="https://notexample.com/page")
    with client.app.state.store.session.begin() as session:
        case = session.get(Case, cid)
        case.page_url = "https://news.example.com/a"
        case.created_at = "2026-01-02T03:04:05+00:00"
        scan = session.get(Scan, case.scan_id)
        run = session.get(CrawlRun, scan.run_id)
        crawl_id = run.id
        run.config = {"seeds": ["http://localhost:8123/"]}
        run.status = "completed_with_errors"
        run.started_at = "2026-01-01T00:00:00+00:00"
        run.metrics = {"pages": 7, "analysed": 11}
        session.add(Person(id="other-person", name="Other", consent="local"))
        session.flush()
        session.add(
            CrawlRun(
                config={
                    "public_search": True,
                    "request": {
                        "person_id": pid,
                        "mode": "name_search",
                        "full_name": "Public Name",
                    },
                },
                identity_version="test",
                status="interrupted",
            )
        )
        session.add(
            CrawlRun(
                config={"public_search": True, "request": {"person_id": "other-person"}},
                identity_version="test",
                status="completed",
            )
        )
        session.add(CrawlRun(config={}, identity_version="test", status="completed"))
    clone(client, other, person_id="other-person")
    put_domains(client, pid, ["example.com"])
    rows = client.get(f"/api/people/{pid}/scans").json()
    assert len(rows) == 2
    assert rows[0]["kind"] == "public_search" and rows[0]["status"] == "failed"
    assert rows[0]["label"] == "Public Name"
    assert rows[0]["pages_fetched"] == rows[0]["images_checked"] == 0
    crawl = rows[1]
    assert crawl["run_id"] == crawl_id and crawl["label"] == "Mock web crawl"
    assert crawl["status"] == "completed"
    assert (crawl["pages_fetched"], crawl["images_checked"]) == (7, 11)
    assert (crawl["match_count"], crawl["possible_count"], crawl["whitelisted_count"]) == (1, 1, 1)
    cases = client.get("/api/cases", params={"person_id": pid, "run_id": crawl_id}).json()
    assert len(cases) == 2 and cases[0]["created_at"] == "2026-01-02T03:04:05+00:00"
    put_domains(client, pid, [])
    assert client.get(f"/api/people/{pid}/scans").json()[1]["whitelisted_count"] == 0


@pytest.mark.parametrize("public", [True, False])
def test_cancel_stops_between_fetches_keeps_cases_releases_busy(
    client, enrolled, mock_site, monkeypatch, public
):
    base, requests = mock_site
    entered, release = threading.Event(), threading.Event()
    crawler_class = PublicCrawler if public else Crawler
    original = crawler_class.analyse_image

    async def pause_after_match(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        if self.metrics["matches"]:
            entered.set()
            await asyncio.to_thread(release.wait, 5)
        return result

    monkeypatch.setattr(crawler_class, "analyse_image", pause_after_match)
    endpoint = "/api/public-searches" if public else "/api/crawls"
    urls = [base + "/copy.html", base + "/face.html"]
    body = (
        {"person_id": enrolled["id"], "supplied_urls": urls}
        if public
        else {
            "seeds": urls,
            "rendered": False,
        }
    )
    response = client.post(endpoint, json=body)
    assert response.status_code == 202, response.text
    run_id = response.json()["id"]
    try:
        assert entered.wait(4)
        response = client.post(f"{endpoint}/{run_id}/cancel")
        assert response.status_code == 202, response.text
    finally:
        release.set()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        run = client.get(f"{endpoint}/{run_id}").json()
        if run["status"] == "cancelled" and not client.get("/api/health").json()["busy"]:
            break
        time.sleep(0.01)
    assert run["status"] == "cancelled" and run["finished_at"]
    assert not client.get("/api/health").json()["busy"]
    assert "/face.html" not in [row[1] for row in requests]
    cases = client.get("/api/cases", params={"person_id": enrolled["id"], "run_id": run_id}).json()
    assert cases and all(row["band"] == "match" for row in cases)
    history = client.get(f"/api/people/{enrolled['id']}/scans").json()[0]
    assert history["run_id"] == run_id and history["status"] == "cancelled"
    assert history["match_count"] == len(cases)
    assert history["pages_fetched"] == history["images_checked"] == 1
    assert client.post(f"{endpoint}/{run_id}/cancel").status_code == 409
    assert client.post(f"{endpoint}/999999/cancel").status_code == 404


def test_existing_sqlite_is_upgraded_without_manual_migration(tmp_path):
    store = Store(tmp_path)
    with store.engine.begin() as connection:
        connection.execute(text("DROP TABLE whitelist_domains"))
        connection.execute(text("ALTER TABLE batches DROP COLUMN mode"))
        connection.execute(text("ALTER TABLE batches DROP COLUMN phase"))
        connection.execute(
            text("""INSERT INTO batches
            (id, accepted_by, accepted_at, accepted_warning, warning, contact, status)
            VALUES ('old', 'operator', 'now', 1, 'warning', '{}', 'completed')""")
        )
    store.engine.dispose()
    store = Store(tmp_path)
    try:
        with store.session() as session:
            batch = session.get(Batch, "old")
            assert batch.mode == "send" and batch.phase == "done"
            assert list(session.scalars(select(WhitelistDomain))) == []
    finally:
        store.engine.dispose()


def test_send_busy_lock_and_progress(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    entered, release = threading.Event(), threading.Event()
    original = client.app.state.workflow.send

    async def paused_send(case_id):
        entered.set()
        await asyncio.to_thread(release.wait, 5)
        return await original(case_id)

    monkeypatch.setattr(client.app.state.workflow, "send", paused_send)
    response = client.post(f"/api/batches/{batch['id']}/send", json={})
    assert response.status_code == 202
    try:
        assert entered.wait(2)
        view = client.get(f"/api/batches/{batch['id']}").json()
        assert view["phase"] == "sending" and view["completed"] == 0
        assert view["items"][0]["status"] == "sending"
        assert client.post(f"/api/batches/{batch['id']}/send").status_code == 409
        assert client.post("/api/batches", json=payload([cid])).status_code == 409
        assert not sent and not delivery_rows(client)
    finally:
        release.set()
    assert await_batch(client, batch["id"])["phase"] == "done"
    assert len(sent) == len(delivery_rows(client)) == 1


def test_empty_send_selection_leaves_all_drafts_unsent(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    batch = prepare(client, [cid])
    assert client.post(f"/api/batches/{batch['id']}/send", json={"case_ids": []}).status_code == 202
    done = await_batch(client, batch["id"])
    assert done["phase"] == "done" and done["completed"] == 1
    assert done["items"][0]["status"] == "drafted_not_sent"
    assert done["items"][0]["reason"] == "Not sent. You left this one out."
    assert not sent and not delivery_rows(client)


def test_prepare_requires_original_warning_and_default_send_finishes(workflow_case, monkeypatch):
    client, cid = workflow_case
    sent = isolated_workflow(client, monkeypatch)
    body = payload([cid]) | {"mode": "prepare", "accepted_warning": False}
    assert client.post("/api/batches", json=body).status_code == 422
    with client.app.state.store.session() as session:
        assert session.scalar(select(Batch)) is None
    batch = client.post("/api/batches", json=payload([cid])).json()
    assert batch["mode"] == "send" and batch["phase"] == "preparing"
    done = await_batch(client, batch["id"])
    assert done["phase"] == "done" and done["completed"] == 1
    assert len(sent) == len(delivery_rows(client)) == 1
