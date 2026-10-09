"""Gate a RAG answer in a few lines. Runs offline with the demo provider:

uv run python examples/quickstart.py
uv run python examples/quickstart.py --provider ollama
"""

import argparse

from nocap import Gate

DOCS = [
    {
        "source": "refund-policy.md",
        "text": "To request a refund, email support with your order ID.",
    },
    {"source": "refund-policy.md", "text": "Customers can request a refund within 30 days."},
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="demo")
    args = parser.parse_args()
    gate = Gate(provider=args.provider, save_traces=False)

    @gate.guard(fallback=lambda v: f"[{v.action}] I can't answer that from the sources.")
    def answer(question, evidence):
        # Replace with your LLM call. It only runs when the evidence supports an answer.
        return "Based on " + ", ".join(e["source"] for e in evidence) + ": " + evidence[0]["text"]

    for question in ["How do I request a refund?", "Who won the lunar chess championship?"]:
        print(f"Q: {question}\nA: {answer(question, DOCS)}\n")


if __name__ == "__main__":
    main()
