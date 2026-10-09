import argparse
import asyncio
import json
from pathlib import Path

from .config import Settings
from .engine import run_query
from .models import Policy, Query
from .samples import DOCUMENTS
from .store import Store

PROVIDERS = ["demo", "ollama", "openai", "laya", "jev"]


def main():
    parser = argparse.ArgumentParser(
        prog="nocap", description="NoCap — no evidence, no answer. A hallucination firewall."
    )
    sub = parser.add_subparsers(dest="command")
    serve = sub.add_parser("serve", help="Open the local evidence workbench")
    serve.add_argument("--port", type=int, default=8787)
    sub.add_parser("demo", help="Load the sample documents")
    sub.add_parser("mcp", help="Run the MCP server (stdio) for Claude Code, Cursor and agents")
    ask = sub.add_parser("ask", help="Ask a question and print a JSON trace")
    ask.add_argument("question")
    ask.add_argument("--provider", choices=PROVIDERS)
    ask.add_argument("--generate", action="store_true", help="Generate accepted answers")
    ask.add_argument("--generator", choices=["ollama", "openai"], default="ollama")
    ingest = sub.add_parser("ingest", help="Import a UTF-8 Markdown or text file")
    ingest.add_argument("path", type=Path)
    check = sub.add_parser("eval", help="Run labelled route tests; non-zero exit on failure")
    check.add_argument("cases", type=Path, help=".jsonl or .json list of test cases")
    check.add_argument("--provider", choices=PROVIDERS)
    check.add_argument("--docs", type=Path, action="append", default=[], help="File or folder")
    check.add_argument("--samples", action="store_true", help="Also load the bundled samples")
    check.add_argument("--support", type=float, default=0.70, help="Support threshold")
    check.add_argument("--conflict", type=float, default=0.35, help="Conflict threshold")
    check.add_argument("--min-accuracy", type=float, default=0.0, help="Fail below this (0-1)")
    check.add_argument("--max-leaks", type=int, default=None, help="Fail above this many leaks")
    check.add_argument("--output", type=Path, help="Write a JSON report")
    args = parser.parse_args()
    settings = Settings()
    if args.command in {None, "serve"}:
        import uvicorn

        uvicorn.run(
            "nocap.app:create_app",
            factory=True,
            host="127.0.0.1",
            port=getattr(args, "port", 8787),
        )
        return
    if args.command == "mcp":
        from .mcp_server import main as mcp_main

        mcp_main()
        return
    if args.command == "eval":
        from .evaluation import load_cases, print_report, run_eval

        try:
            cases = load_cases(args.cases)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        report = asyncio.run(
            run_eval(
                cases,
                settings,
                provider=args.provider,
                policy=Policy(support_threshold=args.support, conflict_threshold=args.conflict),
                docs=args.docs,
                samples=args.samples,
            )
        )
        print_report(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        failed = (
            report["errors"]
            or report["passed"] < args.min_accuracy * report["total"]
            or (args.max_leaks is not None and report["leaks"] > args.max_leaks)
        )
        raise SystemExit(1 if failed else 0)
    store = Store(settings.data_dir)
    if args.command == "demo":
        for name, text in DOCUMENTS.items():
            store.add_document(name, text)
        print("Sample documents loaded. Run: nocap serve")
    elif args.command == "ingest":
        if args.path.suffix.lower() not in {".txt", ".md"} or args.path.stat().st_size > 200_000:
            parser.error("Use a UTF-8 .md or .txt file of at most 200 KB.")
        print(
            json.dumps(
                store.add_document(args.path.name, args.path.read_text(encoding="utf-8-sig"))
            )
        )
    elif args.command == "ask":
        trace = asyncio.run(
            run_query(
                store,
                settings,
                Query(
                    question=args.question,
                    provider=args.provider,
                    generator=args.generator if args.generate else "extractive",
                ),
            )
        )
        print(json.dumps(trace, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
