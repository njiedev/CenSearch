"""Direct tools against recorded real responses, adversarial forms and independent HTTP mocks."""

import asyncio
import json
from pathlib import Path
from urllib.parse import urldefrag
import httpx
import openai
import pytest
from strands.models.openai import OpenAIModel
from censearch.agent import web as web_module
from censearch.agent.recipient import lookup
from censearch.agent.tools import dns_lookup, fetch_page, find_policy_pages, platform_registry, rdap_lookup
from censearch.agent.web import ReadOnlyWeb, lookup_session
from censearch.recipients import resolve
from mockweb.run import running
from mockweb.seed_round2 import seed_round2

RECORDS = Path(__file__).parent / "recordings/real"


@pytest.fixture
def replay(monkeypatch):
    manifest = json.loads((RECORDS / "manifest.json").read_text())
    requested = []

    def respond(request):
        url = str(request.url)
        row = manifest.get(url) or manifest.get(urldefrag(url)[0])
        assert row is not None, "No recorded response for " + url
        requested.append(url)
        return httpx.Response(
            row["status"], headers=row["headers"], content=(RECORDS / row["file"]).read_bytes()
        )

    # Recorded transport never opens sockets; pin DNS as recorded in the real trace.
    monkeypatch.setattr(
        web_module,
        "validate_read_url",
        lambda url: __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(url),
    )
    return httpx.MockTransport(respond), requested


@pytest.mark.parametrize(
    "url,ip,abuse",
    [
        (
            "https://docs.github.com/en/site-policy/content-removal-policies/dmca-takedown-policy",
            "185.199.108.154",
            "abuse@github.com",
        ),
        ("https://www.wikimedia.org/", "208.80.154.224", "abuse@wikimedia.org"),
    ],
)
def test_all_tools_recorded_real_pages(replay, settings, monkeypatch, url, ip, abuse):
    from urllib.parse import urlsplit
    import censearch.agent.tools as module

    transport, requests = replay
    monkeypatch.setattr(module.socket, "getaddrinfo", lambda *args: [(2, 1, 6, "", (ip, 443))])
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": ""})(),
    )
    with lookup_session(url, settings, ReadOnlyWeb(transport=transport, delay=0)) as session:
        page = fetch_page(url)
        assert page["status"] == 200 and page["title"] and page["text"]
        assert len(page["text"]) <= 12000
        policies = find_policy_pages(url)
        assert isinstance(policies["links"], list)
        assert all(urlsplit(link["url"]).netloc == urlsplit(url).netloc for link in policies["links"])
        dns = dns_lookup(urlsplit(url).hostname)
        assert dns["addresses"] == [ip]
        rdap = rdap_lookup(ip)
        assert rdap["status"] == "completed", rdap
        assert abuse in [c["address"] for c in rdap["contacts"]]
        registry = platform_registry(urlsplit(url).hostname)
        assert registry["version"]
        assert any(c["rung"] == "search" for c in session.candidates)
        assert any("robots_allowed" in entry for entry in session.web.trace)
    assert any("robots.txt" in request for request in requests)


def test_reporting_form_must_speak_for_itself(settings):
    html = """<title>Reports</title><h1>Report copyright concerns</h1>
    <form action="/login" method="post"><input type="password"><button>Log in</button></form>
    <form action="/session" method="post"><input name="q"><button>Continue</button></form>
    <form action="/newsletter" method="post"><button>Subscribe for reports</button></form>
    <form action="/search" method="post"><input name="q"><button>Search reports</button></form>
    <form action="/report" method="post"><legend>Report abuse</legend>
    <label for="n">Notice details</label><textarea id="n" name="notice"></textarea><button>Submit report</button></form>
    <a href="/privacy">Privacy policy</a>
    <a href="data:image/png;base64,FACE_PIXELS">Photo</a><script>secret invisible text</script>"""

    def respond(request):
        return httpx.Response(
            200,
            text="User-agent: *\nAllow: /" if request.url.path == "/robots.txt" else html,
            headers={"content-type": "text/html"},
        )

    with lookup_session(
        "http://localhost/page", settings, ReadOnlyWeb(transport=httpx.MockTransport(respond), delay=0)
    ) as session:
        page = fetch_page("http://localhost/page")
        assert [form["reporting"] for form in page["forms"]] == [False, False, False, False, True]
        assert page["forms"][-1]["fields"][0]["label"] == "Notice details"
        assert len(session.candidates) == 1
        assert "secret invisible text" not in page["text"]
        assert "FACE_PIXELS" not in json.dumps(page)
        assert find_policy_pages("http://localhost/page")["links"][0]["text"] == "Privacy policy"


