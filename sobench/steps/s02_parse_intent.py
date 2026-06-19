"""
sobench/steps/s02_parse_intent.py

s02: LLM extracts structured fields from benchmark_intent.md.
Writes parsed_intent.json.
Sets blocker if task AND/OR method cannot be parsed (empty after extraction).
"""

from __future__ import annotations

from sobench.workspace import Workspace
from sobench.models import ParsedIntent
from sobench.steps._common import llm_json, set_blocker

_STEP_NAME = "s02_parse_intent"

_SYSTEM = (
    "You are a precise JSON extractor. Extract information from a benchmark intent document "
    "and return ONLY a valid JSON object — no prose, no markdown fences, no commentary."
)

_PROMPT_TEMPLATE = """\
Extract the following fields from the benchmark intent document below.
Return ONLY a JSON object with exactly these keys (use empty string "" if a field is not found):

{{
  "task": "<task name, e.g. spatial_domain_identification>",
  "method": "<method name, e.g. STAGATE>",
  "case": "<case identifier, e.g. DLPFC_151673>",
  "paper_path": "<path to PDF paper file>",
  "repo_path": "<path to code repository>",
  "data_notes": "<any notes about the data>",
  "reconstruction_goal": "<what needs to be reproduced>",
  "human_observations": "<any human observations or prior knowledge>"
}}

Benchmark intent document:
---
{text}
---
"""


def run(workspace: Workspace) -> None:
    """Parse benchmark_intent.md via LLM and write parsed_intent.json."""
    intent_path = workspace.dir / "benchmark_intent.md"
    text = intent_path.read_text(encoding="utf-8")

    prompt = _PROMPT_TEMPLATE.format(text=text)
    data = llm_json(prompt, system=_SYSTEM)

    pi = ParsedIntent(
        task=data.get("task", ""),
        method=data.get("method", ""),
        case=data.get("case", ""),
        paper_path=data.get("paper_path", ""),
        repo_path=data.get("repo_path", ""),
        data_notes=data.get("data_notes", ""),
        reconstruction_goal=data.get("reconstruction_goal", ""),
        human_observations=data.get("human_observations", ""),
    )

    workspace.write_artifact("parsed_intent", pi)

    # Set blocker if task AND/OR method cannot be determined
    if not pi.task.strip() or not pi.method.strip():
        missing = []
        if not pi.task.strip():
            missing.append("task")
        if not pi.method.strip():
            missing.append("method")
        set_blocker(
            workspace,
            raised_by_step=_STEP_NAME,
            reason=f"Cannot parse required fields: {', '.join(missing)}",
            detail=(
                f"benchmark_intent.md does not contain parseable {' or '.join(missing)} fields. "
                f"Extracted task={pi.task!r}, method={pi.method!r}."
            ),
            evidence="parsed_intent.json — task and/or method field is empty",
            resolution=(
                "Add ## Task and ## Method sections to benchmark_intent.md with "
                "the task name and method name respectively."
            ),
            human_action_required=True,
        )
