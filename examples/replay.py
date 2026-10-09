"""Replay the bundled synthetic Qwen trace offline. No inference, retrieval or API key."""

import json
from pathlib import Path

from nocap.engine import replay
from nocap.models import Policy

trace = json.loads(
    (Path(__file__).parents[1] / "docs/examples/local-ollama.trace.json").read_text(
        encoding="utf-8"
    )
)
for threshold in (0.50, 0.70, 0.90, 0.95):
    result = replay(trace, Policy(support_threshold=threshold))
    print(f"support={threshold:.2f} → {result['action']} ({result['inference_calls']} model calls)")
