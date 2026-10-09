# Contributing

NoCap welcomes useful, small contributions: retriever adapters, real labelled evaluation sets, checkpoint-specific schema experiments, and better evidence inspection.

```sh
git clone https://github.com/xi029/nocap.git
cd nocap
uv sync --extra dev
uv run nocap demo
uv run nocap serve
```

Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q` before opening a pull request. Default tests never download weights or call a paid API. Use `uv run python scripts/evaluate.py --provider demo` for the fixture, and choose `ollama` or `laya` for local integration checks.

Keep policy logic deterministic and independent from inference. Provider errors must be visible; never silently replace live inference with demo scores. Any new backend must document its probability semantics, truncation behavior and data destination. Do not call self-reported probabilities calibrated confidence.

For UI changes, verify keyboard access and widths of 375, 768, 1024 and 1440 pixels. Keep browser assets local. Cite source documents using text nodes, never render untrusted HTML. Include screenshots when changing layout.

Frontend sources use Prettier formatting (`.prettierrc.json`). If Node is available, run `npx prettier --write "src/nocap/static/*.{js,css,html,svg}"`. Node is not needed to run the application.

Issue reports and traces must use public or synthetic documents. Exported traces include document excerpts. Tests are for meaningful behavior, not private user data. By contributing, you agree that your contribution is available under Apache-2.0.
