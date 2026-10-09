"""Keep your retriever and generator; ask NoCap to gate the retrieved evidence.

Run with a NoCap server listening on localhost:
    uv run python examples/external_rag.py --provider demo
The bundled retriever and generator use fictional text and verbatim excerpts.
Replace these two callbacks with your existing application's implementations.
"""

import argparse
from collections.abc import Callable

import httpx


def guarded_rag(
    question: str,
    retriever: Callable[[str], list[dict]],
    generator: Callable[[str, list[dict]], str],
    *,
    client: httpx.Client,
    provider: str = "laya",
    policy: dict | None = None,
) -> dict:
    payload = {
        "question": question,
        "provider": provider,
        "evidence": retriever(question),
        "policy": policy or {"support_threshold": 0.70, "conflict_threshold": 0.35},
    }
    response = client.post("/api/decide", json=payload)
    # Errors propagate before the generator is called. Never generate on gate failure.
    response.raise_for_status()
    trace = response.json()
    answer = None
    if trace["action"] == "answer":
        # Use the exact excerpts judged, including any provider-budget trimming.
        answer = generator(question, trace["evidence"])
    return {"answer": answer, "trace": trace}


def retrieve_sample(_question: str) -> list[dict]:
    return [
        {
            "id": "refund-1",
            "source": "refund-policy.md",
            "text": "Customers can request a refund within 30 days. "
            "To request a refund, email support with the order number.",
        }
    ]


def generate_excerpts(_question: str, evidence: list[dict]) -> str:
    # Demonstration callback: verbatim text, not a model-generated answer.
    return "\n".join(f"[{item['id']}] {item['text']}" for item in evidence)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--provider", choices=["demo", "ollama", "openai", "laya", "jev"], default="demo"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8787")
    parser.add_argument("--question", default="How do I request a refund?")
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=150, trust_env=False) as client:
        result = guarded_rag(
            args.question, retrieve_sample, generate_excerpts, client=client, provider=args.provider
        )
    trace = result["trace"]
    print(f"Provider: {trace['decision']['provider']} | {trace['decision']['semantics']}")
    print(f"Route: {trace['action']} | {trace['reason']}")
    print(f"Saved trace: {trace['id']} | NoCap generator calls: {trace['generator_called']}")
    if result["answer"] is not None:
        print("Example generator output (verbatim excerpts):")
        print(result["answer"])
    else:
        print("Your application's generator was skipped.")


if __name__ == "__main__":
    main()
