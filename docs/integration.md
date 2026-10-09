# Add NoCap to an existing RAG

NoCap can be a standalone workbench or an evidence gate inside an application. The integration path accepts **already retrieved chunks**, makes a coverage judgment and returns a route. Your application keeps its retriever, vector store, generator and user-facing response.

![Any retriever sends excerpts to the NoCap gate, which routes before generation](assets/architecture.svg)

## Python SDK (recommended)

`pip install nocap` gives you an in-process gate. No server needs to run.

```python
from nocap import Gate

gate = Gate(provider="ollama")  # or "openai", "laya", "jev", "demo"


@gate.guard(fallback="I couldn't find that in the documentation.")
def answer(question, evidence):
    # Runs ONLY on the answer route, with exactly the excerpts that were judged.
    return my_llm(question, evidence)


answer("How do I request a refund?", retriever.invoke("How do I request a refund?"))
```

`evidence` can be a list of strings, dicts with `text` / `source` / `id`, LangChain `Document`s or LlamaIndex nodes; NoCap reads `page_content`, `text` or `get_content()` and the `source` / `file_name` metadata without importing either framework. The first 8 items are judged, each capped at 6,000 characters.

- `gate.check(question, evidence)` returns a `Verdict` with `action`, `reason`, `probabilities`, judged `evidence`, `trace_id` and `ok` (true only for `answer`). Use `await gate.acheck(...)` inside async code.
- `@gate.guard()` without a fallback raises `nocap.Blocked`; the exception carries `.verdict`. A callable fallback receives the `Verdict`, so you can return a route-specific message. Async functions are supported.
- Traces are saved to `NOCAP_DATA_DIR` (default `./data`) so that `nocap serve` shows every decision your application made. Pass `save_traces=False` to keep nothing, or `data_dir=` to choose a location.

## HTTP integration

Start `uv run nocap serve`. From your application's backend, send `POST /api/decide`:

```python
import httpx

with httpx.Client(base_url="http://127.0.0.1:8787", timeout=150, trust_env=False) as client:
    response = client.post(
        "/api/decide",
        json={
            "question": "How long do refunds take?",
            "provider": "demo",
            "evidence": [{"id": "refund-1", "source": "policy.md", "text": "Refunds take 5 days."}],
            "policy": {"support_threshold": 0.70, "conflict_threshold": 0.35},
        },
    )
    response.raise_for_status()
    trace = response.json()
    print(trace["action"], trace["evidence"])
```

Use `demo` only to exercise the interface. Configure `laya`, `ollama` or `jev` as described in [Providers](providers.md) for live decisions. An omitted provider uses the server default, which starts as demo.

The endpoint never uses the local document collection and never calls a generator, including on `answer`. It records `evidence_origin: "external"`, `generator: "none"`, `generator_called: false` and `claims: []`. The decision is saved in the same local history as workbench queries and supports export and policy replay. No chunks are imported into `/api/documents`.

## Adapt your retrieval results

Map your existing search results to three fields:

```python
chunks = [
    {"id": f"chunk-{i}", "source": hit["filename"], "text": hit["content"]}
    for i, hit in enumerate(search_results[:8])
]
```

`search_results` above represents your application's own results; change the field names to match your retriever. Preserve meaningful stable IDs when possible. Only text and excerpt IDs are sent in the decision state; the source name is retained in the trace for inspection. The input does not accept retrieval scores because a score's meaning differs across retrievers. Returned external evidence has `score: 0` as an unused placeholder, and the UI labels it as external evidence rather than BM25.

The caller determines chunk order. NoCap includes chunks in that order until the provider character budget is reached, potentially retaining only the beginning of the last chunk. Use `trace["evidence"]` as your generator context: it contains exactly the excerpts judged. Passing additional unjudged context to the generator means that the gate no longer describes the generation input. Warnings and `input_state` expose trimming; provider-reported token truncation blocks generation permission.

### Input contract

