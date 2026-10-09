# NoCap as an MCP server

![Claude Code, Cursor, Codex and any MCP client call NoCap's check_evidence tool](assets/mcp.svg)

Agents read files, search results and tool output, then answer with total confidence. `nocap mcp` gives any [Model Context Protocol](https://modelcontextprotocol.io) client an evidence gate. The agent sends the question and the excerpts it plans to rely on; NoCap returns a route and a plain-language `next_step` the agent should follow.

The server uses stdio and needs the optional extra: `pip install "nocap[mcp]"`. The examples below use [`uvx`](https://docs.astral.sh/uv/), which downloads and runs it on demand.

## Tools

| Tool | What it does |
| --- | --- |
| `check_evidence(question, evidence, support_threshold?, conflict_threshold?)` | Judge caller-supplied excerpts. `evidence` is a list of `{text, source?, id?}`. |
| `ask_knowledge_base(question, top_k?)` | BM25 search over the local NoCap workspace, then gate the results. |
| `add_document(name, text)` | Add a Markdown/text document to the local workspace. |
| `replay_decision(trace_id, support_threshold?, conflict_threshold?)` | Re-route a saved decision with 0 model calls. |

Each decision returns `action`, `next_step`, `reason`, `probabilities`, the judged `evidence`, `warnings` and a `trace_id`. Open `nocap serve` with the same `NOCAP_DATA_DIR` to inspect every decision your agent made at `http://127.0.0.1:8787/#trace=<trace_id>`.

## Client configuration

Set `NOCAP_PROVIDER` to the judge you want (`ollama`, `openai`, `laya`, `jev`; `demo` is a lexical simulation for trying it out). Use an absolute `NOCAP_DATA_DIR` so traces land in one place regardless of the agent's working directory.

### Claude Code

```sh
claude mcp add nocap -e NOCAP_PROVIDER=ollama -- uvx --from "nocap[mcp]" nocap mcp
```

### Cursor / Claude Desktop / Windsurf

`.cursor/mcp.json` (Cursor) or `claude_desktop_config.json` (Claude Desktop):

```json
{
  "mcpServers": {
    "nocap": {
      "command": "uvx",
      "args": ["--from", "nocap[mcp]", "nocap", "mcp"],
      "env": { "NOCAP_PROVIDER": "ollama", "NOCAP_DATA_DIR": "/absolute/path/to/nocap-data" }
    }
  }
}
```

### Codex CLI

`~/.codex/config.toml`:

```toml
[mcp_servers.nocap]
command = "uvx"
args = ["--from", "nocap[mcp]", "nocap", "mcp"]
env = { NOCAP_PROVIDER = "ollama" }
```

### Using an OpenAI-compatible judge

```json
"env": {
  "NOCAP_PROVIDER": "openai",
  "NOCAP_OPENAI_URL": "https://api.deepseek.com/v1",
  "NOCAP_OPENAI_MODEL": "deepseek-chat",
  "NOCAP_OPENAI_API_KEY": "sk-..."
}
```

## Tell the agent when to use it

The server sends instructions to clients that support them. For stronger behavior, add a rule to `CLAUDE.md`, `AGENTS.md` or `.cursorrules`:

```md
Before stating facts taken from documentation, search results or files, call the
`nocap` `check_evidence` tool with the question and the exact excerpts you rely on.
Follow its `next_step`. If the action is not `answer`, do not answer from memory.
```

## Limits

The gate judges only the excerpts the agent submits; it cannot see what the agent left out. An `answer` route is permission under your thresholds, not proof of truth. The MCP server is a local, single-user process without authentication. Hosted judges receive the question and excerpts.
