"""A simulated provider response verifies real SDK wiring, not live inference."""

import httpx
import openai
from fastapi.testclient import TestClient
from pydantic import SecretStr
from strands.models.openai import OpenAIModel
from censearch.api import create_app
import censearch.agent.probe as probe_module


def test_strands_calls_actual_dns_and_records_trace(settings, monkeypatch):
    requests = []

    def respond(request):
        import json

        body = json.loads(request.content)
        requests.append(body)
        assert request.url.path == "/v1/chat/completions"
        assert body["max_tokens"] == 1024
        if len(requests) == 1:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_dns",
                        "type": "function",
                        "function": {"name": "dns_lookup", "arguments": '{"hostname":"localhost"}'},
                    }
                ],
            }
            reason = "tool_calls"
        else:
            message = {"role": "assistant", "content": "Local resolver returned loopback addresses."}
            reason = "stop"
        return httpx.Response(
            200,
            json={
                "id": "test-completion",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "choices": [{"index": 0, "message": message, "finish_reason": reason}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
            },
        )

    # No socket or API credential is used by this transport.
    sdk = openai.AsyncOpenAI(
        api_key="local-test-placeholder",
        base_url="http://127.0.0.1/v1",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
    )
    model = OpenAIModel(client=sdk, model_id="test-model", stream=False, params={"max_tokens": 1024})
    monkeypatch.setattr(probe_module, "build_model", lambda settings: model)
    settings.openai_api_key = SecretStr("local-test-placeholder")
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/agent/probe", json={"hostname": "localhost"})
        assert client.get("/api/health").json()["model"]["live_call_verified"] is True
    result = response.json()
    assert result["status"] == "completed", result
    assert len(requests) == 2
    assert len(result["tool_calls"]) == 1
    call = result["tool_calls"][0]
    assert call["tool_use"]["name"] == "dns_lookup"
    assert "127.0.0.1" in str(call["result"])
    assert requests[1]["messages"][-1]["role"] == "tool"
