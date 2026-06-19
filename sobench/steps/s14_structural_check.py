"""
sobench/steps/s14_structural_check.py

s14: Structural completeness check — always runs, no LLM.

Reads blocker.json to decide which post-execution artifacts are excused,
then checks presence and schema validity of all artifacts, and writes
structural_check.json.

Required-always artifacts:
  benchmark_intent.md (presence only), paper_evidence, repo_evidence,
  data_manifest, task_spec, evaluation_contract, risk_audit, blocker,
  execution_log, experience_record, structural_check (being written now).

Excused-when-blocked artifacts (raw_observations, result_validity_audit,
  interpretation): when blocker.blocked is True these are excused (not counted
  as missing_unacknowledged); when NOT blocked they ARE expected.

passed = (len(missing_unacknowledged) == 0)
"""

from __future__ import annotations

from pathlib import Path

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
    StructuralCheck,
    TaskSpec,
)


def _check_json_artifact(workspace: Workspace, name: str, cls) -> dict:
    """
    Return a checks entry for a JSON artifact.

    Returns {"artifact": "<name>.json", "present": bool, "valid": bool?}
    valid is only included when present is True.
    """
    path = workspace.artifact_path(name)
    if not path.exists():
        return {"artifact": f"{name}.json", "present": False}
    try:
        obj = workspace.read_artifact(name, cls)
        obj.validate()
        return {"artifact": f"{name}.json", "present": True, "valid": True}
    except Exception:
        return {"artifact": f"{name}.json", "present": True, "valid": False}


def _check_markdown_artifact(workspace: Workspace, name: str) -> dict:
    """Return a checks entry for a markdown file (presence only)."""
    path = workspace.dir / name
    return {"artifact": name, "present": path.exists()}


def run(workspace: Workspace) -> None:
    """
    s14: Always runs. Checks structural completeness and writes
    structural_check.json.
    """
    # Read blocker to decide which artifacts are excused
    blocker = workspace.read_blocker()
    is_blocked = (blocker is not None and blocker.blocked)

    checks = []
    missing_unacknowledged = []

    # --- benchmark_intent.md (presence only) ---
    checks.append(_check_markdown_artifact(workspace, "benchmark_intent.md"))
    if not checks[-1]["present"]:
        missing_unacknowledged.append("benchmark_intent.md")

    # --- Required-always JSON artifacts ---
    required_always = [
        ("paper_evidence", PaperEvidence),
        ("repo_evidence", RepoEvidence),
        ("data_manifest", DataManifest),
        ("task_spec", TaskSpec),
        ("evaluation_contract", EvaluationContract),
        ("risk_audit", RiskAudit),
        ("blocker", Blocker),
        ("execution_log", ExecutionLog),
    ]
    for name, cls in required_always:
        entry = _check_json_artifact(workspace, name, cls)
        checks.append(entry)
        if not entry["present"] or entry.get("valid") is False:
            missing_unacknowledged.append(f"{name}.json")

    # --- Excused-when-blocked artifacts ---
    post_exec = [
        ("raw_observations", RawObservations),
        ("result_validity_audit", ResultValidityAudit),
        ("interpretation", Interpretation),
    ]
    for name, cls in post_exec:
        path = workspace.artifact_path(name)
        if is_blocked:
            # Excused: present:false expected_given_blocker:false
            entry = {"artifact": f"{name}.json", "present": path.exists(), "expected_given_blocker": False}
            checks.append(entry)
            # NOT added to missing_unacknowledged — excused
        else:
            entry = _check_json_artifact(workspace, name, cls)
            checks.append(entry)
            if not entry["present"] or entry.get("valid") is False:
                missing_unacknowledged.append(f"{name}.json")

    # --- experience_record ---
    entry = _check_json_artifact(workspace, "experience_record", ExperienceRecord)
    checks.append(entry)
    if not entry["present"] or entry.get("valid") is False:
        missing_unacknowledged.append("experience_record.json")

    # --- structural_check.json itself (being written now — mark present:true) ---
    checks.append({"artifact": "structural_check.json", "present": True})

    # --- Derived fields ---
    passed = len(missing_unacknowledged) == 0
    structurally_complete = passed  # same logic per spec

    completed_with_blocker = is_blocked

    # execution_attempted: True when execution_log.status != "not_attempted"
    execution_attempted = False
    elog_path = workspace.artifact_path("execution_log")
    if elog_path.exists():
        try:
            elog = workspace.read_artifact("execution_log", ExecutionLog)
            execution_attempted = (elog.status != "not_attempted")
        except Exception:
            pass

    # benchmark_result_claimed: from interpretation.benchmark_result_claimed if present
    benchmark_result_claimed = False
    interp_path = workspace.artifact_path("interpretation")
    if interp_path.exists():
        try:
            interp = workspace.read_artifact("interpretation", Interpretation)
            benchmark_result_claimed = bool(interp.benchmark_result_claimed)
        except Exception:
            pass

    # --- Warnings ---
    warnings = []
    if is_blocked:
        warnings.append("execution not attempted — blocked on missing data")

    sc = StructuralCheck(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        passed=passed,
        structurally_complete=structurally_complete,
        completed_with_blocker=completed_with_blocker,
        execution_attempted=execution_attempted,
        benchmark_result_claimed=benchmark_result_claimed,
        checks=checks,
        missing_unacknowledged=missing_unacknowledged,
        warnings=warnings,
    )

    workspace.write_artifact("structural_check", sc)
