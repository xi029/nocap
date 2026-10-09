"""Reproducible routing smoke evaluation, not a general RAG benchmark."""

import argparse
import asyncio
import json
import statistics
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from nocap.config import Settings
from nocap.engine import run_query
from nocap.models import Query
from nocap.providers import ProviderError
from nocap.samples import CONFLICT_DOCUMENT, DOCUMENTS
from nocap.store import Store

CASES = [
    ("refund", "How do I request a refund?", "answer", False),
    ("deployment", "What port does the service listen on?", "answer", False),
    ("database", "What is the default database?", "answer", False),
    ("privacy", "Is telemetry disabled by default?", "answer", False),
    ("pricing", "What is the exact team plan pricing?", "retrieve_more", False),
    ("missing", "Who won the lunar chess championship?", "abstain", False),
    ("chinese", "本地部署默认端口是多少？", "answer", False),
    ("conflict", "How many days do I have to request a refund?", "review_conflict", True),
]


async def evaluate(args):
    settings = Settings(timeout_seconds=args.timeout)
    rows = []
    # Keep evaluation documents separate from the user's workspace.
    with tempfile.TemporaryDirectory(prefix="nocap-eval-", dir=".cache") as directory:
        store = Store(Path(directory))
        for name, text in DOCUMENTS.items():
            store.add_document(name, text)
        for case_id, question, expected, conflict in CASES:
            if conflict:
                store.add_document(*CONFLICT_DOCUMENT)
            try:
                trace = await run_query(
                    store, settings, Query(question=question, provider=args.provider)
                )
                rows.append(
                    {
                        "case": case_id,
                        "question": question,
                        "expected": expected,
                        "actual": trace["action"],
                        "correct": expected == trace["action"],
                        "probabilities": trace["decision"]["probabilities"],
                        "timing_ms": trace["timing_ms"],
                        "warnings": trace["warnings"],
                        "model": trace["decision"]["model"],
                        "raw_probabilities": trace["decision"]["raw_probabilities"],
                        "usage": trace["decision"]["usage"],
                    }
                )
                print(f"{case_id:12} expected={expected:16} actual={trace['action']}", flush=True)
            except ProviderError as exc:
                rows.append(
                    {"case": case_id, "expected": expected, "error": str(exc), "correct": False}
                )
                print(f"{case_id:12} ERROR {exc}", flush=True)
    completed = [row for row in rows if "actual" in row]
    report = {
        "created": datetime.now(UTC).isoformat(),
        "provider": args.provider,
        "dataset": "8 original fictional routing smoke cases; not held-out or representative",
        "disclaimer": "Demo is a lexical simulation. Ollama estimates are uncalibrated. "
        "Do not infer general accuracy or provider rankings from this fixture.",
        "policy": {"support_threshold": 0.70, "conflict_threshold": 0.35},
        "configuration": {
            "ollama_model": settings.ollama_model,
            "laya_model": settings.laya_model,
            "laya_state_chars": settings.laya_state_chars,
            "laya_balance_options": settings.laya_balance_options,
        },
        "cases": rows,
        "completed": len(completed),
        "errors": len(rows) - len(completed),
        "route_matches": sum(row["correct"] for row in rows),
        "median_total_ms": round(
            statistics.median(row["timing_ms"]["total"] for row in completed), 2
        )
        if completed
        else None,
        "answer_rate": sum(row["actual"] == "answer" for row in completed) / len(completed)
        if completed
        else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {args.output}; {report['route_matches']}/{len(rows)} expected routes matched.")
    return report["errors"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["demo", "ollama", "openai", "laya", "jev"], default="demo"
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluation.json"))
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    Path(".cache").mkdir(exist_ok=True)
    raise SystemExit(asyncio.run(evaluate(args)) > 0)


if __name__ == "__main__":
    main()
