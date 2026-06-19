"""
conftest.py — load .env at session start so OPENAI_API_KEY is available for
skipif markers that run at collection time.
"""

from pathlib import Path


def pytest_configure(config):
    """Load .env from repo root before collection so env-gated tests are not skipped falsely."""
    try:
        from dotenv import load_dotenv
        repo_root = Path(__file__).parents[1]
        load_dotenv(repo_root / ".env")
    except Exception:
        pass
