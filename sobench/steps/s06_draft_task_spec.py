"""
sobench/steps/s06_draft_task_spec.py

s06: Select one evaluation context, reconstruct concrete task, list assumptions
and unresolved questions. Write task_spec.json.

Sets a blocker if no evaluation context can be selected with sufficient
confidence (e.g. LLM returns no source_context / empty contexts).
Still writes task_spec.json with what was determined.
"""

from __future__ import annotations

import json as _json

from sobench.workspace import Workspace
from sobench.models import (
    ParsedIntent,
    PaperEvidence,
    RepoEvidence,
    DataManifest,
    TaskSpec,
)
from sobench.steps._common import llm_json, set_blocker

_STEP_NAME = "s06_draft_task_spec"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark construction. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
You are reconstructing a concrete benchmark task specification from evidence.

Select ONE evaluation context from the paper_evidence.evaluation_contexts list
(use its id as source_context). Then reconstruct the concrete task.

If no evaluation context can be selected with sufficient confidence (evaluation_contexts
is empty or none are relevant to the case), set source_context to "" and note the
reason in unresolved.

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "source_context": "<id of selected evaluation context, or empty string if none>",
  "input_description": "<what input data the method receives>",
  "expected_output": "<what the method should produce>",
  "primary_metric": {{"name": "<metric name>", "resolved": <true or false>}},
  "assumptions": ["<assumption made>"],
  "unresolved": ["<open question or unresolved item>"]
}}

Task: {task}
Method: {method}
Case: {case}

Paper evidence:
{paper_evidence_json}

Repo evidence:
{repo_evidence_json}

Data manifest:
{data_manifest_json}

Parsed intent:
{parsed_intent_json}
"""


def run(workspace: Workspace) -> None:
    """Draft task spec from prior artifacts. Sets blocker if no context selectable."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)
    pe = workspace.read_artifact("paper_evidence", PaperEvidence)
    re = workspace.read_artifact("repo_evidence", RepoEvidence)
    dm = workspace.read_artifact("data_manifest", DataManifest)

    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        case=pi.case,
        paper_evidence_json=_json.dumps(pe.to_dict(), indent=2),
        repo_evidence_json=_json.dumps(re.to_dict(), indent=2),
        data_manifest_json=_json.dumps(dm.to_dict(), indent=2),
        parsed_intent_json=_json.dumps(pi.to_dict(), indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    # Resolve identity fields
    task = data.get("task") or pi.task
    method = data.get("method") or pi.method
    case = data.get("case") or pi.case

    source_context = data.get("source_context", "")

    ts = TaskSpec(
        task=task,
        method=method,
        case=case,
        source_context=source_context,
        input_description=data.get("input_description", ""),
        expected_output=data.get("expected_output", ""),
        primary_metric=data.get("primary_metric", {"name": "", "resolved": False}),
        assumptions=data.get("assumptions", []),
        unresolved=data.get("unresolved", []),
    )

    # Always write task_spec.json
    workspace.write_artifact("task_spec", ts)

    # Set blocker if no evaluation context could be selected
    if not source_context:
        set_blocker(
            workspace=workspace,
            raised_by_step=_STEP_NAME,
            reason="no evaluation context could be selected with sufficient confidence",
            detail=(
                "s06 could not identify a selectable evaluation context from paper_evidence. "
                "paper_evidence.evaluation_contexts may be empty or none are relevant to this case."
            ),
            evidence="paper_evidence.evaluation_contexts is empty or LLM returned no source_context",
            resolution=(
                "Re-run s03 to extract evaluation contexts from the paper, or manually add "
                "evaluation context to paper_evidence.json and re-run from s06."
            ),
            human_action_required=True,
        )
