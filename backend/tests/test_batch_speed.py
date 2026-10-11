"""Batch concurrency, recipient provenance, shared throttling and repeated shutdown signals."""

import asyncio
from copy import deepcopy
import os
import signal
import subprocess
import sys
import threading

import httpx
import openai
import pytest

from censearch.agent.model import ChatModel, ModelLimiter, ModelRateLimitExhausted, build_model
from censearch.agent.route import pick_route
from censearch.workflow import site_origin
from test_recipient_tools import completion
from test_round2 import RECIPIENT, workflow_case as workflow_case
from test_round3 import await_batch, clone, isolated_workflow, payload


def research_result():
    return {
        "source": "strands_agent", "status": "completed", "model_status": "completed",
        "recipients": [deepcopy(RECIPIENT)], "tool_calls": [{"tool": "fetch_page"}],
        "requests": [{"url": "http://localhost/policy", "status": 200}],
        "model_metrics": {"turns": 3, "requests": 3, "rate_limit_responses": 0},
    }


def real_lookup_with_fake_research(client, monkeypatch, responder):
    from censearch.workflow import Workflow

    workflow = client.app.state.workflow
    isolated_workflow(client, monkeypatch)
    # Keep real per-case storage and provenance behavior.
    monkeypatch.setattr(workflow, "recipients", Workflow.recipients.__get__(workflow))
    monkeypatch.setattr("censearch.workflow.lookup", responder)
    return workflow


def test_site_reuse_retains_evidence_and_case_records(workflow_case, monkeypatch):
    client, cid = workflow_case
    second = clone(client, cid, page_url="http://localhost/another")
    with client.app.state.store.session.begin() as session:
        from censearch.db import Case
        session.get(Case, cid).page_url = "http://localhost/first"
    calls = []

    async def research(url, settings):
        calls.append(url)
        return research_result()

    real_lookup_with_fake_research(client, monkeypatch, research)
    result = client.post("/api/batches", json=payload([cid, second])).json()
    batch = await_batch(client, result["id"])
    assert [row["status"] for row in batch["items"]] == ["sent", "sent"]
    assert calls == ["http://localhost/first"]
    first = client.get(f"/api/cases/{cid}/workflow").json()
    other = client.get(f"/api/cases/{second}/workflow").json()
    assert first["lookup"]["reused"] is False
    assert other["lookup"]["reused"] is True
    assert other["lookup"]["source_case_id"] == cid
    assert str(cid) in other["lookup"]["reuse_reason"]
    assert other["lookup"]["source_page_url"] == "http://localhost/first"
    for key in ("recipients", "tool_calls", "requests"):
        assert first["lookup"][key] == other["lookup"][key]
    assert other["lookup"]["model_metrics"]["turns"] == 0
    assert other["lookup"]["source_model_metrics"]["turns"] == 3
    events = [row for row in other["timeline"] if row["kind"] == "recipients_researched"]
    assert len(events) == 1 and events[0]["details"]["reused"]
    assert len(other["notices"]) == len(other["deliveries"]) == 1
    # A later batch must not reuse this cache or resend these cases.
    third = clone(client, cid)
    result = client.post("/api/batches", json=payload([third])).json()
    assert await_batch(client, result["id"])["items"][0]["status"] == "sent"
    assert len(calls) == 2


@pytest.mark.parametrize("failure", ["exception", "empty", "model_error"])
def test_failed_research_retries_next_case(workflow_case, monkeypatch, failure):
    client, cid = workflow_case
    second, third = clone(client, cid), clone(client, cid)
    calls = []

    async def research(url, settings):
        calls.append(url)
        result = research_result()
        if len(calls) == 1:
            if failure == "exception":
                raise RuntimeError("First site lookup unavailable")
            if failure == "empty":
                result["recipients"] = []
            else:
                result["model_status"] = "model_error"
        return result

    real_lookup_with_fake_research(client, monkeypatch, research)
    result = client.post("/api/batches", json=payload([cid, second, third])).json()
    batch = await_batch(client, result["id"])
    assert len(calls) == 2
    assert [row["status"] for row in batch["items"]] == [
        "sent" if failure == "model_error" else "failed", "sent", "sent"
    ]
    last = client.get(f"/api/cases/{third}/workflow").json()["lookup"]
    assert last["reused"] and last["source_case_id"] == second


def test_four_site_workers_progress_and_keep_same_site_order(workflow_case, monkeypatch):
    client, cid = workflow_case
    from censearch.db import Case
    with client.app.state.store.session.begin() as session:
        session.get(Case, cid).page_url = "http://localhost:9111/one"
    same_site = clone(client, cid, page_url="http://localhost:9111/two")
    others = [clone(client, cid, page_url=f"http://localhost:{port}/one") for port in range(9112, 9116)]
    workflow = client.app.state.workflow
    isolated_workflow(client, monkeypatch)
    original_capture = workflow.capture
    entered, release = threading.Event(), threading.Event()
    active = set()
    seen = []

    async def capture(case_id):
        active.add(case_id)
        seen.append(case_id)
        if len(active) == 4:
            entered.set()
        await asyncio.to_thread(release.wait, 5)
        await original_capture(case_id)
        active.remove(case_id)

    monkeypatch.setattr(workflow, "capture", capture)
    result = client.post("/api/batches", json=payload([cid, same_site, *others])).json()
    try:
        assert entered.wait(2), "Different sites did not run concurrently"
        assert set(active) == {cid, *others[:3]}
        assert same_site not in seen and others[-1] not in seen
        progress = client.get(f"/api/batches/{result['id']}").json()
        assert progress["status"] == "running" and progress["completed"] == 0
        assert sum(row["status"] == "capturing" for row in progress["items"]) == 4
        assert client.get(f"/api/cases/{cid}/workflow").status_code == 200
        assert client.post(f"/api/cases/{cid}/recipients").status_code == 409
        assert client.post("/api/batches", json=payload([cid])).status_code == 409
    finally:
        release.set()
    assert await_batch(client, result["id"])["completed"] == 6
    assert seen.index(cid) < seen.index(same_site)


