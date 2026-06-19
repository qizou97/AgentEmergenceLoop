"""
sobench/steps/s11_audit_result_validity.py

s11: Audit whether the execution outputs are structurally valid and plausible.

SKIP (return without writing) when workspace.blocked.

Otherwise:
  - Read raw_observations.json, task_spec.json, evaluation_contract.json
  - Call llm_json: structural validity + plausibility checks
  - Write result_validity_audit.json
"""

from __future__ import annotations

import json as _json

from sobench.workspace import Workspace
from sobench.models import (
    EvaluationContract,
    RawObservations,
    ResultValidityAudit,
    TaskSpec,
)
from sobench.steps._common import llm_json

_STEP_NAME = "s11_audit_result_validity"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark analysis. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
You are auditing whether a spatial-omics benchmark execution produced valid results.

Perform structural validity checks and plausibility assessment.

Task: {task}
Method: {method}
Case: {case}

Raw observations:
{raw_observations_json}

Task specification:
{task_spec_json}

Evaluation contract:
{evaluation_contract_json}

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "result_valid": <true or false>,
  "checks": [
    {{"check": "<description of what was checked>", "passed": <true or false>}},
    ...
  ],
  "validity_reasoning": "<brief explanation of the overall validity decision>",
  "warnings": ["<warning>"]
}}

Rules:
- result_valid: true only if outputs are structurally complete and plausibly correct.
  Set false if: outputs_found is empty, output_shape rows is 0 or inconsistent with
  expected task output, metric value is out of plausible range, or anomalies are severe.
- checks: list every check performed, with passed:true or passed:false.
  Include at minimum: (1) outputs were found, (2) output shape is non-empty,
  (3) no severe anomalies observed.
- validity_reasoning: 1-3 sentences explaining the decision.
- warnings: non-blocking issues (e.g. assumed k, missing ground truth).
- Do NOT invent data. Base checks only on the provided artifacts.
"""


def run(workspace: Workspace) -> None:
    """
    s11: Audit result validity.

    Skip silently when workspace.blocked.
    Read prior artifacts, call LLM, write result_validity_audit.json.
    """
    if workspace.blocked:
        return

    ro = workspace.read_artifact("raw_observations", RawObservations)
    ts = workspace.read_artifact("task_spec", TaskSpec)
    ec = workspace.read_artifact("evaluation_contract", EvaluationContract)

    prompt = _PROMPT_TEMPLATE.format(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        raw_observations_json=_json.dumps(ro.to_dict(), indent=2),
        task_spec_json=_json.dumps(ts.to_dict(), indent=2),
        evaluation_contract_json=_json.dumps(ec.to_dict(), indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    # Resolve identity fields
    task = data.get("task") or workspace.task
    method = data.get("method") or workspace.method
    case = data.get("case") or workspace.case

    rva = ResultValidityAudit(
        task=task,
        method=method,
        case=case,
        result_valid=bool(data.get("result_valid", False)),
        checks=data.get("checks", []),
        validity_reasoning=data.get("validity_reasoning", ""),
        warnings=data.get("warnings", []),
    )
    workspace.write_artifact("result_validity_audit", rva)
