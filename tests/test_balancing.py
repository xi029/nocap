import asyncio
import json

import httpx

from nocap.config import Settings
from nocap.models import Evidence
from nocap.providers import evaluate


def test_laya_balances_all_slots_and_preserves_usage(monkeypatch):
    original = httpx.AsyncClient

    def handle(request):
        questions = json.loads(request.content)["questions"]
        assert len(questions) == 4
        orders = [q["option_order"] for q in questions.values()]
        for slot in range(4):
            assert sorted(order[slot] for order in orders) == [0, 1, 2, 3]
        return httpx.Response(
            200,
            json={
                "answers": {
                    key: {
                        "probabilities": {
                            "supported": 0.7,
                            "partial": 0.2,
                            "missing": 0.05,
                            "conflicting": 0.05,
                        }
                    }
                    for key in questions
                },
                "usage": {"input_tokens": 100, "truncated": False, "truncated_questions": []},
            },
        )

    monkeypatch.setattr(
        "nocap.providers.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    evidence = [
        Evidence(
            id="a", document_id="d", source="a.md", text="Refunds take 5 days.", score=1, position=0
        )
    ]
    result, _, _ = asyncio.run(evaluate("laya", Settings(), "How long are refunds?", evidence))
    assert result.probabilities["supported"] == 0.7
    assert len(result.question_schema) == 4
    assert result.usage["truncated_questions"] == []