def test_robots_budget_and_redirects():
    requested = []

    def respond(request):
        requested.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private")
        if request.url.path == "/redirect":
            return httpx.Response(302, headers={"location": "/private"})
        return httpx.Response(200, text="ok")

    web = ReadOnlyWeb(limit=3, transport=httpx.MockTransport(respond), delay=0)
    try:
        with pytest.raises(ValueError, match="robots"):
            web.get("http://localhost/redirect")
        assert not any(url.endswith("/private") for url in requested)
        web.get("http://localhost/one")
        with pytest.raises(ValueError, match="budget"):
            web.get("http://localhost/two")
    finally:
        web.close()


def test_every_tool_against_independent_mocks(tmp_path, photo_folder, settings):
    base = 9211
    root = tmp_path / "mock"
    seed_round2(photo_folder, root, base)
    settings.smtp_relay = f"smtp://127.0.0.1:{base + 7}"
    settings.rdap_bootstrap = f"http://127.0.0.1:{base + 6}/bootstrap"
    settings.search_endpoint = f"http://127.0.0.1:{base + 5}/report"
    with running(root, base, extended=True):
        url = f"http://127.0.0.1:{base + 3}/post/0004.html"
        with lookup_session(url, settings) as session:
            assert fetch_page(url)["status"] == 200
            assert find_policy_pages(url)["links"]
            assert dns_lookup("127.0.0.1")["addresses"] == ["127.0.0.1"]
            assert rdap_lookup("127.0.0.1")["contacts"]
            assert platform_registry("127.0.0.1")["contacts"]
            assert len(session.calls) >= 5
        result = resolve(f"http://127.0.0.1:{base}/post/0001.html", settings)
        assert any(r["channel"] == "smtp" for r in result["recipients"])
        form = resolve(f"http://127.0.0.1:{base + 1}/post/0002.html", settings)
        assert any(r["channel"] == "http_form" and r["rung"] == "site" for r in form["recipients"])
        # Pixboard's independent mail administrator rejects an incomplete MIME notice with a reason.
        import smtplib
        from email.message import EmailMessage

        message = EmailMessage()
        message["From"] = "operator@example.test"
        message["To"] = "agent@pixboard.test"
        message.set_content("Incomplete local fixture")
        message.add_attachment(
            json.dumps(
                {"route": "copyright_notice", "facts": {}, "contact": {}, "body": "incomplete"}
            ).encode(),
            maintype="application",
            subtype="json",
            filename="notice.json",
        )
        with smtplib.SMTP("127.0.0.1", base + 7, timeout=3) as smtp:
            with pytest.raises(smtplib.SMTPDataError) as caught:
                smtp.send_message(message)
            assert caught.value.smtp_code == 550 and b"Missing" in caught.value.smtp_error
        # Incomplete notices are independently rejected; test goes through HTTP to actual administrator.
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                f"http://127.0.0.1:{base + 1}/report",
                data={
                    "notice": json.dumps(
                        {"route": "copyright_notice", "facts": {}, "contact": {}, "body": "incomplete"}
                    )
                },
            )
            assert response.status_code == 422 and response.json()["reason"].startswith("Missing")


def simulated_model(responder):
    client = openai.AsyncOpenAI(
        api_key="simulated-only",
        base_url="http://localhost/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(responder)),
    )
    return OpenAIModel(client=client, model_id="simulated-model", stream=False, params={"max_tokens": 1024})


