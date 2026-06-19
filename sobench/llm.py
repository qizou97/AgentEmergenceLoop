"""
sobench/llm.py — thin LLM wrapper for all pipeline steps.

Public API:
    complete(prompt: str, system: str = "") -> str

Reads OPENAI_BASE_URL, OPENAI_MODEL_NAME, OPENAI_API_KEY from the environment
(loaded from .env at the repo root via python-dotenv). Config is read at call
time so callers / tests that set env vars after import still work.

No network calls at import time.
"""

from __future__ import annotations

import os


def _load_env() -> None:
    """Load .env from the repo root robustly; silently skip on any error."""
    try:
        from dotenv import load_dotenv
        _here = os.path.dirname(os.path.abspath(__file__))
        _repo_root = os.path.dirname(_here)
        _dotenv_path = os.path.join(_repo_root, ".env")
        load_dotenv(_dotenv_path)
    except Exception:
        pass


def complete(prompt: str, system: str = "") -> str:
    """
    Issue a single chat-completion request and return the model's reply text.

    Parameters
    ----------
    prompt : str
        The user message to send.
    system : str, optional
        System message (empty string → no system message).

    Returns
    -------
    str
        The text content of the first completion choice.

    Notes
    -----
    Uses max_tokens=8192 to ensure the reasoning model has enough budget to
    produce non-empty message.content (reasoning tokens are spent first; if
    max_tokens is too small the content comes back as an empty string even
    though finish_reason is 'stop').  8192 is needed for later steps (s08+)
    whose prompts include multiple accumulated JSON artifacts and can generate
    long risk / evaluation / experience responses.
    """
    _load_env()

    from openai import OpenAI  # imported here so the module is importable without the SDK

    api_key = os.environ["OPENAI_API_KEY"]
    base_url = os.environ["OPENAI_BASE_URL"]
    model = os.environ["OPENAI_MODEL_NAME"]

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=8192,
    )

    return response.choices[0].message.content or ""
