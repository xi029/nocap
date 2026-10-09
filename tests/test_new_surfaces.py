import asyncio
import json
import sys
from types import SimpleNamespace

import httpx
import pytest

from nocap import Blocked, Gate, to_evidence
from nocap.config import Settings
from nocap.models import Evidence
from nocap.providers import ProviderError, evaluate, generate

REFUND = "To request a refund, email support with the order number."


def gate(tmp_path, **kwargs):
    return Gate("demo", settings=Settings(data_dir=tmp_path), **kwargs)


def test_to_evidence_accepts_strings_dicts_and_framework_objects():
    langchain_doc = SimpleNamespace(page_content="A", metadata={"source": "a.md"}, id=None)
    llama_node = SimpleNamespace(
        node=SimpleNamespace(text="B", metadata={"file_name": "b.md"}, node_id="node/1")
    )
    items = to_evidence(["plain", {"text": "D", "id": "x"}, langchain_doc, llama_node])
    assert [i["text"] for i in items] == ["plain", "D", "A", "B"]
    assert [i["source"] for i in items] == ["external", "external", "a.md", "b.md"]
    assert items[3]["id"] == "node-1"
    assert len({i["id"] for i in items}) == 4
    assert len(to_evidence(["x"] * 20)) == 8
    assert len({i["id"] for i in to_evidence([{"text": "a", "id": "s"}] * 3)}) == 3


def test_gate_check_and_guard_run_generator_only_on_answer(tmp_path):
    g = gate(tmp_path)
    verdict = g.check("How do I request a refund?", [REFUND])
    assert verdict.ok and verdict.action == "answer" and verdict.trace_id
    calls = []

    @g.guard(fallback="I don't know.")
    def answer(question, evidence):
        calls.append(evidence)
        return "generated"

    assert answer("How do I request a refund?", [REFUND]) == "generated"
    assert calls[0][0]["text"] == REFUND
    assert answer("Who won the lunar chess championship?", [REFUND]) == "I don't know."
    assert len(calls) == 1


def test_guard_raises_blocked_and_supports_async(tmp_path):
    g = gate(tmp_path, save_traces=False)

    @g.guard()
    def strict(question, evidence):
        raise AssertionError("must not run")

    with pytest.raises(Blocked) as info:
        strict("Who won the lunar chess championship?", [])
    assert info.value.verdict.action == "abstain"

    @g.guard(fallback=lambda verdict: verdict.action)
    async def answer(question, evidence):
        return "generated"

    assert asyncio.run(answer("How do I request a refund?", [REFUND])) == "generated"
    assert asyncio.run(answer("Lunar chess winner?", [])) == "abstain"
    assert not (tmp_path / "nocap.sqlite3").exists()


def test_openai_compatible_provider_judges_and_generates(monkeypatch):
    seen = []

    def handle(request):
        payload = json.loads(request.content)
        seen.append((request, payload))
        assert request.url.path == "/v1/chat/completions"
        assert payload["model"] == "deepseek-chat"
        assert payload["response_format"] == {"type": "json_object"}
        if "probabilities" in payload["messages"][0]["content"]:
            content = '{"probabilities": {"supported": 0.8, "partial": 0.1, "missing": 0.1, "conflicting": 0}}'
        else:
            content = '```json\n{"claims": [{"text": "Five days.", "evidence_ids": ["a"]}]}\n```'
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    settings = Settings(
        openai_url="https://api.example.test/v1", openai_model="deepseek-chat", openai_api_key="k"
    )
    items = [Evidence(id="a", document_id="d", source="p", text="Five days.", score=1, position=0)]
    decision, _, _ = asyncio.run(evaluate("openai", settings, "How long?", items))
    assert decision.probabilities["supported"] == pytest.approx(0.8)
    assert decision.model == "deepseek-chat" and decision.usage["input_tokens"] == 12
    assert seen[0][0].headers["authorization"] == "Bearer k"
    answer = asyncio.run(generate(settings, "How long?", items, "openai"))
    assert answer.claims[0].evidence_ids == ["a"]


def test_openai_provider_requires_a_model():
    items = [Evidence(id="a", document_id="d", source="p", text="x", score=1, position=0)]
    with pytest.raises(ProviderError, match="NOCAP_OPENAI_MODEL"):
        asyncio.run(evaluate("openai", Settings(openai_model=""), "Question?", items))


def run_cli(monkeypatch, tmp_path, *args):
    from nocap import cli

    monkeypatch.setenv("NOCAP_DATA_DIR", str(tmp_path / "workspace"))
    monkeypatch.setattr(sys, "argv", ["nocap", *args])
    with pytest.raises(SystemExit) as info:
        cli.main()
    return info.value.code


def test_eval_cli_reports_leaks_and_exit_codes(monkeypatch, tmp_path, capsys):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(
        "\n".join(
            json.dumps(c)
            for c in [
                {"question": "How do I request a refund?", "expect": "answer"},
                {"question": "Who won the lunar chess championship?", "expect": "abstain"},
                {"question": "How do I request a refund?", "expect": "abstain", "id": "leaky"},
            ]
        ),
        encoding="utf-8",
    )
    report = tmp_path / "out" / "report.json"
    code = run_cli(monkeypatch, tmp_path, "eval", str(cases), "--samples", "--output", str(report))
    assert code == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert (data["passed"], data["leaks"], data["errors"]) == (2, 1, 0)
    assert "LEAK  leaky" in capsys.readouterr().out
    assert run_cli(monkeypatch, tmp_path, "eval", str(cases), "--samples", "--max-leaks", "0") == 1
    assert not (tmp_path / "workspace").exists()


def test_mcp_server_tools(tmp_path):
    pytest.importorskip("mcp")
    from nocap.mcp_server import create_server

    server = create_server(Settings(data_dir=tmp_path, provider="demo"))
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert names == {"check_evidence", "ask_knowledge_base", "add_document", "replay_decision"}

    def call(name, arguments):
        result = asyncio.run(server.call_tool(name, arguments))
        return json.loads(result.content[0].text)

    verdict = call(
        "check_evidence",
        {"question": "How do I request a refund?", "evidence": [{"text": REFUND}]},
    )
    assert verdict["action"] == "answer" and "ONLY" in verdict["next_step"]
    replayed = call("replay_decision", {"trace_id": verdict["trace_id"], "support_threshold": 0.99})
    assert replayed["action"] == "retrieve_more" and replayed["inference_calls"] == 0
    call("add_document", {"name": "refunds.md", "text": REFUND})
    assert call("ask_knowledge_base", {"question": "How do I request a refund?"})["action"] == (
        "answer"
    )


def test_store_adopts_legacy_database(tmp_path):
    from nocap.store import Store

    Store(tmp_path).add_document("a.md", "Legacy text.")
    (tmp_path / "nocap.sqlite3").rename(tmp_path / "jevlens.sqlite3")
    assert [d["name"] for d in Store(tmp_path).documents()] == ["a.md"]
    assert not (tmp_path / "jevlens.sqlite3").exists()
