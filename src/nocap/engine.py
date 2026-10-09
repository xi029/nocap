from time import perf_counter

from .config import Settings
from .models import Claim, Decision, DecisionQuery, Evidence, Policy, Query, apply_policy
from .providers import ProviderError, evaluate, generate
from .retrieval import retrieve
from .store import Store


async def run_query(
    store: Store, settings: Settings, query: Query, *, evidence: list[Evidence] | None = None
) -> dict:
    start = perf_counter()
    external = evidence is not None
    candidates = evidence if external else retrieve(store.documents(), query.question, query.top_k)
    retrieved_at = perf_counter()
    provider = query.provider or settings.provider
    decision, evidence, state = await evaluate(provider, settings, query.question, candidates)
    decided_at = perf_counter()
    action, reason = apply_policy(decision, query.policy, len(evidence))
    claims: list[Claim] = []
    generation_error = None
    generator_called = False
    if action == "answer":
        if query.generator in {"ollama", "openai"}:
            generator_called = True
            try:
                claims = (
                    await generate(settings, query.question, evidence, query.generator)
                ).claims
            except ProviderError as exc:
                generation_error = str(exc)
        elif query.generator == "extractive":
            # Verbatim evidence, explicitly displayed as excerpts, not a synthesized answer.
            claims = [Claim(text=e.text, evidence_ids=[e.id]) for e in evidence[:2]]
    finished = perf_counter()
    warnings = []
    if decision.usage.get("validation_retries"):
        warnings.append(
            "The first LLM decision output was invalid. One schema-repair retry "
            "was made with the same model; the valid response is shown."
        )
    if decision.usage.get("truncated") or decision.usage.get("state_tokens_dropped", 0):
        warnings.append(
            "The provider reported token truncation. Generation is blocked for this trace."
        )
    if len(evidence) < len(candidates) or any(
        e.text != next(c.text for c in candidates if c.id == e.id) for e in evidence
    ):
        warnings.append(
            "Evidence was trimmed to the provider character budget. Only displayed "
            "excerpts were judged. The model tokenizer may impose further truncation."
        )
    if provider == "laya":
        warnings.append(
            "Laya label order and checkpoint token limits can affect results. "
            "Inspect the input, configure max_len, and validate your question schema."
        )
    if query.generator in {"ollama", "openai"} and claims:
        warnings.append(
            "Citation IDs are validated. Semantic support of generated claims is not verified."
        )
    return store.save_trace(
        {
            "question": query.question,
            "action": action,
            "reason": reason,
            "policy": query.policy.model_dump(),
            "decision": decision.model_dump(),
            "evidence": [e.model_dump() for e in evidence],
            "retrieved_count": len(candidates),
            "evidence_origin": "external" if external else "bm25",
            "input_state": state,
            "claims": [c.model_dump() for c in claims],
            "generator": query.generator,
            "generator_called": generator_called,
            "generation_error": generation_error,
            "warnings": warnings,
            "timing_ms": {
                "retrieval": round((retrieved_at - start) * 1000, 2),
                "decision": round((decided_at - retrieved_at) * 1000, 2),
                "generation": round((finished - decided_at) * 1000, 2),
                "total": round((finished - start) * 1000, 2),
            },
        }
    )


async def run_decision(store: Store, settings: Settings, query: DecisionQuery) -> dict:
    """Judge caller-supplied retrieval results; never retrieve or generate an answer."""
    evidence = [
        Evidence(
            id=item.id,
            document_id=f"external:{item.id}",
            source=item.source,
            text=item.text,
            score=0,
            position=position,
        )
        for position, item in enumerate(query.evidence)
    ]
    return await run_query(
        store,
        settings,
        Query(
            question=query.question,
            provider=query.provider,
            policy=query.policy,
            generator="none",
        ),
        evidence=evidence,
    )


def replay(trace: dict, policy: Policy) -> dict:
    action, reason = apply_policy(
        Decision.model_validate(trace["decision"]), policy, len(trace["evidence"])
    )
    return {
        "trace_id": trace["id"],
        "action": action,
        "reason": reason,
        "policy": policy.model_dump(),
        "inference_calls": 0,
        "original_action": trace["action"],
        "note": "Policy replay only; no new answer is generated.",
    }
