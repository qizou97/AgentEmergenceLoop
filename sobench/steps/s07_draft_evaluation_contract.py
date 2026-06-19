"""
sobench/steps/s07_draft_evaluation_contract.py

s07: Resolve data and metric requirements, flag ambiguous or blocked items.
Write evaluation_contract.json.

metric.resolved: false is a VALID output — do NOT force resolution.
No blocker set by this step.
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
    EvaluationContract,
)
from sobench.steps._common import llm_json

_STEP_NAME = "s07_draft_evaluation_contract"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark construction. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
You are drafting an evaluation contract for a spatial-omics benchmark reconstruction.

Resolve what is known about the metric and data requirements. Flag items that are
ambiguous or blocked. metric.resolved: false is a VALID output — record uncertainty,
do NOT invent resolution.

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "metric": {{
    "name": "<primary metric name>",
    "resolved": <true if metric can be computed unambiguously, false otherwise>,
    "implementation": "<suggested implementation, e.g. sklearn.metrics.adjusted_rand_score, or empty>",
    "provenance": "<where metric is confirmed>",
    "known_risks": ["<risk related to this metric>"]
  }},
  "data_requirements_resolved": <true if all required data is available, false otherwise>,
  "data_blockers": ["<description of data item blocking resolution>"],
  "open_questions": ["<open question about evaluation>"]
}}

Task: {task}
Method: {method}
Case: {case}

Task spec:
{task_spec_json}

Paper evidence:
{paper_evidence_json}

Repo evidence:
{repo_evidence_json}

Data manifest:
{data_manifest_json}
"""


def run(workspace: Workspace) -> None:
    """Draft evaluation contract from prior artifacts. Does not set a blocker."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)
    pe = workspace.read_artifact("paper_evidence", PaperEvidence)
    re = workspace.read_artifact("repo_evidence", RepoEvidence)
    dm = workspace.read_artifact("data_manifest", DataManifest)
    ts = workspace.read_artifact("task_spec", TaskSpec)

    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        case=pi.case,
        task_spec_json=_json.dumps(ts.to_dict(), indent=2),
        paper_evidence_json=_json.dumps(pe.to_dict(), indent=2),
        repo_evidence_json=_json.dumps(re.to_dict(), indent=2),
        data_manifest_json=_json.dumps(dm.to_dict(), indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    # Resolve identity fields
    task = data.get("task") or pi.task
    method = data.get("method") or pi.method
    case = data.get("case") or pi.case

    # Build metric dict — ensure 'resolved' is a bool
    metric_raw = data.get("metric", {})
    if not isinstance(metric_raw, dict):
        metric_raw = {}
    resolved_raw = metric_raw.get("resolved", False)
    # Normalize to bool in case LLM returns string "false"/"true"
    if isinstance(resolved_raw, str):
        resolved_raw = resolved_raw.lower() == "true"
    metric = {
        "name": metric_raw.get("name", ts.primary_metric.get("name", "")),
        "resolved": bool(resolved_raw),
        "implementation": metric_raw.get("implementation", ""),
        "provenance": metric_raw.get("provenance", ""),
        "known_risks": metric_raw.get("known_risks", []),
    }

    data_requirements_resolved = data.get("data_requirements_resolved", False)
    if isinstance(data_requirements_resolved, str):
        data_requirements_resolved = data_requirements_resolved.lower() == "true"

    ec = EvaluationContract(
        task=task,
        method=method,
        case=case,
        metric=metric,
        data_requirements_resolved=bool(data_requirements_resolved),
        data_blockers=data.get("data_blockers", []),
        open_questions=data.get("open_questions", []),
    )

    workspace.write_artifact("evaluation_contract", ec)
    # No blocker from s07
