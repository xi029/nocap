import importlib.util
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from nocap.app import create_app
from nocap.config import Settings
from nocap.providers import ProviderError


def evidence():
    return [{"id": "refund-1", "source": "policy.md", "text": "Refunds take 5 days."}]


def client(tmp_path):
    return TestClient(create_app(Settings(data_dir=tmp_path, provider="demo")))


def test_external_gate_bypasses_retrieval_and_generation_and_replays(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External gate must not retrieve or generate.")

    monkeypatch.setattr("nocap.engine.retrieve", forbidden)
    monkeypatch.setattr("nocap.engine.generate", forbidden)
    c = client(tmp_path)
    response = c.post(
        "/api/decide", json={"question": "How many days for refunds?", "evidence": evidence()}
    )
    assert response.status_code == 200
    trace = response.json()
    assert trace["action"] == "answer"
    assert trace["generator"] == "none" and not trace["generator_called"] and not trace["claims"]
    assert trace["evidence_origin"] == "external"
    assert trace["evidence"][0]["id"] == "refund-1"
    assert trace["input_state"]["excerpts"][0]["text"] == "Refunds take 5 days."
    assert c.get("/api/documents").json() == []
    replay = c.post(
        f"/api/traces/{trace['id']}/replay", json={"policy": {"support_threshold": 0.95}}
    ).json()
    assert replay["action"] == "retrieve_more" and replay["inference_calls"] == 0
    assert c.get(f"/api/traces/{trace['id']}/export").json() == trace


def test_empty_external_evidence_does_not_use_workspace_or_models(tmp_path, monkeypatch):
    c = client(tmp_path)
    c.post("/api/documents", json={"name": "local.md", "text": "Refunds take 5 days."})
    response = c.post(
        "/api/decide",
        json={"question": "How many days for refunds?", "evidence": [], "provider": "laya"},
    )
    assert response.status_code == 200
    trace = response.json()
    assert trace["action"] == "abstain" and trace["evidence"] == []
    assert trace["decision"]["model"] == "skipped-no-evidence"


def test_external_gate_exposes_actual_trimmed_evidence(tmp_path):
    chunks = evidence()
    chunks[0]["text"] += " More context." * 700
    trace = (
        client(tmp_path)
        .post("/api/decide", json={"question": "How many days for refunds?", "evidence": chunks})
        .json()
    )
    assert len(trace["evidence"][0]["text"]) < len(chunks[0]["text"])
    assert trace["evidence"][0]["text"] == trace["input_state"]["excerpts"][0]["text"]
    assert trace["warnings"] and not trace["generator_called"]


@pytest.mark.parametrize(
    "chunks",
    [
        evidence() * 2,
        [{"id": "bad id", "text": "Some text"}],
        [{"id": "a", "text": "   "}],
        [{"id": "a", "text": "x" * 12_001}],
        [{"id": str(i), "text": "Some text"} for i in range(9)],
        [{"id": str(i), "text": "x" * 10_000} for i in range(5)],
    ],
)
def test_external_gate_rejects_invalid_or_oversized_evidence(tmp_path, chunks):
    assert (
        client(tmp_path)
        .post("/api/decide", json={"question": "How many days for refunds?", "evidence": chunks})
        .status_code
        == 422
    )


def test_external_provider_failure_returns_502_without_saved_fake_trace(tmp_path, monkeypatch):
    async def unavailable(*args, **kwargs):
        raise ProviderError("Provider unavailable. No demo fallback was used.")

    monkeypatch.setattr("nocap.engine.evaluate", unavailable)
    c = client(tmp_path)
    response = c.post(
        "/api/decide", json={"question": "How many days for refunds?", "evidence": evidence()}
    )
    assert response.status_code == 502
    assert c.get("/api/traces").json() == []


def load_example():
    path = Path(__file__).resolve().parents[1] / "examples" / "external_rag.py"
    spec = importlib.util.spec_from_file_location("external_rag", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.guarded_rag


@pytest.mark.parametrize("route", ["answer", "retrieve_more", "review_conflict", "abstain"])
def test_example_only_generates_for_answer_using_judged_excerpts(route):
    judged = [{"id": "refund-1", "text": "Refunds take 5 days."}]
    calls = []

    def generate(question, chunks):
        calls.append((question, chunks))
        return "5 days"

    with httpx.Client(
        base_url="http://testserver",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"action": route, "evidence": judged})
        ),
    ) as c:
        result = load_example()(
            "How many days for refunds?", lambda _: evidence(), generate, client=c, provider="demo"
        )
    assert len(calls) == (1 if route == "answer" else 0)
    if calls:
        assert calls[0][1] == judged
        assert result["answer"] == "5 days"


def test_example_does_not_generate_when_gate_fails():
    def forbidden(*args):
        pytest.fail("Generator must not run on an HTTP error.")

    with (
        httpx.Client(
            base_url="http://testserver",
            transport=httpx.MockTransport(lambda _: httpx.Response(502)),
        ) as c,
        pytest.raises(httpx.HTTPStatusError),
    ):
        load_example()("How many days for refunds?", lambda _: evidence(), forbidden, client=c)
