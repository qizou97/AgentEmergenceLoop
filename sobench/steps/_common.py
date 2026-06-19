"""
sobench/steps/_common.py — shared helpers for all step modules.

Helpers exported:
  - llm_json(prompt, system="") -> dict
      Calls LLM and extracts the first JSON object from the response text.
      Tries json.loads directly first; if that fails, strips ```json fences
      then extracts the first balanced {...} block. Raises ValueError if no
      JSON can be found.

  - set_blocker(workspace, raised_by_step, reason, detail, evidence,
                resolution, human_action_required=True) -> None
      Constructs a Blocker and writes blocker.json to the workspace.

Only helpers actually used by s01–s04 live here. Extend for later tasks.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from sobench.models import Blocker

if TYPE_CHECKING:
    from sobench.workspace import Workspace


# ---------------------------------------------------------------------------
# LLM → JSON extraction
# ---------------------------------------------------------------------------

def llm_json(prompt: str, system: str = "") -> dict:
    """
    Call the LLM with *prompt* and return its response parsed as a JSON dict.

    Strategy (applied in order):
    1. Try json.loads on the full response text.
    2. Strip ```json ... ``` fences if present, then try json.loads.
    3. Extract the first balanced {...} block (handles prose wrappers).

    Raises
    ------
    ValueError
        If no valid JSON object can be extracted from the LLM response.
    """
    from sobench.llm import complete

    text = complete(prompt, system=system)

    # Attempt 1: whole text is JSON
    stripped = text.strip()
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Attempt 2: strip ```json ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.DOTALL)
    if fence_match:
        try:
            result = json.loads(fence_match.group(1))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Attempt 3: extract first balanced { ... } block
    block = _extract_first_json_object(stripped)
    if block is not None:
        try:
            result = json.loads(block)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract a JSON object from LLM response. "
        f"First 300 chars: {text[:300]!r}"
    )


def _extract_first_json_object(text: str) -> str | None:
    """
    Find the first '{' in *text* and return the balanced {...} substring,
    or None if no balanced block is found.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i, ch in enumerate(text[start:], start=start):
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


# ---------------------------------------------------------------------------
# Blocker writer
# ---------------------------------------------------------------------------

def set_blocker(
    workspace: "Workspace",
    raised_by_step: str,
    reason: str,
    detail: str,
    evidence: str,
    resolution: str,
    human_action_required: bool = True,
) -> None:
    """Write blocker.json to *workspace* with blocked: true."""
    blocker = Blocker(
        blocked=True,
        raised_by_step=raised_by_step,
        reason=reason,
        detail=detail,
        evidence=evidence,
        resolution=resolution,
        human_action_required=human_action_required,
    )
    workspace.write_artifact("blocker", blocker)
