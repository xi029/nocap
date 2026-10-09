"""In-process SDK: gate any RAG pipeline in a few lines, no server required.

from nocap import Gate

gate = Gate(provider="ollama")

@gate.guard(fallback="I don't know based on the available sources.")
def answer(question, evidence):
    return my_llm(question, evidence)

answer("How do I request a refund?", retriever(question))
"""

import asyncio
import functools
import inspect
import re
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .engine import run_decision
from .models import DecisionQuery, Policy
from .store import Store

_SAFE_ID = re.compile(r"[^A-Za-z0-9_.:-]+")


class Blocked(RuntimeError):
    """Raised by a guarded function when the gate refuses generation and no fallback is set."""

    def __init__(self, verdict: "Verdict"):
        super().__init__(f"{verdict.action}: {verdict.reason}")
        self.verdict = verdict


@dataclass(frozen=True)
class Verdict:
    action: str
    reason: str
    probabilities: dict[str, float]
    evidence: list[dict]
    trace: dict = field(repr=False)

    @property
    def ok(self) -> bool:
        """True only when the policy allows generation."""
        return self.action == "answer"

    def __bool__(self) -> bool:
        return self.ok

    @property
    def trace_id(self) -> str:
        return self.trace["id"]


class _MemoryStore:
    """Keeps no history. Used when a caller opts out of saving traces."""

    def save_trace(self, payload: dict) -> dict:
        return {
            **payload,
            "id": uuid.uuid4().hex,
            "created": datetime.now(UTC).isoformat(),
            "schema_version": 1,
        }


def to_evidence(items: Iterable[Any]) -> list[dict]:
    """Normalize strings, dicts, LangChain Documents and LlamaIndex nodes (first 8 items)."""
    result = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, str):
            text, source, item_id = item, "external", None
        elif isinstance(item, dict):
            text = item.get("text") or item.get("page_content") or item.get("content") or ""
            source = item.get("source") or (item.get("metadata") or {}).get("source", "external")
            item_id = item.get("id")
        else:
            node = getattr(item, "node", item)  # LlamaIndex NodeWithScore wraps a node.
            text = getattr(node, "page_content", None) or getattr(node, "text", None) or ""
            if not text and hasattr(node, "get_content"):
                text = node.get_content()
            metadata = getattr(node, "metadata", None) or {}
            source = metadata.get("source") or metadata.get("file_name") or "external"
            item_id = getattr(node, "id", None) or getattr(node, "node_id", None)
        item_id = _SAFE_ID.sub("-", str(item_id or f"e{index}"))[:120].strip("-") or f"e{index}"
        # 8 x 6,000 characters fits the request limit; provider budgets are smaller anyway.
        result.append({"id": item_id, "source": str(source)[:240], "text": str(text)[:6000]})
        if len(result) == 8:
            break
    seen: set[str] = set()
    for index, item in enumerate(result, start=1):
        if item["id"] in seen:
            item["id"] = f"{item['id']}-{index}"[:120]
        seen.add(item["id"])
    return result


class Gate:
    """Judge whether evidence supports a question before any generator runs."""

    def __init__(
        self,
        provider: str | None = None,
        *,
        support_threshold: float = 0.70,
        conflict_threshold: float = 0.35,
        settings: Settings | None = None,
        data_dir: str | Path | None = None,
        save_traces: bool = True,
    ):
        self.settings = settings or Settings()
        if data_dir is not None:
            self.settings = self.settings.model_copy(update={"data_dir": Path(data_dir)})
        self.provider = provider
        self.policy = Policy(
            support_threshold=support_threshold, conflict_threshold=conflict_threshold
        )
        self._store = Store(self.settings.data_dir) if save_traces else _MemoryStore()

    async def acheck(self, question: str, evidence: Iterable[Any]) -> Verdict:
        query = DecisionQuery(
            question=question,
            provider=self.provider,
            policy=self.policy,
            evidence=to_evidence(evidence),
        )
        trace = await run_decision(self._store, self.settings, query)
        return Verdict(
            action=trace["action"],
            reason=trace["reason"],
            probabilities=trace["decision"]["probabilities"],
            evidence=[
                {"id": e["id"], "source": e["source"], "text": e["text"]} for e in trace["evidence"]
            ],
            trace=trace,
        )

    def check(self, question: str, evidence: Iterable[Any]) -> Verdict:
        """Synchronous check. In async code, use ``await gate.acheck(...)``."""
        return asyncio.run(self.acheck(question, evidence))

    def guard(self, fallback: Any = None) -> Callable:
        """Run the wrapped ``fn(question, evidence)`` only on the ``answer`` route.

        The function receives the judged excerpts (``{"id", "source", "text"}``), exactly what
        the decision model saw. On any other route, return ``fallback`` (a value or a callable
        taking the ``Verdict``), or raise ``Blocked`` when no fallback is set.
        """

        def refuse(verdict: Verdict):
            if fallback is None:
                raise Blocked(verdict)
            return fallback(verdict) if callable(fallback) else fallback

        def decorate(fn: Callable) -> Callable:
            if inspect.iscoroutinefunction(fn):

                @functools.wraps(fn)
                async def async_wrapper(question: str, evidence: Iterable[Any], *args, **kwargs):
                    verdict = await self.acheck(question, evidence)
                    if not verdict.ok:
                        return refuse(verdict)
                    return await fn(question, verdict.evidence, *args, **kwargs)

                return async_wrapper

            @functools.wraps(fn)
            def wrapper(question: str, evidence: Iterable[Any], *args, **kwargs):
                verdict = self.check(question, evidence)
                if not verdict.ok:
                    return refuse(verdict)
                return fn(question, verdict.evidence, *args, **kwargs)

            return wrapper

        return decorate
