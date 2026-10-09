**JevLens is now NoCap.** No evidence, no answer. 🧢

### New
- **Python SDK**: `from nocap import Gate`; `@gate.guard(fallback=...)` runs your generator only when evidence supports an answer. Accepts strings, dicts, LangChain Documents and LlamaIndex nodes.
- **MCP server**: `nocap mcp` exposes `check_evidence`, `ask_knowledge_base`, `add_document` and `replay_decision` to Claude Code, Cursor, Codex and any MCP client (`pip install "nocap[mcp]"`).
- **OpenAI-compatible judge and generator**: OpenAI, DeepSeek, Qwen/DashScope, OpenRouter, vLLM, LM Studio and more via `NOCAP_OPENAI_URL` / `NOCAP_OPENAI_MODEL` / `NOCAP_OPENAI_API_KEY`.
- **`nocap eval`**: labelled route tests with leak / over-refusal counts and CI exit codes, plus a GitHub Action (`uses: xi029/nocap@v0.2.0`).
- **Trace permalinks**: `http://127.0.0.1:8787/#trace=<id>` opens any saved decision.

### Changed
- Package, CLI and import name: `jevlens` → `nocap`. Environment prefix: `JEVLENS_` → `NOCAP_`. The SQLite file is now `nocap.sqlite3`; an existing `jevlens.sqlite3` in the same data directory is renamed automatically, keeping your documents and history.

### Limits
LLM judges are uncalibrated; `answer` means "meets your threshold", not "true". Citations are checked for valid IDs, not entailment. The bundled fixture is a smoke test, not a benchmark.
