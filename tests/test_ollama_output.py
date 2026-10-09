import asyncio
import json

import httpx
import pytest

from nocap.config import Settings
from nocap.models import Evidence
from nocap.providers import ProviderError, evaluate


@pytest.mark.parametrize("fence", [False, True])
def test_ollama_retains_and_normalizes_self_reported_weights(monkeypatch, fence):
    original = httpx.AsyncClient
    raw = {"supported": 0.9, "partial": 0.2, "missing": 0.1, "conflicting": 0.1}
    content = json.dumps({"probabilities": raw})
    if fence:
        content = "```json\n" + content + "\n```"

    def handle(request):
        body = json.loads(request.content)
        assert "supported" in body["messages"][0]["content"]
        assert body["format"]["$defs"]["CoverageProbabilities"]["required"] == list(raw)
        return httpx.Response(200, json={"message": {"content": content}})

    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    evidence = [
        Evidence(
            id="a", document_id="d", source="a.md", text="Refunds take 5 days.", score=1, position=0
        )
    ]
    result, _, _ = asyncio.run(evaluate("ollama", Settings(), "How long are refunds?", evidence))
    assert result.raw_probabilities == raw
    assert sum(result.probabilities.values()) == pytest.approx(1)
    assert result.probabilities["supported"] == pytest.approx(0.9 / 1.3)


def test_prose_around_json_is_not_accepted(monkeypatch):
    original = httpx.AsyncClient
    response = {"message": {"content": 'Here is your result: {"probabilities":{}}'}}
    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=response)), **kwargs
        ),
    )
    evidence = [
        Evidence(
            id="a", document_id="d", source="a.md", text="Refunds take 5 days.", score=1, position=0
        )
    ]
    with pytest.raises(ProviderError):
        asyncio.run(evaluate("ollama", Settings(), "How long are refunds?", evidence))


def test_invalid_decision_has_one_disclosed_repair_attempt(monkeypatch):
    original = httpx.AsyncClient
    calls = []

    def handle(request):
        body = json.loads(request.content)
        calls.append(body)
        if len(calls) == 1:
            content = '{"schema":"wrong output"}'
        else:
            assert "response did not validate" in body["messages"][0]["content"]
            content = json.dumps(
                {
                    "probabilities": {
                        "supported": 0.8,
                        "partial": 0.1,
                        "missing": 0.05,
                        "conflicting": 0.05,
                    }
                }
            )
        return httpx.Response(200, json={"message": {"content": content}})

    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    evidence = [
        Evidence(
            id="a", document_id="d", source="a.md", text="Refunds take 5 days.", score=1, position=0
        )
    ]
    decision, _, _ = asyncio.run(evaluate("ollama", Settings(), "How long are refunds?", evidence))
    assert len(calls) == 2
    assert decision.usage["validation_retries"] == 1