def test_origin_includes_scheme_host_and_effective_port():
    assert site_origin("http://EXAMPLE.test/a") == site_origin("http://example.test:80/b")
    assert len({site_origin(url) for url in [
        "http://localhost:9111/a", "http://localhost:9112/a",
        "https://localhost:9111/a", "http://127.0.0.1:9111/a",
    ]}) == 4


class VirtualClock:
    def __init__(self):
        self.now = 0.0
        self.waits = []

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds


def test_shared_limiter_spaces_requests_and_defers_all_callers():
    clock = VirtualClock()
    limiter = ModelLimiter(clock=clock, sleep=clock.sleep)
    starts = []

    async def call():
        await limiter.acquire()
        starts.append(clock())

    async def run():
        await asyncio.gather(*(call() for _ in range(46)))
        limiter.defer(20)
        await call()

    asyncio.run(run())
    assert starts[45] >= 60 - 1e-8
    assert all(b - a >= 60 / 45 - 1e-8 for a, b in zip(starts, starts[1:]))
    assert starts[-1] - starts[-2] >= 20 - 1e-8


@pytest.mark.parametrize("always_limited", [False, True])
def test_chat_model_retries_429_bounded_and_records_metrics(settings, always_limited):
    clock = VirtualClock()
    limiter = ModelLimiter(clock=clock, sleep=clock.sleep)
    calls = []

    def respond(request):
        calls.append(clock())
        if always_limited or len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"}, json={"error": {"message": "busy"}})
        return completion({"role": "assistant", "content": '{"route":"privacy_request","reason":"Privacy"}'})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            model = ChatModel(
                client=openai.AsyncOpenAI(api_key="test", max_retries=0, http_client=http),
                model_id="simulated", params={"stream": False}, limiter=limiter,
            )
            value = await pick_route({"page_url": "http://localhost/page"}, "", settings, model)
            return value, model

    value, model = asyncio.run(run())
    assert len(calls) == (3 if always_limited else 2)
    assert calls[1] - calls[0] >= 7
    assert model.metrics["rate_limit_responses"] == (3 if always_limited else 1)
    assert model.metrics["turns"] == 1
    assert value["source"] == ("rule_fallback" if always_limited else "agent")
    if always_limited:
        assert value["error"] == ModelRateLimitExhausted.__name__
    else:
        assert value["model_status"] == "completed"



def test_models_share_limiter_and_parallel_tools_are_optional(settings):
    from pydantic import SecretStr

    settings.openai_api_key = SecretStr("test-not-a-real-key")
    first, second = build_model(settings), build_model(settings)
    assert first.limiter is second.limiter
    messages = [{"role": "user", "content": [{"text": "Research"}]}]
    tool = {"name": "fetch_page", "description": "Read", "inputSchema": {"json": {"type": "object"}}}
    with_tools = first.format_request(messages, [tool], "Research", None)
    without_tools = second.format_request(messages, [], "Route", None)
    assert with_tools["parallel_tool_calls"] is True
    assert "parallel_tool_calls" not in without_tools
    assert "tools" not in without_tools and "tool_choice" not in without_tools


def test_cancelled_limiter_waiter_does_not_consume_a_slot():
    async def run():
        entered = asyncio.Event()

        async def wait(seconds):
            entered.set()
            await asyncio.Event().wait()

        limiter = ModelLimiter(clock=lambda: 0, sleep=wait)
        await limiter.acquire()
        task = asyncio.create_task(limiter.acquire())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert limiter.next_start == 60 / 45

    asyncio.run(run())

def test_shutdown_ignores_repeated_sigint_during_cleanup():
    # Real OS signals and child processes, no sockets or fixture photos.
    code = '''
import os, signal, subprocess, sys, time
from mockweb.run import cleanup_signals, interrupted, stop
signal.signal(signal.SIGINT, interrupted)
signal.signal(signal.SIGTERM, interrupted)
children = [subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"]) for _ in range(3)]
print("READY", flush=True)
try:
    time.sleep(30)
except KeyboardInterrupt:
    pass
finally:
    with cleanup_signals():
        for child in reversed(children):
            os.kill(os.getpid(), signal.SIGINT)
            os.kill(os.getpid(), signal.SIGTERM)
            stop(child)
print([child.poll() is not None for child in children], flush=True)
'''
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert process.stdout.readline().strip() == "READY"
        os.kill(process.pid, signal.SIGINT)
        output, _ = process.communicate(timeout=5)
        assert process.returncode == 0
        assert output.strip() == "[True, True, True]"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
