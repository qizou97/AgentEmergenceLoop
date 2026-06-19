"""
sobench/steps/s12_write_interpretation.py

s12: Write interpretation of benchmark execution results.

SKIP (return without writing) when workspace.blocked AND execution_log.status ==
"not_attempted" (pre-execution blocker; execution was never attempted).
Since blocked ⟺ not_attempted (s09 equivalence), this simplifies to:
  SKIP when workspace.blocked.

RUN when execution was attempted (execution_log.status != "not_attempted"),
EVEN IF result_valid is false.

If result_valid: false → write MINIMAL interpretation:
  benchmark_result_claimed: false, primary_metric_value: null, can_conclude: [],
  cannot_conclude noting validity failure.

If result_valid: true → write FULL interpretation:
  benchmark_result_claimed: true, with LLM-derived analysis.

LLM prompt PROHIBITS promoting unresolved metrics or unapproved conclusions
(spec section 8 s12).
"""

from __future__ import annotations

import json as _json

from sobench.workspace import Workspace
from sobench.models import (
    ExecutionLog,
    Interpretation,
    PaperEvidence,
    RawObservations,
    ResultValidityAudit,
    TaskSpec,
)
from sobench.steps._common import llm_json

_STEP_NAME = "s12_write_interpretation"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark analysis. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_FULL = """\
You are writing an interpretation of a spatial-omics benchmark result.

Task: {task}
Method: {method}
Case: {case}

Result validity audit:
{rva_json}

Raw observations:
{ro_json}

Task specification:
{ts_json}

Paper evidence:
{pe_json}

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "primary_metric_value": <number or null>,
  "can_conclude": ["<evidence-backed conclusion>"],
  "cannot_conclude": ["<limitation or uncertainty>"],
  "benchmark_result_claimed": true,
  "open_questions": ["<open question for future work>"],
  "interpretation": "<1-3 sentence narrative summary>"
}}

STRICT RULES — violations invalidate the interpretation:
1. Do NOT promote unresolved metrics. Only include metric values that are
   explicitly present in raw_observations.metric_raw or result_validity_audit.
2. Do NOT claim conclusions that are not directly supported by the artifacts.
   If evidence is absent or ambiguous, place the item in cannot_conclude.
3. can_conclude items must each cite a specific artifact value.
4. cannot_conclude must include any assumption-dependent findings (e.g. assumed k).
5. benchmark_result_claimed MUST be true in this response.
6. primary_metric_value: use the value from raw_observations.metric_raw if
   it is a number; otherwise null.
"""

_PROMPT_MINIMAL = """\
You are writing a minimal interpretation for a spatial-omics benchmark execution
that ran but failed the result validity audit.

Task: {task}
Method: {method}
Case: {case}

Result validity audit (result_valid: false):
{rva_json}

Raw observations:
{ro_json}

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "primary_metric_value": null,
  "can_conclude": [],
  "cannot_conclude": ["<reason validity failed — no benchmark result can be claimed>"],
  "benchmark_result_claimed": false,
  "open_questions": [],
  "interpretation": "<1-2 sentence note that execution ran but outputs did not pass validity audit>"
}}

STRICT RULES:
1. benchmark_result_claimed MUST be false.
2. primary_metric_value MUST be null.
3. can_conclude MUST be an empty list [].
4. cannot_conclude must reference the validity failure reason from the audit.
5. Do NOT promote any metric values or conclusions from the failed run.
"""


def run(workspace: Workspace) -> None:
    """
    s12: Write interpretation.

    Skip silently when workspace.blocked (which is equivalent to
    execution_log.status == "not_attempted" per spec design).
    Run otherwise, even when result_valid is false.
    """
    if workspace.blocked:
        return

    elog = workspace.read_artifact("execution_log", ExecutionLog)

    # Defensive guard: if somehow execution was never attempted, skip.
    if elog.status == "not_attempted":
        return

    rva = workspace.read_artifact("result_validity_audit", ResultValidityAudit)
    ro = workspace.read_artifact("raw_observations", RawObservations)
    ts = workspace.read_artifact("task_spec", TaskSpec)
    pe = workspace.read_artifact("paper_evidence", PaperEvidence)

    if not rva.result_valid:
        # Minimal interpretation path
        prompt = _PROMPT_MINIMAL.format(
            task=workspace.task,
            method=workspace.method,
            case=workspace.case,
            rva_json=_json.dumps(rva.to_dict(), indent=2),
            ro_json=_json.dumps(ro.to_dict(), indent=2),
        )
        data = llm_json(prompt, system=_SYSTEM)

        interp = Interpretation(
            task=data.get("task") or workspace.task,
            method=data.get("method") or workspace.method,
            case=data.get("case") or workspace.case,
            primary_metric_value=None,
            can_conclude=[],
            cannot_conclude=data.get("cannot_conclude", ["result validity check failed; no benchmark result can be claimed"]),
            benchmark_result_claimed=False,
            open_questions=data.get("open_questions", []),
            interpretation=data.get("interpretation", "execution ran but outputs did not pass validity audit"),
        )
    else:
        # Full interpretation path
        prompt = _PROMPT_FULL.format(
            task=workspace.task,
            method=workspace.method,
            case=workspace.case,
            rva_json=_json.dumps(rva.to_dict(), indent=2),
            ro_json=_json.dumps(ro.to_dict(), indent=2),
            ts_json=_json.dumps(ts.to_dict(), indent=2),
            pe_json=_json.dumps(pe.to_dict(), indent=2),
        )
        data = llm_json(prompt, system=_SYSTEM)

        # Extract primary_metric_value — enforce numeric or None
        pmv = data.get("primary_metric_value")
        if pmv is not None:
            try:
                pmv = float(pmv)
            except (TypeError, ValueError):
                pmv = None

        interp = Interpretation(
            task=data.get("task") or workspace.task,
            method=data.get("method") or workspace.method,
            case=data.get("case") or workspace.case,
            primary_metric_value=pmv,
            can_conclude=data.get("can_conclude", []),
            cannot_conclude=data.get("cannot_conclude", []),
            benchmark_result_claimed=True,
            open_questions=data.get("open_questions", []),
            interpretation=data.get("interpretation", ""),
        )

    workspace.write_artifact("interpretation", interp)