def completion(message, reason="stop"):
    return httpx.Response(
        200,
        json={
            "id": "test",
            "object": "chat.completion",
            "created": 1,
            "model": "simulated-model",
            "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        },
    )


def test_recipient_strands_real_tool_wiring_simulated_provider(settings):
    requests = []

    def responder(request):
        data = json.loads(request.content)
        requests.append(data)
        assert "image_url" not in str(data)
        if len(requests) == 1:
            return completion(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_registry",
                            "type": "function",
                            "function": {
                                "name": "platform_registry",
                                "arguments": '{"hostname":"github.com"}',
                            },
                        }
                    ],
                },
                "tool_calls",
            )
        return completion(
            {
                "role": "assistant",
                "content": json.dumps(
                    {"ranked_contact_ids": ["contact-1", "contact-2"], "summary": "Registry only"}
                ),
            }
        )

    result = asyncio.run(lookup("https://github.com/example", settings, model=simulated_model(responder)))
    assert result["source"] == "strands_agent", result
    assert len(requests) == 2 and len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "platform_registry"
    assert result["sdk_tool_calls"][0]["tool_use"]["name"] == "platform_registry"
    assert result["recipients"][0]["evidence"]["method"] == "platform_registry"
    assert requests[-1]["messages"][-1]["role"] == "tool"


def test_recipient_call_cap_and_labelled_fallback(settings, monkeypatch):
    import censearch.agent.recipient as module

    calls = []

    def responder(request):
        calls.append(request)
        return completion(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_" + str(len(calls)),
                        "type": "function",
                        "function": {"name": "platform_registry", "arguments": '{"hostname":"github.com"}'},
                    }
                ],
            },
            "tool_calls",
        )

    monkeypatch.setattr(
        module, "resolve", lambda *args: {"source": "deterministic_baseline", "recipients": []}
    )
    result = asyncio.run(lookup("https://github.com/", settings, model=simulated_model(responder)))
    assert len(calls) <= 12
    assert result["source"] == "deterministic_baseline" and result["model_status"] == "model_error"
    assert result["agent_attempt"]["tool_calls"]


def test_agent_rejects_invented_contact(settings, monkeypatch):
    import censearch.agent.recipient as module

    model = simulated_model(
        lambda request: completion({"role": "assistant", "content": '{"ranked_contact_ids":["made-up"]}'})
    )
    monkeypatch.setattr(
        module, "resolve", lambda *args: {"source": "deterministic_baseline", "recipients": []}
    )
    result = asyncio.run(lookup("https://example.com/", settings, model=model))
    assert result["model_status"] == "model_error"
    assert result["agent_attempt"]["error"] == "ValueError"


def test_iana_domain_and_ipv6_bootstrap(settings):
    from censearch.agent.web import ReadOnlyWeb
    from urllib.parse import urlsplit

    def respond(request):
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(404)
        if path.endswith("dns.json"):
            return httpx.Response(200, json={"services": [[["test"], ["http://localhost/registry"]]]})
        if path.endswith("ipv6.json"):
            return httpx.Response(
                200, json={"services": [[["2606:4700::/32"], ["http://localhost/registry"]]]}
            )
        return httpx.Response(
            200,
            json={
                "name": "Recorded-format registry",
                "entities": [
                    {
                        "entities": [
                            {
                                "roles": ["abuse"],
                                "vcardArray": ["vcard", [["email", {}, "text", "abuse@example.test"]]],
                            }
                        ]
                    }
                ],
            },
        )

    for target in ("example.test", "2606:4700::1111"):
        with lookup_session(
            "http://localhost/page", settings, ReadOnlyWeb(transport=httpx.MockTransport(respond), delay=0)
        ) as session:
            result = rdap_lookup(target)
            assert result["status"] == "completed", result
            assert result["contacts"][0]["address"] == "abuse@example.test"
            assert urlsplit(result["registry_url"]).path.endswith(target)
            assert len(session.web.trace) > 0


@pytest.mark.parametrize("category", ["acted", "reasoned_refusal", "brush_off", "needs_more_information"])
def test_reply_reader_simulated_provider(settings, category):
    from censearch.agent.reply import read_reply

    model = simulated_model(
        lambda request: completion(
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "category": category,
                        "recommendation": "Review the reply and independently check the source.",
                    }
                ),
            }
        )
    )
    result = asyncio.run(read_reply("A simulated recipient reply", settings, model))
    assert result["status"] == "completed" and result["category"] == category
    assert result["advisory"] is True


def test_reply_no_model_and_bad_model_output(settings):
    from censearch.agent.reply import read_reply

    assert asyncio.run(read_reply("reply", settings))["status"] == "model_not_configured"
    model = simulated_model(lambda request: completion({"role": "assistant", "content": "not JSON"}))
    result = asyncio.run(read_reply("reply", settings, model))
    assert result["status"] == "model_error" and result["category"] is None
