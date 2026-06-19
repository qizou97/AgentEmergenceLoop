"""
Tests for s14_structural_check.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.
All tests are FULLY DETERMINISTIC — no LLM, no skip allowed.

Test 1 — passed:true for blocked-but-complete cycle:
  Workspace with ALL required-always artifacts present + blocker.json blocked:true
  + execution_log not_attempted + experience_record present.
  Post-exec artifacts (raw_observations, result_validity_audit, interpretation)
  are ABSENT (excused by blocker).
  Expected outcome:
    - passed: True
    - structurally_complete: True
    - completed_with_blocker: True
    - execution_attempted: False
    - benchmark_result_claimed: False
    - missing_unacknowledged: []
    - post-exec checks show expected_given_blocker: False

Test 2 — passed:false for missing required artifact without blocker:
  Workspace NOT blocked (blocker.json blocked:false) but task_spec absent.
  Expected outcome:
    - passed: False
    - missing_unacknowledged: contains "task_spec.json"

Test 3 — passed:false for missing post-exec artifact without blocker:
  Workspace NOT blocked, all required-always artifacts present, but
  raw_observations absent (unexcused when not blocked).
  Expected outcome:
    - passed: False
    - missing_unacknowledged: contains "raw_observations.json"

Test 4 — derived fields: execution_attempted and benchmark_result_claimed:
  NOT-blocked workspace, execution_log status="success", interpretation present
  with benchmark_result_claimed:true.
  Expected outcome:
    - execution_attempted: True
    - benchmark_result_claimed: True
    - completed_with_blocker: False

Provenance: data/spatial_domain_identification_task/ (STAGATE repo + papers)
"""

from __future__ import annotations

from pathlib import Path

import pytest

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

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

ABSENT_H5AD = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"


# ---------------------------------------------------------------------------
# Real-task-derived artifact factories
# ---------------------------------------------------------------------------

def _make_paper_evidence() -> PaperEvidence:
    return PaperEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        source="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        evaluation_contexts=[
            {
                "id": "ctx-001",
                "task": "spatial_domain_identification",
                "cases": ["DLPFC_151673"],
                "metrics": [{"name": "ARI", "confidence": "high", "quote": "we report ARI"}],
                "downstream_tasks": [],
                "notes": "primary evaluation",
            }
        ],
        coordinate_evidence="spatial coordinates in obsm['spatial']",
        coordinate_open_questions=[],
        ambiguities=["k selection not described"],
        missing=[],
    )


def _make_repo_evidence() -> RepoEvidence:
    return RepoEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        entry_points=["run_STAGATE.py"],
        dependencies={"python": "3.7", "tensorflow": "1.15.0"},
        hardcoded_paths=["./data/DLPFC/"],
        metric_implementations=["sklearn.metrics.adjusted_rand_score"],
        deviations_from_paper=["k=7 default"],
        coordinate_evidence="obsm['spatial'] loaded from .h5ad",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=[],
    )


def _make_data_manifest() -> DataManifest:
    return DataManifest(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        required=[
            {
                "role": "expression_matrix_with_coords",
                "format": "AnnData .h5ad",
                "expected_path": ABSENT_H5AD,
                "available": False,
                "notes": "spatialLIBD DLPFC slice 151673 — not downloaded",
            }
        ],
        coordinate_evidence="repo loads obsm['spatial'] from .h5ad",
        coordinate_assumptions="none",
        coordinate_open_questions=[],
        coordinate_checks=[],
        open_questions=[],
    )


def _make_task_spec() -> TaskSpec:
    return TaskSpec(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        source_context="ctx-001",
        input_description="AnnData with expression matrix and spatial coordinates",
        expected_output="cluster label per spot",
        primary_metric={"name": "ARI", "resolved": True},
        assumptions=["raw counts"],
        unresolved=["k"],
    )


def _make_evaluation_contract() -> EvaluationContract:
    return EvaluationContract(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        metric={"name": "ARI", "resolved": True},
        data_requirements_resolved=False,
        data_blockers=["DLPFC .h5ad absent"],
        open_questions=[],
    )


def _make_risk_audit() -> RiskAudit:
    return RiskAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        risks=[
            {
                "id": "risk-001",
                "category": "data",
                "description": "DLPFC .h5ad absent",
                "severity": "high",
                "evidence": "data_manifest.required[0].available=false",
                "mitigation": "Download from spatialLIBD",
            }
        ],
        overall_confidence="low",
        blocker_risk_ids=["risk-001"],
    )


def _make_blocker_blocked() -> Blocker:
    return Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail=(
            f"{ABSENT_H5AD} does not exist; DLPFC 151673 .h5ad absent"
        ),
        evidence="data_manifest.required[0].available=false",
        resolution="download DLPFC 151673 from spatialLIBD",
        human_action_required=True,
    )