- Question: 3–500 nonblank characters.
- Evidence: 0–8 items, at most 48,000 text characters in total.
- Each item: `id`, `text`, and optional `source` (default `external`).
- IDs: unique within the request, 1–120 characters; letters, digits, `_`, `.`, `:`, `-`.
- Text: 1–12,000 nonblank characters per item. Leading/trailing whitespace is stripped.
- Source: 1–240 nonblank characters. This is metadata, not a file to open.
- Policy: support threshold 0.25–1, conflict threshold 0.05–1; defaults 0.70 and 0.35.
- Extra fields such as `generator` are rejected; the endpoint only makes a decision.

An empty evidence list abstains without contacting a provider, even if the workbench has documents. Bad inputs return 422. A provider/network/schema failure returns 502, without a synthetic fallback judgment.

## Keep your generator behind the gate

The runnable [external_rag.py](../examples/external_rag.py) exports `guarded_rag`. It takes a question, a retriever callback, a generator callback, and an HTTP client. The retriever returns items in the input contract; the generator receives the question and the **judged** evidence list. Its return value is your answer.

```python
import httpx
from examples.external_rag import guarded_rag

# Existing callbacks in your application:
# retrieve(question) -> list of {id, source, text}
# generate_answer(question, judged_evidence) -> str
with httpx.Client(base_url="http://127.0.0.1:8787", timeout=150, trust_env=False) as client:
    result = guarded_rag(question, retrieve, generate_answer, client=client, provider="laya")
```

The last snippet shows the callback wiring; `question`, `retrieve` and `generate_answer` belong to your application. `examples` is repository example code, not an installed package API. Copy the adapter into your project or run it from the repository. The fully runnable version is:

```sh
uv run python examples/external_rag.py --provider demo
uv run python examples/external_rag.py --provider demo --question "Who won lunar chess?"
```

That example uses fictional retrieval data and an excerpt-only generator; it requires no additional model. In your application, generate only for `answer`. For `retrieve_more`, try better evidence or request clarification with a bounded retry count. For `abstain`, return an insufficient-evidence response. For `review_conflict`, use a person or your existing source-resolution workflow. On an HTTP/provider error, stop before generation and report an unavailable gate. The example propagates that error.

Your generator runs outside NoCap: its answer, citations and timings are **not** attached to the saved decision trace or validated by NoCap. Store them in your own logs if needed. A route of `answer` is permission under the selected policy, not a guarantee of factual correctness.

## Lower-level Python integration

The `Gate` SDK above wraps these building blocks. To control storage and settings yourself, call the engine directly:

```python
import asyncio
from pathlib import Path

from nocap.config import Settings
from nocap.engine import run_decision
from nocap.models import DecisionQuery
from nocap.store import Store


async def main():
    settings = Settings(data_dir=Path("my-gate-traces"), provider="demo")
    query = DecisionQuery(
        question="How long do refunds take?",
        evidence=[{"id": "refund-1", "source": "policy.md", "text": "Refunds take 5 days."}],
    )
    trace = await run_decision(Store(settings.data_dir), settings, query)
    print(trace["action"], trace["id"])


asyncio.run(main())
```

For an existing asynchronous application, `await run_decision(...)` from its event loop. `DecisionQuery` validates the same limits as HTTP. `ProviderError` propagates to the caller and must stop generation. There is no hosted NoCap service.

## Inspect, tune and store responsibly

Open the workbench and select the saved question in recent history. Inspect the submitted excerpts, provider semantics and route. Adjust a threshold to replay only the routing decision; no inference or new answer is produced. A score of 0.8 is not a demonstrated 80% factual accuracy rate. Choose thresholds on labelled questions from your own deployment; see [Evaluation](evaluation.md).

The integration saves the question and used excerpts in local SQLite, even though it does not import documents. Delete or retain those traces according to your application's requirements. Hosted Jev sends the submitted state to its configured service; remote Laya/Ollama endpoints also receive it. Serve the local HTTP API only on loopback: it has no multi-user authentication or document ACLs, and browser cross-origin writes are rejected. [Security](../SECURITY.md) explains storage and sharing.
