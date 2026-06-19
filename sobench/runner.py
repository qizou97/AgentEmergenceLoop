"""
sobench/runner.py — ordered step execution with blocked-cycle skip logic.

Single responsibility: iterate STEPS in s01→s14 order, skip
SKIP_WHEN_BLOCKED steps when workspace.blocked is True, and return
the ordered list of executed step names for observability.
"""

from __future__ import annotations

from sobench.workspace import Workspace
from sobench.steps import (
    s01_ensure_workspace,
    s02_parse_intent,
    s03_extract_paper_evidence,
    s04_inspect_repo_evidence,
    s05_build_data_manifest,
    s06_draft_task_spec,
    s07_draft_evaluation_contract,
    s08_draft_risk_audit,
    s09_execute_or_block,
    s10_record_raw_observations,
    s11_audit_result_validity,
    s12_write_interpretation,
    s13_write_experience_record,
    s14_structural_check,
)

# Steps that are skipped when workspace.blocked is True.
# Exactly these three; s01–s09 and s13–s14 always run.
SKIP_WHEN_BLOCKED = {
    "s10_record_raw_observations",
    "s11_audit_result_validity",
    "s12_write_interpretation",
}

# Ordered list of (name, run_callable) pairs.  Must be s01→s14.
STEPS: list[tuple[str, object]] = [
    ("s01_ensure_workspace",      s01_ensure_workspace.run),
    ("s02_parse_intent",          s02_parse_intent.run),
    ("s03_extract_paper_evidence", s03_extract_paper_evidence.run),
    ("s04_inspect_repo_evidence", s04_inspect_repo_evidence.run),
    ("s05_build_data_manifest",   s05_build_data_manifest.run),
    ("s06_draft_task_spec",       s06_draft_task_spec.run),
    ("s07_draft_evaluation_contract", s07_draft_evaluation_contract.run),
    ("s08_draft_risk_audit",      s08_draft_risk_audit.run),
    ("s09_execute_or_block",      s09_execute_or_block.run),
    ("s10_record_raw_observations", s10_record_raw_observations.run),
    ("s11_audit_result_validity", s11_audit_result_validity.run),
    ("s12_write_interpretation",  s12_write_interpretation.run),
    ("s13_write_experience_record", s13_write_experience_record.run),
    ("s14_structural_check",      s14_structural_check.run),
]


def run(workspace: Workspace) -> list[str]:
    """
    Execute all 14 steps in order, skipping SKIP_WHEN_BLOCKED steps when
    workspace.blocked is True.

    workspace.blocked is re-evaluated each iteration from disk so that once
    s09 writes blocked:true the subsequent skip checks see it immediately.

    Returns the ordered list of executed step names (for observability and
    testing without mocking).
    """
    executed: list[str] = []
    for name, step_run in STEPS:
        if workspace.blocked and name in SKIP_WHEN_BLOCKED:
            continue
        step_run(workspace)
        executed.append(name)
    return executed
