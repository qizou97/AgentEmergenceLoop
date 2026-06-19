"""
sobench/steps/s13_write_experience_record.py

s13: Write experience_record.json — always runs, even for blocked cycles.

Reads all AVAILABLE artifacts (guarded by artifact_path(...).exists()), then
calls the LLM to draft a scoped, evidence-backed hypothesis.

status is ALWAYS "hypothesis" at P0 — enforced in Python after LLM returns.
The LLM cannot override this.

For blocked cycles: captures what was attempted and what was learned about
the blocker (spec 7.13 blocked-cycle example).
"""

from __future__ import annotations

import json as _json
from datetime import date

from sobench.workspace import Workspace
from sobench.models import (
    Blocker,
    DataManifest,
    EvaluationContract,
    ExecutionLog,
    ExperienceRecord,
    Interpretation,
    PaperEvidence,
    RawObservations,
    RepoEvidence,
    ResultValidityAudit,
    RiskAudit,
    TaskSpec,
)
from sobench.steps._common import llm_json

_STEP_NAME = "s13_write_experience_record"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark analysis. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT = """\
You are writing an experience record for a spatial-omics benchmark cycle.
This record is a scoped, evidence-backed hypothesis to carry forward.

Task: {task}
Method: {method}
Case: {case}
Blocked: {blocked}

Available artifacts (JSON summaries):
{artifacts_json}

Return ONLY a JSON object with exactly these keys:

{{
  "id": "exp-001",
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "tags": ["<topic-tag>"],
  "finding": "<1-2 sentence scoped hypothesis backed by the artifacts>",
  "evidence": ["<artifact_name.field_path>"],
  "confidence": "<low|medium|high>",
  "failure_conditions": ["<condition under which this finding would NOT hold>"]
}}

RULES:
1. finding must be evidence-backed — cite specific artifact fields.
2. evidence must reference artifact fields that actually appear above (e.g.
   "data_manifest.required[0]", "blocker.detail", "paper_evidence.evaluation_contexts[0]").
3. evidence must be non-empty.
4. For a BLOCKED cycle: capture what was attempted and what was learned about
   the blocker (e.g., which data file is missing and its expected source).
5. tags must include relevant topic identifiers (method, data, metric names etc.).
6. Do NOT include "status" — it is set by the system to "hypothesis".
7. confidence must be one of: low, medium, high.
"""


def _collect_artifacts(workspace: Workspace) -> dict:
    """Read all available JSON artifacts. Skips absent files silently."""
    artifact_classes = [
        ("paper_evidence", PaperEvidence),
        ("repo_evidence", RepoEvidence),
        ("data_manifest", DataManifest),
        ("task_spec", TaskSpec),
        ("evaluation_contract", EvaluationContract),
        ("risk_audit", RiskAudit),
        ("blocker", Blocker),
        ("execution_log", ExecutionLog),
        ("raw_observations", RawObservations),
        ("result_validity_audit", ResultValidityAudit),
        ("interpretation", Interpretation),
    ]
    result = {}
    for name, cls in artifact_classes:
        path = workspace.artifact_path(name)
        if path.exists():
            try:
                result[name] = workspace.read_artifact(name, cls).to_dict()
            except Exception:
                pass
    return result


def run(workspace: Workspace) -> None:
    """
    s13: Always runs. Draft and write experience_record.json.
    status is hardcoded to "hypothesis" — LLM output is ignored for this field.
    """
    available = _collect_artifacts(workspace)

    prompt = _PROMPT.format(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        blocked=str(workspace.blocked),
        artifacts_json=_json.dumps(available, indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    record = ExperienceRecord(
        id=data.get("id") or "exp-001",
        task=data.get("task") or workspace.task,
        method=data.get("method") or workspace.method,
        case=data.get("case") or workspace.case,
        tags=data.get("tags") or [],
        finding=data.get("finding") or "",
        evidence=data.get("evidence") or [],
        confidence=data.get("confidence") or "medium",
        failure_conditions=data.get("failure_conditions") or [],
        # status is ALWAYS "hypothesis" at P0 — hardcoded; LLM cannot override
        status="hypothesis",
        created=date.today().isoformat(),
    )

    workspace.write_artifact("experience_record", record)
