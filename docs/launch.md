# Launch kit

Maintainer checklist and drafts. Nothing here has been posted anywhere.

## 1. Repository

- Rename `xi029/jev-lens` → **`xi029/nocap`** with `./scripts/publish.ps1`. GitHub keeps redirects from the old URL. The script also sets the description, homepage and topics.
- Description: `No evidence, no answer. 🧢 System One evidence gate for RAG & AI agents: Jev / Laya / any LLM judges before your LLM speaks. MCP server, Python SDK, CI route tests.`
- Topics: `system-one` `jev` `laya` `rag` `hallucination` `llm` `mcp` `mcp-server` `ai-agents` `guardrails` `ollama` `openai` `deepseek` `langchain` `llamaindex` `claude-code` `local-first` `python` `evaluation`
- Social preview: upload `docs/assets/social-preview.png` (1280×640) in **Settings → General → Social preview**.
- Pin the repository on your profile.

## 2. Package and release

`pip install nocap-ai`, `uvx --from "nocap-ai[mcp]"` and the README's PyPI badge only work after the package is on PyPI. PyPI rejected `nocap` as too similar to an existing project, so the distribution is `nocap-ai`; the import name and CLI stay `nocap`.

```sh
uv build
uv publish            # needs a PyPI token: UV_PUBLISH_TOKEN=pypi-...
git tag v0.2.0 && git push origin v0.2.0
gh release create v0.2.0 --title "NoCap 0.2 — no evidence, no answer" --notes-file docs/launch-release.md
```

The tag makes `uses: xi029/nocap@v0.2.0` work. To list the Action on the GitHub Marketplace, tick "Publish this Action to the GitHub Marketplace" when you create the release.

Also consider submitting the MCP server to the [official MCP registry](https://github.com/modelcontextprotocol/registry) and awesome lists (`awesome-mcp-servers`, `awesome-rag`, `awesome-llm-apps`, `awesome-local-ai`).

## 3. Demo asset

A 20-second GIF/MP4 usually beats any screenshot. Suggested shot list:

1. `nocap demo && nocap serve`, then ask "How do I request a refund?" → **answer**.
2. Drag **Minimum support** to 95% → route flips, "0 model calls".
3. **Add conflicting policy** → ask again → **review_conflict** with 30 vs 14 days.
4. Cut to Claude Code calling `check_evidence` and replying "the sources don't say".

## 4. Announcement drafts

**X / Bluesky**

> Your RAG is capping. 🧢
>
> I built NoCap, a System One gate (Jev / Laya / any LLM as the judge) that asks "do these chunks actually answer the question?" *before* your LLM speaks, then routes to answer / retrieve more / abstain / flag conflict.
>
> - 3-line Python SDK
> - MCP server for Claude Code & Cursor
> - any OpenAI-compatible or Ollama model as the judge
> - `nocap eval` fails CI on hallucination leaks
>
> Local-first, Apache-2.0: github.com/xi029/nocap

**Show HN**: *Show HN: NoCap – decide whether retrieved evidence supports an answer before generating*

> NoCap sits between retrieval and generation. It asks a judge model (Ollama, any OpenAI-compatible API, or a decision model such as Laya) for a four-way distribution (supported / partial / missing / conflicting), applies your thresholds, and only lets the generator run on "answer". Each decision is saved, so you can replay a stricter threshold with no model calls and see what would have been blocked. There's an MCP server so coding agents can call it, and `nocap eval` for route regression tests in CI. LLM judges are uncalibrated and we don't claim accuracy numbers; the traces show exactly what was judged so you can check.

**r/LocalLLaMA**: lead with Ollama + `qwen3.5:4b` running fully offline, and include the screenshot of the real local run.

**V2EX / 掘金 / 知乎（中文）**

> 做 RAG 最怕的不是检索不到，而是检索到“沾边”的内容后模型开始一本正经地编。
> 我做了个开源小工具 **NoCap**（No cap = 不吹牛）：借最近很火的 System One 思路（Jev / Laya 这类只做判断、不写文字的决策模型），在大模型生成之前，先让裁判模型判断证据是“支持 / 部分 / 缺失 / 冲突”，再按你设的阈值决定回答、继续检索、拒答或提示冲突。
> 支持 Ollama、DeepSeek、通义千问等任意 OpenAI 兼容接口；有 Python SDK（3 行接入）、MCP Server（Claude Code / Cursor 直接用），还能用 `nocap eval` 在 CI 里给“幻觉”写单元测试。
> 本地优先，Apache-2.0：github.com/xi029/nocap

## 5. Honesty rules for every post

No invented accuracy, speed, token-savings or "hallucination reduced by X%" numbers. The bundled fixture is a smoke test. LLM judge scores are uncalibrated. Say so; it builds more trust than a benchmark you can't defend.
