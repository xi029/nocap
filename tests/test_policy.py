import pytest
from pydantic import ValidationError

from nocap.models import Decision, Policy, apply_policy


def decision(values):
    return Decision(
        probabilities=dict(
            zip(("supported", "partial", "missing", "conflicting"), values, strict=True)
        ),
        provider="test",
        model="fixture",
        semantics="Test fixture",
        input_chars=0,
    )


@pytest.mark.parametrize(
    ("values", "count", "action"),
    [
        ([0.8, 0.1, 0.05, 0.05], 2, "answer"),
        ([0.8, 0.1, 0.05, 0.05], 0, "abstain"),
        ([0.4, 0.15, 0.05, 0.4], 2, "review_conflict"),
        ([0.4, 0.4, 0.15, 0.05], 2, "retrieve_more"),
        ([0.1, 0.1, 0.75, 0.05], 2, "abstain"),
        ([0.7, 0.2, 0.05, 0.05], 2, "answer"),
    ],
)
def test_routes(values, count, action):
    assert apply_policy(decision(values), Policy(), count)[0] == action


def test_replay_changes_policy_without_changing_decision():
    d = decision([0.8, 0.1, 0.05, 0.05])
    assert apply_policy(d, Policy(support_threshold=0.9), 1)[0] == "retrieve_more"
    assert d.probabilities["supported"] == 0.8


def test_reported_token_truncation_blocks_generation_at_any_threshold():
    d = decision([0.8, 0.1, 0.05, 0.05])
    d.usage = {"input_tokens": 100, "truncated": True, "truncated_questions": ["coverage_0"]}
    assert apply_policy(d, Policy(support_threshold=0.25), 2)[0] == "retrieve_more"


@pytest.mark.parametrize(
    "bad",
    [
        {"supported": 1},
        {"supported": float("nan"), "partial": 0, "missing": 0, "conflicting": 0},
        {"supported": 0.8, "partial": 0.3, "missing": 0.1, "conflicting": 0.1},
        {"supported": -0.1, "partial": 1, "missing": 0.1, "conflicting": 0},
    ],
)
def test_invalid_probability_distribution_rejected(bad):
    with pytest.raises(ValidationError):
        Decision(
            probabilities=bad, provider="test", model="fixture", semantics="test", input_chars=0
        )
