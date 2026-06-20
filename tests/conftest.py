"""
conftest.py — load .env at session start.

The M1 deterministic substrate makes no LLM calls, so no substrate test needs an
API key. This loader is retained only so that opt-in integration runs (and the
M2-reserved sobench/llm.py) can read OPENAI_* config without each entry point
re-loading it.
"""

from pathlib import Path


def pytest_configure(config):
    """Load .env from the repo root before collection (best-effort, never fails)."""
    try:
        from dotenv import load_dotenv

        repo_root = Path(__file__).parents[1]
        load_dotenv(repo_root / ".env")
    except Exception:
        pass