def _make_blocker_not_blocked() -> Blocker:
    return Blocker(
        blocked=False,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    )


def _make_execution_log_not_attempted() -> ExecutionLog:
    return ExecutionLog(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        status="not_attempted",
        command="",
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment={"python": "3.13", "platform": "linux"},
        output_files=[],
    )


def _make_execution_log_success() -> ExecutionLog:
    return ExecutionLog(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        status="success",
        command="python run_STAGATE.py --slice 151673",
        stdout_excerpt="Training complete. 7 clusters assigned.",
        stderr_excerpt="",
        duration_seconds=42.0,
        environment={"python": "3.13", "platform": "linux"},
        output_files=["results/151673_labels.csv"],
    )


def _make_experience_record() -> ExperienceRecord:
    """
    Real-task-derived experience record for the blocked cycle.
    Provenance: matches blocked-cycle spec example (7.13).
    """
    return ExperienceRecord(
        id="exp-001",
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        tags=["data_missing", "spatialLIBD", "DLPFC"],
        finding="DLPFC 151673 .h5ad not present locally; spatialLIBD is the expected source",
        evidence=["data_manifest.required[0]", "blocker.detail"],
        confidence="high",
        failure_conditions=[],
        status="hypothesis",
        created="2026-06-19",
    )


def _make_raw_observations() -> RawObservations:
    return RawObservations(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        outputs_found=["results/151673_labels.csv"],
        output_shape={"rows": 10, "columns": 2},
        metric_raw={"name": "ARI", "value": None},
        stdout_summary="7 clusters assigned to 10 spots",
        stderr_summary="",
        anomalies_observed=[],
    )


def _make_result_validity_audit() -> ResultValidityAudit:
    return ResultValidityAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        result_valid=True,
        checks=[{"check": "output rows match spots", "passed": True}],
        validity_reasoning="outputs structurally consistent",
        warnings=[],
    )


def _make_interpretation_claimed() -> Interpretation:
    return Interpretation(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        primary_metric_value=None,
        can_conclude=["ARI computed"],
        cannot_conclude=[],
        benchmark_result_claimed=True,
        open_questions=[],
        interpretation="ARI consistent with paper; normalization ambiguous",
    )


def _write_benchmark_intent(ws: Workspace) -> None:
    """Write benchmark_intent.md (markdown, not JSON — presence check only)."""
    md_path = ws.dir / "benchmark_intent.md"
    md_path.write_text(
        "# Benchmark Intent\n"
        f"task: {REAL_TASK}\n"
        f"method: {REAL_METHOD}\n"
        f"case: {REAL_CASE}\n"
        "paper: data/spatial_domain_identification_task/papers/STAGATE.pdf\n"
        "repo: data/spatial_domain_identification_task/STAGATE/\n"
        "data: data/spatial_domain_identification_task/DLPFC/\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Test 1 — passed:true for blocked-but-complete cycle (NO skip — deterministic)
# ---------------------------------------------------------------------------

def test_s14_passed_true_blocked_but_complete(tmp_path):
    """
    s14 passes when all required-always artifacts are present and blocked:true
    excuses the three post-execution artifacts.

    Fixture: ALL required-always artifacts present + blocker blocked:true +
    execution_log not_attempted + experience_record present.
    Post-exec artifacts ABSENT (excused by blocker).
    """
    from sobench.steps import s14_structural_check

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    _write_benchmark_intent(ws)
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit())
    ws.write_artifact("blocker", _make_blocker_blocked())
    ws.write_artifact("execution_log", _make_execution_log_not_attempted())
    ws.write_artifact("experience_record", _make_experience_record())
    # NO raw_observations, result_validity_audit, interpretation (excused by blocker)

    s14_structural_check.run(ws)

    sc_path = ws.artifact_path("structural_check")
    assert sc_path.exists(), "s14 must write structural_check.json"

    sc = ws.read_artifact("structural_check", StructuralCheck)

    assert sc.passed is True, f"passed must be True for complete blocked cycle; got {sc.passed}"
    assert sc.structurally_complete is True
    assert sc.completed_with_blocker is True, "completed_with_blocker must be True"
    assert sc.execution_attempted is False, "execution_attempted must be False (not_attempted)"
    assert sc.benchmark_result_claimed is False, "benchmark_result_claimed must be False"
    assert sc.missing_unacknowledged == [], (
        f"missing_unacknowledged must be [] for complete blocked cycle; got {sc.missing_unacknowledged}"
    )

    # Post-exec checks should show expected_given_blocker: False
    checks_by_artifact = {c["artifact"]: c for c in sc.checks}
    for artifact in ("raw_observations.json", "result_validity_audit.json", "interpretation.json"):
        assert artifact in checks_by_artifact, f"checks must include {artifact}"
        entry = checks_by_artifact[artifact]
        assert entry["present"] is False
        assert entry.get("expected_given_blocker") is False, (
            f"{artifact} must have expected_given_blocker: False; got {entry}"
        )

    # Identity
    assert sc.task == REAL_TASK
    assert sc.method == REAL_METHOD
    assert sc.case == REAL_CASE


