"""
Tests for sobench/llm.py — real endpoint integration.

Per docs/TESTING_POLICY.md: no mocks; test drives the real complete() function
against the real endpoint with a prompt derived from real task data under data/.

Real data used:
  data/spatial_domain_identification_task/codes/STAGATE/README.md
  (real STAGATE method repo for spatial_domain_identification_task)

The test skips when:
  - Any of OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL_NAME is absent
  - The real README file is absent
"""

import os
import pytest

_README_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "spatial_domain_identification_task",
    "codes",
    "STAGATE",
    "README.md",
)
_ENV_KEYS = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL_NAME")


def _skip_if_missing() -> None:
    """Skip with explicit reason if env or data file is absent."""
    missing_env = [k for k in _ENV_KEYS if not os.environ.get(k)]
    if missing_env:
        pytest.skip(f"LLM env vars not set: {', '.join(missing_env)}")
    if not os.path.isfile(_README_PATH):
        pytest.skip(f"Real data file absent: {_README_PATH}")


def test_complete_returns_nonempty_text_from_real_task_data():
    """
    Call complete() with a short factual question derived from the STAGATE README.
    Assert the response is a non-empty string (regression guard for the
    empty-content reasoning-model bug when max_tokens is too small).
    """
    # Load .env before checking env — complete() also does this but we need
    # env populated for _skip_if_missing() to see the keys.
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    except Exception:
        pass

    _skip_if_missing()

    # Read a minimal real snippet from the STAGATE README (first 300 chars).
    with open(_README_PATH, encoding="utf-8") as fh:
        readme_snippet = fh.read(300).strip()

    from sobench.llm import complete

    prompt = (
        "Here is the beginning of a bioinformatics tool's README:\n\n"
        f"{readme_snippet}\n\n"
        "In one sentence, what does this tool do?"
    )
    result = complete(prompt)

    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert len(result) > 0, (
        "complete() returned an empty string — likely a reasoning-model "
        "max_tokens issue"
    )
    # Light content check: response should mention spatial or clustering context
    # (robust enough given the README content, but we don't fail on this alone)
    result_lower = result.lower()
    has_relevant_term = any(
        term in result_lower
        for term in ("spatial", "cluster", "transcriptom", "gene", "expression",
                     "domain", "embedding", "neural", "graph", "stagate")
    )
    if not has_relevant_term:
        import warnings
        warnings.warn(
            f"Response did not mention expected spatial-biology terms: {result!r}"
        )
    # Non-empty is the hard assertion; content check is advisory only.
