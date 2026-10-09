"""`nocap eval`: regression tests for the routes your RAG should take. CI-friendly exit codes."""

import json
import tempfile
from pathlib import Path

from .config import Settings
from .engine import run_decision, run_query
from .gate import to_evidence
from .models import DecisionQuery, Policy, Query
from .providers import ProviderError
from .samples import DOCUMENTS
from .store import Store

ACTIONS = ("answer", "retrieve_more", "abstain", "review_conflict")


def load_cases(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".jsonl":
        cases = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        cases = json.loads(text)
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict) or "question" not in case or "expect" not in case:
            raise ValueError(f"Case {index} needs 'question' and 'expect'.")
        if case["expect"] not in ACTIONS:
            raise ValueError(f"Case {index}: expect must be one of {', '.join(ACTIONS)}.")
        case.setdefault("id", f"case-{index}")
    return cases


def load_documents(store: Store, paths: list[Path], samples: bool) -> int:
    count = 0
    if samples:
        for name, text in DOCUMENTS.items():
            store.add_document(name, text)
            count += 1
    for path in paths:
        files = sorted(path.rglob("*")) if path.is_dir() else [path]
        for file in files:
            if file.is_file() and file.suffix.lower() in {".md", ".txt"}:
                store.add_document(file.name, file.read_text(encoding="utf-8-sig"))
                count += 1
    return count


async def run_eval(
    cases: list[dict],
    settings: Settings,
    *,
    provider: str | None,
    policy: Policy,
    docs: list[Path],
    samples: bool,
) -> dict:
    rows = []
    # Evaluation never touches the user's workspace or trace history.
    with tempfile.TemporaryDirectory(prefix="nocap-eval-") as directory:
        store = Store(Path(directory))
        load_documents(store, docs, samples)
        for case in cases:
            row = {"id": case["id"], "question": case["question"], "expect": case["expect"]}
            try:
                if "evidence" in case:
                    trace = await run_decision(
                        store,
                        settings,
                        DecisionQuery(
                            question=case["question"],
                            provider=provider,
                            policy=policy,
                            evidence=to_evidence(case["evidence"]),
                        ),
                    )
                else:
                    trace = await run_query(
                        store,
                        settings,
                        Query(
                            question=case["question"],
                            provider=provider,
                            policy=policy,
                            generator="none",
                        ),
                    )
                row |= {
                    "actual": trace["action"],
                    "probabilities": trace["decision"]["probabilities"],
                    "ms": trace["timing_ms"]["total"],
                }
            except (ProviderError, ValueError) as exc:
                row["error"] = str(exc)
            rows.append(row)
    done = [r for r in rows if "actual" in r]
    return {
        "provider": provider or settings.provider,
        "policy": policy.model_dump(),
        "cases": rows,
        "total": len(rows),
        "passed": sum(r.get("actual") == r["expect"] for r in rows),
        "errors": len(rows) - len(done),
        # The dangerous failure: the gate allowed generation when it should not have.
        "leaks": sum(r["actual"] == "answer" and r["expect"] != "answer" for r in done),
        # The annoying failure: the gate blocked a question the sources could answer.
        "over_refusals": sum(r["actual"] != "answer" and r["expect"] == "answer" for r in done),
    }


def print_report(report: dict) -> None:
    width = max([len(r["id"]) for r in report["cases"]] + [4])
    for row in report["cases"]:
        if "error" in row:
            mark, detail = "ERR ", row["error"]
        else:
            ok = row["actual"] == row["expect"]
            leak = row["actual"] == "answer" and row["expect"] != "answer"
            mark = "PASS" if ok else ("LEAK" if leak else "FAIL")
            detail = row["actual"] if ok else f"expected {row['expect']}, got {row['actual']}"
        print(f"  {mark}  {row['id']:<{width}}  {detail}")
    total = report["total"] or 1
    print(
        f"\n  {report['passed']}/{report['total']} routes matched "
        f"({report['passed'] / total:.0%}) | {report['leaks']} leaks | "
        f"{report['over_refusals']} over-refusals | {report['errors']} errors "
        f"| provider={report['provider']}"
    )
