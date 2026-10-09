import asyncio
import json

import httpx
import pytest

from nocap.config import Settings
from nocap.models import Evidence
from nocap.providers import ProviderError, evaluate, generate, prepare_state


def evidence():
    return [
        Evidence(
            id="a",
            document_id="doc",
            source="policy.md",
            text="Refunds take 5 days.",
            score=1,
            position=0,
        )
    ]


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.parametrize("provider", ["laya", "jev"])
def test_systemone_wire_contract(monkeypatch, provider):
    def handle(request):
        assert request.url.path == "/v1/systemone"
        payload = json.loads(request.content)
        assert payload["questions"]["coverage"]["type"] == "choice"
        assert list(payload["questions"]["coverage"]["criteria"]) == [
            "supported",
            "partial",
            "missing",
            "conflicting",
        ]
        assert payload["state"]["question"] == "How long do refunds take?"
        assert request.headers["authorization"] == "Bearer test-key"
        return httpx.Response(
            200,
            json={
                "model": "resolved-v1",
                "answers": {
                    "coverage": {
                        "choice": "supported",
                        "confidence": 0.99,
                        "probabilities": {
                            "supported": 0.8,
                            "partial": 0.1,
                            "missing": 0.05,
                            "conflicting": 0.05,
                        },
                    }
                },
                "usage": {"input_tokens": 22, "output_tokens": 0},
            },
        )

    install_transport(monkeypatch, handle)
    settings = Settings(laya_api_key="test-key", jev_api_key="test-key", laya_balance_options=False)
    d, used, state = asyncio.run(
        evaluate(provider, settings, "How long do refunds take?", evidence())
    )
    assert d.probabilities["supported"] == 0.8
    assert d.model == "resolved-v1"
    assert used[0].text == state["excerpts"][0]["text"]


def test_unavailable_provider_does_not_fall_back(monkeypatch):
    def handle(request):
        raise httpx.ConnectError("offline", request=request)

    install_transport(monkeypatch, handle)
    with pytest.raises(ProviderError, match="No demo fallback"):
        asyncio.run(evaluate("laya", Settings(), "How long do refunds take?", evidence()))


def test_bad_response_rejected(monkeypatch):
    install_transport(
        monkeypatch,
        lambda _: httpx.Response(
            200,
            json={
                "answers": {
                    "coverage": {
                        "probabilities": {
                            "supported": 9,
                            "partial": 0,
                            "missing": 0,
                            "conflicting": 0,
                        }
                    }
                }
            },
        ),
    )
    with pytest.raises(ProviderError):
        asyncio.run(evaluate("laya", Settings(), "How long do refunds take?", evidence()))


def test_unknown_citations_rejected(monkeypatch):
    install_transport(
        monkeypatch,
        lambda _: httpx.Response(
            200,
            json={
                "message": {
                    "content": json.dumps(
                        {"claims": [{"text": "Invented fact.", "evidence_ids": ["invented"]}]}
                    )
                }
            },
        ),
    )
    with pytest.raises(ProviderError, match="invalid citations"):
        asyncio.run(generate(Settings(), "How long do refunds take?", evidence()))


def test_exact_budgeted_input_is_visible():
    many = evidence() * 4
    many[0] = many[0].model_copy(update={"text": "x" * 1000})
    state, included = prepare_state("Question here?", many, 500)
    assert len(included) < len(many)
    assert included[0].text == state["excerpts"][0]["text"]
    assert len(included[0].text) < 1000
