import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Provider = Literal["demo", "ollama", "openai", "laya", "jev"]
Action = Literal["answer", "retrieve_more", "abstain", "review_conflict"]
LABELS = ("supported", "partial", "missing", "conflicting")


class Policy(BaseModel):
    support_threshold: float = Field(default=0.70, ge=0.25, le=1)
    conflict_threshold: float = Field(default=0.35, ge=0.05, le=1)


class QuestionInput(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    provider: Provider | None = None
    policy: Policy = Field(default_factory=Policy)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Enter a question with at least three non-whitespace characters.")
        return value


class Query(QuestionInput):
    generator: Literal["extractive", "ollama", "openai", "none"] = "extractive"
    top_k: int = Field(default=4, ge=1, le=8)


class ExternalEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")
    source: str = Field(default="external", min_length=1, max_length=240)
    text: str = Field(min_length=1, max_length=12_000)


class DecisionQuery(QuestionInput):
    model_config = ConfigDict(extra="forbid")
    evidence: list[ExternalEvidence] = Field(max_length=8)

    @model_validator(mode="after")
    def check_evidence(self):
        if len({item.id for item in self.evidence}) != len(self.evidence):
            raise ValueError("Evidence IDs must be unique within a request.")
        if sum(len(item.text) for item in self.evidence) > 48_000:
            raise ValueError("External evidence must total 48,000 characters or fewer.")
        return self


class DocumentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=200_000)


class Evidence(BaseModel):
    id: str
    document_id: str
    source: str
    text: str
    score: float
    position: int


class Decision(BaseModel):
    probabilities: dict[str, float]
    provider: str
    model: str
    semantics: str
    input_chars: int
    usage: dict = Field(default_factory=dict)
    question_schema: dict = Field(default_factory=dict)
    raw_probabilities: dict[str, float] = Field(default_factory=dict)

    @field_validator("probabilities")
    @classmethod
    def check_distribution(cls, value: dict[str, float]) -> dict[str, float]:
        if set(value) != set(LABELS):
            raise ValueError("Decision must contain exactly the four evidence labels.")
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in value.values()):
            raise ValueError("Invalid probability.")
        total = sum(value.values())
        if not 0.98 <= total <= 1.02:
            raise ValueError("Probabilities must sum to one (within rounding tolerance).")
        return {key: p / total for key, p in value.items()}


class Claim(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class GeneratedAnswer(BaseModel):
    claims: list[Claim] = Field(min_length=1, max_length=8)


class ReplayInput(BaseModel):
    policy: Policy


def apply_policy(decision: Decision, policy: Policy, evidence_count: int) -> tuple[Action, str]:
    """Pure routing: probability of a named outcome, never provider confidence."""
    p = decision.probabilities
    if not evidence_count:
        return "abstain", "No matching evidence was retrieved."
    if decision.usage.get("truncated") or decision.usage.get("state_tokens_dropped", 0):
        return (
            "retrieve_more",
            "The provider reported input truncation. Reduce the evidence or "
            "use a larger supported context before generating.",
        )
    if p["conflicting"] >= policy.conflict_threshold:
        return "review_conflict", "Evidence may disagree. Resolve the conflict before generating."
    if p["supported"] >= policy.support_threshold:
        return "answer", "The estimated support meets your selected threshold."
    if p["partial"] + p["supported"] >= 0.50:
        return "retrieve_more", "Some evidence exists, but it does not meet the answer threshold."
    return "abstain", "Available evidence is insufficient for this question."
