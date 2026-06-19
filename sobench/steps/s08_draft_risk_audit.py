"""
sobench/steps/s08_draft_risk_audit.py

s08: Enumerate risks across categories data/metric/coordinate/code/reproducibility.
Write risk_audit.json ALWAYS, even if the risk list is empty.

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
    RiskAudit,
)
from sobench.steps._common import llm_json

_STEP_NAME = "s08_draft_risk_audit"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark construction. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
You are auditing risks for a spatial-omics benchmark reconstruction.

Enumerate all benchmark-construction risks across these categories:
  data, metric, coordinate, code, reproducibility

For each risk produce an entry with id, category, description, severity
(high/medium/low), evidence (reference to a specific field in a prior artifact),
and mitigation.

If there are genuinely no risks, return an empty list.

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "risks": [
    {{
      "id": "risk-001",
      "category": "<data|metric|coordinate|code|reproducibility>",
      "description": "<description of the risk>",
      "severity": "<high|medium|low>",
      "evidence": "<reference to prior artifact field, e.g. data_manifest.required[0].available=false>",
      "mitigation": "<suggested mitigation>"
    }}
  ],
  "overall_confidence": "<high|medium|low — overall confidence in being able to reproduce>",
  "blocker_risk_ids": ["<id of any risk that would block execution>"]
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

Task spec:
{task_spec_json}

Evaluation contract:
{evaluation_contract_json}
"""


def run(workspace: Workspace) -> None:
    """Enumerate risks from all prior artifacts and write risk_audit.json. Always writes."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)
    pe = workspace.read_artifact("paper_evidence", PaperEvidence)
    re = workspace.read_artifact("repo_evidence", RepoEvidence)
    dm = workspace.read_artifact("data_manifest", DataManifest)
    ts = workspace.read_artifact("task_spec", TaskSpec)
    ec = workspace.read_artifact("evaluation_contract", EvaluationContract)

    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        case=pi.case,
        paper_evidence_json=_json.dumps(pe.to_dict(), indent=2),
        repo_evidence_json=_json.dumps(re.to_dict(), indent=2),
        data_manifest_json=_json.dumps(dm.to_dict(), indent=2),
        task_spec_json=_json.dumps(ts.to_dict(), indent=2),
        evaluation_contract_json=_json.dumps(ec.to_dict(), indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    # Resolve identity fields
    task = data.get("task") or pi.task
    method = data.get("method") or pi.method
    case = data.get("case") or pi.case

    risks = data.get("risks", [])
    if not isinstance(risks, list):
        risks = []

    overall_confidence = data.get("overall_confidence", "low")
    if not isinstance(overall_confidence, str) or not overall_confidence:
        overall_confidence = "low"

    blocker_risk_ids = data.get("blocker_risk_ids", [])
    if not isinstance(blocker_risk_ids, list):
        blocker_risk_ids = []

    ra = RiskAudit(
        task=task,
        method=method,
        case=case,
        risks=risks,
        overall_confidence=overall_confidence,
        blocker_risk_ids=blocker_risk_ids,
    )

    # ALWAYS write risk_audit.json, even if risks list is empty
    workspace.write_artifact("risk_audit", ra)
    # No blocker from s08
