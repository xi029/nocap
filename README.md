<p align="center"><img src="docs/assets/hero.svg" alt="NoCap — no evidence, no answer. The hallucination firewall for RAG and AI agents." width="100%"></p>

<p align="center">
  <a href="https://github.com/xi029/nocap/actions/workflows/ci.yml"><img src="https://github.com/xi029/nocap/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/nocap-ai/"><img src="https://img.shields.io/pypi/v/nocap-ai?color=8ae4b6&labelColor=202c24" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-8ae4b6?labelColor=202c24" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/MCP-server-8ae4b6?labelColor=202c24" alt="MCP server">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-8ae4b6?labelColor=202c24" alt="Apache-2.0"></a>
  <a href="https://github.com/xi029/nocap/stargazers"><img src="https://img.shields.io/github/stars/xi029/nocap?style=flat&color=8ae4b6&labelColor=202c24" alt="GitHub stars"></a>
</p>

<p align="center">
  <b>Your RAG is capping. 🧢</b><br>
  NoCap checks whether the retrieved evidence actually answers the question <i>before</i> your LLM speaks,<br>
  then routes to <b>answer</b>, <b>retrieve more</b>, <b>abstain</b>, or <b>review a conflict</b>.
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="#-60-second-quickstart">Quickstart</a> ·
  <a href="#-three-ways-to-plug-it-in">SDK · MCP · HTTP</a> ·
  <a href="#-ci-for-hallucinations">CI</a> ·
  <a href="docs/providers.md">Models</a> ·
  <a href="docs/mcp.md">MCP guide</a>
</p>

---

## 🧢 Why

Most RAG pipelines pass the top-k chunks straight to the generator. When those chunks only *mention* the topic, leave out the key detail, or contradict each other, the model fills the gap anyway, and does it confidently.

> "No cap" is slang for "no lie". NoCap adds one step between retrieval and generation that asks:
> **do these excerpts support an answer, partly support it, miss it, or conflict?**
> Then your own policy decides what happens next.

<table>
<tr>
<th width="50%">Without NoCap</th>
<th width="50%">With NoCap</th>
</tr>
<tr>
<td>

```text
Q: How many days do I have for a refund?
A: You have 90 days. ✨        ← invented
```

</td>
<td>

```text
Q: How many days do I have for a refund?
→ review_conflict  (conflicting 0.88)
  refund-policy.md: "within 30 days"
  refund-draft.md:  "within 14 days"
  LLM not called. Ask which source wins.
```

</td>
</tr>
</table>

## ✨ What you get

| | Feature | Why it matters |
| --- | --- | --- |
| 🛡️ | **Evidence gate** | Four routes: `answer` · `retrieve_more` · `abstain` · `review_conflict`. Your generator runs only on `answer`. |
| 🐍 | **3-line Python SDK** | `@gate.guard` wraps any generator. Accepts strings, dicts, LangChain `Document`s and LlamaIndex nodes. |
| 🤖 | **MCP server** | Give Claude Code, Cursor, Codex or any MCP agent a `check_evidence` tool. |
| 🔌 | **Any model as the judge** | Ollama, any **OpenAI-compatible** API (OpenAI, DeepSeek, Qwen, vLLM, LM Studio…), open-weight Laya, hosted Jev. |
| 🧪 | **CI for hallucinations** | `nocap eval` runs labelled route tests and fails the build on **leaks**. Also available as a GitHub Action. |
| ⏪ | **Zero-cost policy replay** | Change thresholds on a saved decision and re-route it with **0 model calls**. |
| 🔍 | **Inspectable traces** | Exact excerpts sent, the distribution, timings and citations, as JSON with a permalink. |
| 🏠 | **Local-first** | FastAPI + SQLite + a no-build web UI. The demo needs no keys, models, embeddings or vector DB. |

## 🚀 60-second quickstart

```sh
pip install nocap-ai
nocap demo     # load fictional sample docs
nocap serve    # open http://127.0.0.1:8787
```

