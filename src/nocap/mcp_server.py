"""MCP server: give Claude Code, Cursor, Codex and any MCP agent a "no evidence, no answer" tool.

Run with ``nocap mcp`` (stdio). Requires the optional extra: ``pip install "nocap-ai[mcp]"``.
"""

from pydantic import BaseModel, Field

from .config import Settings
from .engine import replay, run_decision, run_query
from .models import DecisionQuery, Policy, Query
from .providers import ProviderError
from .store import Store

NEXT_STEP = {
    "answer": "Answer using ONLY the judged excerpts and cite their ids. Add nothing unsupported.",
    "retrieve_more": "Do not answer yet. Search for more specific evidence, or ask the user a "
    "clarifying question. Do not fill gaps from memory.",
    "abstain": "Tell the user the available sources do not contain the answer. Do not guess.",
    "review_conflict": "Sources disagree. Show the conflicting excerpts and ask the user which "
    "is authoritative. Do not silently pick one.",
}

INSTRUCTIONS = (
    "NoCap is an evidence gate. Before stating facts drawn from documents, search results, "
    "files or tool output, call check_evidence with the question and the exact excerpts you "
    "plan to rely on. Follow the returned next_step. Never answer when action is not 'answer'."
)


class EvidenceItem(BaseModel):
    text: str = Field(description="The exact excerpt you would rely on.")
    source: str = Field(default="external", description="File path, URL or title.")
    id: str | None = Field(default=None, description="Optional stable id for citations.")


def _summary(trace: dict) -> dict:
    return {
        "action": trace["action"],
        "next_step": NEXT_STEP[trace["action"]],
        "reason": trace["reason"],
        "probabilities": {k: round(v, 3) for k, v in trace["decision"]["probabilities"].items()},
        "provider": f"{trace['decision']['provider']} / {trace['decision']['model']}",
        "evidence": [
            {"id": e["id"], "source": e["source"], "text": e["text"]} for e in trace["evidence"]
        ],
        "warnings": trace["warnings"],
        "trace_id": trace["id"],
    }


def create_server(settings: Settings | None = None):
    from mcp.server.mcpserver import MCPServer

    from . import __version__
    from .gate import to_evidence

    settings = settings or Settings()
    store = Store(settings.data_dir)
    server = MCPServer("nocap", instructions=INSTRUCTIONS, version=__version__)

    @server.tool()
    async def check_evidence(
        question: str,
        evidence: list[EvidenceItem],
        support_threshold: float = 0.70,
        conflict_threshold: float = 0.35,
    ) -> dict:
        """Judge whether excerpts support an answer: answer, retrieve_more, abstain or
        review_conflict. Call this before answering from retrieved or searched content."""
        try:
            trace = await run_decision(
                store,
                settings,
                DecisionQuery(
                    question=question,
                    evidence=to_evidence(item.model_dump() for item in evidence),
                    policy=Policy(
                        support_threshold=support_threshold, conflict_threshold=conflict_threshold
                    ),
                ),
            )
        except ProviderError as exc:
            return {
                "action": "error",
                "next_step": "Do not answer; the gate is unavailable.",
                "reason": str(exc),
            }
        return _summary(trace)

    @server.tool()
    async def ask_knowledge_base(question: str, top_k: int = 4) -> dict:
        """Search the local NoCap knowledge base (BM25) and gate the results in one call."""
        try:
            trace = await run_query(
                store, settings, Query(question=question, top_k=top_k, generator="none")
            )
        except ProviderError as exc:
            return {
                "action": "error",
                "next_step": "Do not answer; the gate is unavailable.",
                "reason": str(exc),
            }
        return _summary(trace)

    @server.tool()
    def add_document(name: str, text: str) -> dict:
        """Add a Markdown or text document to the local NoCap knowledge base."""
        return store.add_document(name, text)

    @server.tool()
    def replay_decision(
        trace_id: str, support_threshold: float = 0.70, conflict_threshold: float = 0.35
    ) -> dict:
        """Re-route a saved decision under a new policy with zero model calls."""
        trace = store.trace(trace_id)
        if trace is None:
            return {"error": "Trace not found."}
        return replay(
            trace,
            Policy(support_threshold=support_threshold, conflict_threshold=conflict_threshold),
        )

    return server


def main():
    try:
        server = create_server()
    except ImportError as exc:
        raise SystemExit('The MCP server needs the extra: pip install "nocap-ai[mcp]"') from exc
    server.run("stdio")