# ---------------------------------------------------------------------------
# Test 2 — passed:false for missing required artifact without blocker
# ---------------------------------------------------------------------------

def test_s14_passed_false_missing_required_without_blocker(tmp_path):
    """
    s14 fails when a required artifact (task_spec) is absent and blocker is NOT set.

    Fixture: NOT-blocked workspace missing task_spec.json.
    """
    from sobench.steps import s14_structural_check

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    _write_benchmark_intent(ws)
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    # task_spec ABSENT (required, not excused)
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit())
    ws.write_artifact("blocker", _make_blocker_not_blocked())
    ws.write_artifact("execution_log", _make_execution_log_not_attempted())
    ws.write_artifact("experience_record", _make_experience_record())

    s14_structural_check.run(ws)

    sc = ws.read_artifact("structural_check", StructuralCheck)

    assert sc.passed is False, "passed must be False when a required artifact is missing without a blocker"
    assert "task_spec.json" in sc.missing_unacknowledged, (
        f"task_spec.json must be in missing_unacknowledged; got {sc.missing_unacknowledged}"
    )


# ---------------------------------------------------------------------------
# Test 3 — passed:false for missing post-exec artifact without blocker
# ---------------------------------------------------------------------------

def test_s14_passed_false_missing_post_exec_without_blocker(tmp_path):
    """
    s14 fails when raw_observations is absent and blocker is NOT set.
    Post-exec artifacts are only excused when blocked:true.

    Fixture: NOT-blocked workspace, all required-always artifacts present,
    raw_observations ABSENT (unexcused).
    """
    from sobench.steps import s14_structural_check

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    _write_benchmark_intent(ws)
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit())
    ws.write_artifact("blocker", _make_blocker_not_blocked())
    ws.write_artifact("execution_log", _make_execution_log_not_attempted())
    ws.write_artifact("experience_record", _make_experience_record())
    # raw_observations ABSENT (no blocker to excuse it)
    # result_validity_audit + interpretation also absent

    s14_structural_check.run(ws)

    sc = ws.read_artifact("structural_check", StructuralCheck)

    assert sc.passed is False, (
        "passed must be False when raw_observations is absent without a blocker"
    )
    assert "raw_observations.json" in sc.missing_unacknowledged, (
        f"raw_observations.json must be in missing_unacknowledged; got {sc.missing_unacknowledged}"
    )


# ---------------------------------------------------------------------------
# Test 4 — derived fields: execution_attempted and benchmark_result_claimed
# ---------------------------------------------------------------------------

def test_s14_derived_fields_execution_and_benchmark(tmp_path):
    """
    s14 correctly derives execution_attempted from execution_log.status and
    benchmark_result_claimed from interpretation.benchmark_result_claimed.

    Fixture: NOT-blocked workspace, execution_log status="success",
    interpretation with benchmark_result_claimed:true. All required artifacts present.
    """
    from sobench.steps import s14_structural_check

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    _write_benchmark_intent(ws)
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit())
    ws.write_artifact("blocker", _make_blocker_not_blocked())
    ws.write_artifact("execution_log", _make_execution_log_success())
    ws.write_artifact("raw_observations", _make_raw_observations())
    ws.write_artifact("result_validity_audit", _make_result_validity_audit())
    ws.write_artifact("interpretation", _make_interpretation_claimed())
    ws.write_artifact("experience_record", _make_experience_record())

    s14_structural_check.run(ws)

    sc = ws.read_artifact("structural_check", StructuralCheck)

    assert sc.execution_attempted is True, (
        "execution_attempted must be True when execution_log.status == 'success'"
    )
    assert sc.benchmark_result_claimed is True, (
        "benchmark_result_claimed must be True when interpretation.benchmark_result_claimed is True"
    )
    assert sc.completed_with_blocker is False, (
        "completed_with_blocker must be False when blocker.blocked is False"
    )
    # All artifacts present → passed should be True (no missing_unacknowledged)
    assert sc.missing_unacknowledged == [], f"unexpected missing: {sc.missing_unacknowledged}"
    assert sc.passed is True