Or from source with [uv](https://docs.astral.sh/uv/): `git clone https://github.com/xi029/nocap && cd nocap && uv sync && uv run nocap demo && uv run nocap serve`.

The default **demo** judge is a clearly labelled lexical simulation, so you can explore everything offline. Switch to a real model in the UI or with `NOCAP_PROVIDER` (see [models](#-bring-your-own-judge)).

![The NoCap workbench flagging a refund-policy conflict: decision distribution, policy replay and evidence](docs/assets/studio.jpg)

<sub>Actual workbench screenshot in demo mode. Demo scores are a lexical simulation, not AI probabilities.</sub>

**Try this:** ask "How do I request a refund?" → drag **Minimum support** to 95% and watch the route change with no model call → click **Add conflicting policy** and ask again.

## 🔌 Three ways to plug it in

![Any retriever → NoCap gate → answer, retrieve_more, abstain or review_conflict](docs/assets/architecture.svg)

### 1. Python SDK: wrap your generator

```python
from nocap import Gate

gate = Gate(provider="ollama")  # or "openai", "laya", "jev", "demo"


@gate.guard(fallback="I couldn't find that in our docs.")
def answer(question, evidence):
    return llm(question, evidence)  # runs ONLY when the evidence supports an answer


answer("How do I request a refund?", retriever.invoke("How do I request a refund?"))
```

Need the details? `verdict = gate.check(question, docs)` gives you `verdict.action`, `verdict.probabilities`, `verdict.evidence` and `verdict.ok`. Async functions work too. Runnable: [`examples/quickstart.py`](examples/quickstart.py).

### 2. MCP: make your agent show its receipts

```sh
claude mcp add nocap -e NOCAP_PROVIDER=ollama -- uvx --from "nocap-ai[mcp]" nocap mcp
```

![Claude Code, Cursor, Codex and other MCP clients call check_evidence and follow next_step](docs/assets/mcp.svg)

Your agent gets `check_evidence`, `ask_knowledge_base`, `add_document` and `replay_decision`. Each verdict carries a `next_step`, such as *"Tell the user the sources do not contain the answer. Do not guess."* Configs for Cursor, Claude Desktop and Codex are in the [MCP guide](docs/mcp.md).

### 3. HTTP: any language, any stack

```sh
curl -s http://127.0.0.1:8787/api/decide -H "Content-Type: application/json" -d '{
  "question": "How do I request a refund?",
  "evidence": [{"id": "r1", "source": "refund-policy.md",
                "text": "To request a refund, email support with the order number."}]
}'
# → {"action": "answer", "reason": "...", "decision": {"probabilities": {...}}, ...}
```

| Route | What your app should do |
| --- | --- |
| `answer` | Generate from the **returned** (judged) excerpts |
| `retrieve_more` | Search again, ask a clarifying question, or stop. Bound the retry loop. |
| `abstain` | Say "I don't know" and skip generation |
| `review_conflict` | Show both sources to a person or your source-of-truth rules |

See the [integration guide](docs/integration.md) and [API reference](docs/api.md).

## 🧪 CI for hallucinations

Write the routes you expect, then fail the build when your RAG would answer without evidence.

```jsonl
{"id": "refund", "question": "How do I request a refund?", "expect": "answer"}
{"id": "pricing", "question": "What is the exact team plan pricing?", "expect": "retrieve_more"}
{"id": "off-topic", "question": "Who won the lunar chess championship?", "expect": "abstain"}
```

```sh
nocap eval cases.jsonl --docs ./knowledge --provider ollama --max-leaks 0
```

![Real nocap eval output: 6/8 routes matched, 0 leaks, 2 over-refusals](docs/assets/eval.svg)

A **leak** means the gate allowed an answer it should have blocked. An **over-refusal** means it blocked an answer the sources supported. Both are counted; you choose which one fails CI. As a GitHub Action:

```yaml
- uses: xi029/nocap@v0.2.0
  with:
    cases: tests/rag-cases.jsonl
    docs: knowledge/
    provider: openai          # set NOCAP_OPENAI_* in env
    max-leaks: 0
```

## 🧠 Bring your own judge

| Provider | Setup | Score meaning |
| --- | --- | --- |
| `ollama` | `ollama pull qwen3.5:4b` and choose **Ollama · local** | Self-reported, normalized, uncalibrated |
| `openai` | `NOCAP_OPENAI_URL`, `NOCAP_OPENAI_MODEL`, `NOCAP_OPENAI_API_KEY`. Works with OpenAI, DeepSeek, Qwen/DashScope, OpenRouter, vLLM, LM Studio | Self-reported, normalized, uncalibrated |
| `laya` | Self-hosted [Laya](https://github.com/NandhaKishorM/laya) `/v1/systemone` | Choice-head distribution, averaged over 4 label rotations |
| `jev` | [TypeSafe Jev](https://docs.typesafe.ai/introduction) API key | Hosted decision distribution |
| `demo` | Nothing | Lexical simulation for exploring the UI |

```dotenv
# .env — for example, DeepSeek as the judge
NOCAP_PROVIDER=openai
NOCAP_OPENAI_URL=https://api.deepseek.com/v1
NOCAP_OPENAI_MODEL=deepseek-chat
NOCAP_OPENAI_API_KEY=sk-...
```

Every judge answers the same typed question; the policy, traces and replay are identical. [Provider setup and troubleshooting →](docs/providers.md)

<details>
<summary><b>Real local run: qwen3.5:4b judging and answering with citations</b></summary>

![A real qwen3.5:4b decision and a cited answer on the sample documents](docs/assets/ollama.jpg)

A real request on a CPU-bound Windows machine, not the demo simulation. It took about 85 seconds end to end there; speed depends entirely on your hardware and model.

</details>

## ⏪ Policy replay

Every decision is saved with its full distribution. Move the thresholds and NoCap recomputes the route from the saved judgment with **zero new model calls**, while the original response stays attached to its original policy. Use it to see how many questions a stricter policy would block before you ship that policy.

```sh
uv run python examples/replay.py    # replay a real Qwen trace, no model running
```

## 🤔 How is this different?

- **Evaluation frameworks** (RAGAS, DeepEval, promptfoo…) score answers *after* generation, usually offline. NoCap makes a **runtime routing decision before generation** and can skip the generator. Use both: NoCap's `nocap eval` tests routes, not answer quality.
- **Guardrail libraries** usually validate *outputs* (format, toxicity, PII). NoCap judges whether the *inputs* support an answer at all, and tells you whether to answer, dig deeper, abstain or escalate.
- **"Answer only from context" prompts** leave the decision inside the same model call that writes the answer. NoCap makes it a separate, inspectable, replayable step with your thresholds.

## 📏 Honest limits

- `answer` means "meets your threshold", not "guaranteed true". LLM judges are uncalibrated; validate thresholds on your own labelled questions.
- Generated citations are checked for valid **IDs**, not semantic entailment.
- The built-in retriever is BM25 (no embeddings). For semantic search, bring your own retriever via the SDK, MCP or `/api/decide`.
- The bundled 8-case fixture is a smoke test, not a benchmark. We publish no invented accuracy, speed or hallucination-reduction numbers. [Methodology →](docs/evaluation.md)
- Local, single-user workbench without auth. See [SECURITY.md](SECURITY.md).

## 🗺️ Roadmap

- [x] OpenAI-compatible judges · MCP server · Python SDK · `nocap eval` + GitHub Action
- [ ] Claim-level entailment check of generated answers
- [ ] Risk / coverage curves from labelled sets
- [ ] Native LangChain `Runnable` and LlamaIndex postprocessor wrappers
- [ ] Shareable, redacted trace cards
- [ ] OpenAI-compatible **proxy mode**: put NoCap in front of any chat app

Ideas and PRs welcome: see [CONTRIBUTING.md](CONTRIBUTING.md) or [open an issue](https://github.com/xi029/nocap/issues).

## ⭐ Support

If NoCap stopped your bot from making something up, **a star helps other builders find it.**

<a href="https://star-history.com/#xi029/nocap&Date"><img src="https://api.star-history.com/svg?repos=xi029/nocap&type=Date" alt="Star history" width="600"></a>

## License

[Apache-2.0](LICENSE). NoCap is an independent project. Thanks to [Laya](https://github.com/NandhaKishorM/laya), [TypeSafe](https://docs.typesafe.ai/api), [Ollama](https://github.com/ollama/ollama) and the [Model Context Protocol](https://modelcontextprotocol.io). Model weights are not included; upstream models keep their own licenses. See [NOTICE](NOTICE).
