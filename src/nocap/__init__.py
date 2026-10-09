"""NoCap: the hallucination firewall for RAG and AI agents. No evidence, no answer."""

__version__ = "0.2.0"

from .gate import Blocked, Gate, Verdict, to_evidence  # noqa: E402

__all__ = ["Blocked", "Gate", "Verdict", "__version__", "to_evidence"]
