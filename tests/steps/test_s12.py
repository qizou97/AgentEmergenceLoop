"""
Tests for s12_write_interpretation.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.
Follows the same workspace-building style as test_s09.py, test_s10.py.

Test 1 (primary, deterministic — MUST RUN, no skip):
  Blocked path (blocked:true AND execution_log.status="not_attempted").
  Assert s12 writes NO interpretation.json.
  This is deterministic — no LLM, no skip allowed.

Test 2 (execution attempted + result_valid:false — LLM; skip if no API key):
  NOT-blocked workspace, execution_log.status="failed", result_validity_audit
  with result_valid:false. Assert s12 writes a MINIMAL interpretation:
    - benchmark_result_claimed: false
    - primary_metric_value: null
    - can_conclude: []
    - cannot_conclude: non-empty (notes validity failure)

Test 3 (execution attempted + result_valid:true — LLM; skip if no API key):
  NOT-blocked workspace, execution_log.status="success", result_validity_audit
  with result_valid:true. Assert s12 writes FULL interpretation:
    - benchmark_result_claimed: true

Provenance: data/spatial_domain_identification_task/ (STAGATE repo + papers)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sobench.workspace import Workspace
from sobench.models import (
    Blocker,
    EvaluationContract,
    ExecutionLog,
    Interpretation,
    PaperEvidence,
    RawObservations,
    ResultValidityAudit,
    TaskSpec,
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

ABSENT_H5AD = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"


# ---------------------------------------------------------------------------
# Shared real-task-derived artifact factories
# ---------------------------------------------------------------------------

def _make_task_spec() -> TaskSpec:
    return TaskSpec(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        source_context="ctx-001",
        input_description="AnnData with expression matrix and spatial coordinates for DLPFC slice 151673",
        expected_output="cluster label per spot",
        primary_metric={"name": "ARI", "resolved": True},
        assumptions=["raw counts as input based on repo evidence"],
        unresolved=["cluster count k not stated in paper"],
    )


def _make_evaluation_contract() -> EvaluationContract:
    return EvaluationContract(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        metric={
            "name": "ARI",
            "resolved": True,
            "implementation": "sklearn.metrics.adjusted_rand_score",
            "provenance": "stated in paper ctx-001",
            "known_risks": ["sensitive to k"],
        },
        data_requirements_resolved=False,
        data_blockers=[],
        open_questions=["ground truth column name"],
    )


def _make_raw_observations() -> RawObservations:
    """
    Real-task-derived raw observations for DLPFC 151673 / STAGATE (10-spot fixture).
    Provenance: see test_s10.py fixture documentation.
    """
    return RawObservations(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        outputs_found=["results/151673_labels.csv"],
        output_shape={"rows": 10, "columns": 2},
        metric_raw={"name": "ARI", "value": None},
        stdout_summary=(
            "Epoch 1/200 loss=1.234. Epoch 200/200 loss=0.021. "
            "Training complete. 7 clusters assigned to 10 spots."
        ),
        stderr_summary="",
        anomalies_observed=[],
    )


def _make_paper_evidence() -> PaperEvidence:
    """
    Real-task-derived paper evidence for STAGATE on DLPFC 151673.
    Provenance: STAGATE.pdf section 4.1 describes DLPFC evaluation with ARI.
    """
    return PaperEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        source="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        evaluation_contexts=[
            {
                "id": "ctx-001",
                "task": "spatial_domain_identification",
                "cases": ["DLPFC_151673", "DLPFC_151507"],
                "metrics": [
                    {
                        "name": "ARI",
                        "confidence": "high",
                        "quote": "we report ARI across all slices",
                    }
                ],
                "downstream_tasks": [],
                "notes": "primary evaluation; k varies by slice (7 used for most slices)",
            }
        ],
        coordinate_evidence=(
            "paper references spatial coordinates but does not specify coordinate space"
        ),
        coordinate_open_questions=["which coordinate space is used for spatial graph construction?"],
        ambiguities=["k selection procedure not described"],
        missing=["no train/test split described"],
    )


def _make_result_validity_audit_invalid() -> ResultValidityAudit:
    """
    Real-task-derived validity audit with result_valid:false.
    Scenario: execution ran but output had too few rows (mock truncation).
    """
    return ResultValidityAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        result_valid=False,
        checks=[
            {
                "check": "output row count matches input spot count",
                "passed": False,
            },
            {
                "check": "no NaN or missing labels",
                "passed": True,
            },
        ],
        validity_reasoning=(
            "output has 10 rows but expected 3639 spots for DLPFC 151673; "
            "structural validity failed"
        ),
        warnings=["k=7 was assumed, not confirmed from paper"],
    )


def _make_result_validity_audit_valid() -> ResultValidityAudit:
    """
    Real-task-derived validity audit with result_valid:true.
    Scenario: execution ran successfully and output passes all checks.
    """
    return ResultValidityAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        result_valid=True,
        checks=[
            {
                "check": "output row count matches input spot count",
                "passed": True,
            },
            {
                "check": "cluster count matches assumed k=7",
                "passed": True,
            },
            {
                "check": "no NaN or missing labels",
                "passed": True,
            },
        ],
        validity_reasoning=(
            "outputs structurally consistent with expected task output for DLPFC 151673"
        ),
        warnings=["k=7 was assumed, not confirmed from paper"],
    )


def _write_blocked_artifacts(ws: Workspace) -> None:
    """Write blocker.json (blocked:true) + execution_log.json (not_attempted)."""
    blocker = Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail=(
            f"{ABSENT_H5AD} does not exist at expected path; "
            "DLPFC 151673 .h5ad absent from data directory"
        ),
        evidence="data_manifest.required[0].available=false",
        resolution="download DLPFC 151673 from spatialLIBD and update data_manifest.json",
        human_action_required=True,
    )
    ws.write_artifact("blocker", blocker)
    elog = ExecutionLog(
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
    ws.write_artifact("execution_log", elog)


def _build_blocked_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    _write_blocked_artifacts(ws)
    return ws


def _build_not_blocked_workspace(
    tmp_path: Path,
    exec_status: str,
    rva: ResultValidityAudit,
) -> Workspace:
    """
    Build a NOT-blocked workspace where execution was attempted.

    exec_status: "success" or "failed"
    rva: ResultValidityAudit to write
    All artifacts are real-task-derived.
    """
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    blocker = Blocker(
        blocked=False,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    )
    ws.write_artifact("blocker", blocker)

    elog = ExecutionLog(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        status=exec_status,
        command="python run_STAGATE.py --slice 151673",
        stdout_excerpt="Training complete. 7 clusters assigned to 10 spots.",
        stderr_excerpt="",
        duration_seconds=42.0,
        environment={"python": "3.13", "platform": "linux"},
        output_files=["results/151673_labels.csv"],
    )
    ws.write_artifact("execution_log", elog)

    ws.write_artifact("raw_observations", _make_raw_observations())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("result_validity_audit", rva)

    return ws


# ---------------------------------------------------------------------------
# Test 1 — Blocked path (PRIMARY, deterministic, NO skip allowed)
# ---------------------------------------------------------------------------

def test_s12_no_artifact_when_blocked_not_attempted(tmp_path):
    """
    s12 writes NO interpretation.json when workspace.blocked is True and
    execution_log.status == "not_attempted" (pre-execution blocker).

    Real-task ground truth: ABSENT_H5AD does not exist on disk.
    This test is deterministic — no LLM calls, no skip allowed.

    Asserts: interpretation.json does NOT exist after s12.run().
    """
    assert not Path(ABSENT_H5AD).exists(), (
        f"Assumption violated: {ABSENT_H5AD!r} now exists on disk. "
        "Update the test — it was designed for genuinely-absent DLPFC data."
    )

    from sobench.steps import s12_write_interpretation

    ws = _build_blocked_workspace(tmp_path)
    assert ws.blocked is True, "Precondition: workspace must be blocked"

    s12_write_interpretation.run(ws)

    interp_path = ws.artifact_path("interpretation")
    assert not interp_path.exists(), (
        "s12 must NOT write interpretation.json when blocked AND status=not_attempted; "
        f"but file exists at {interp_path}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Execution attempted + result_valid:false (LLM; skip if no API key)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)
def test_s12_minimal_interpretation_when_validity_failed(tmp_path):
    """
    s12 writes a MINIMAL interpretation when result_valid:false but execution
    was attempted (execution_log.status != "not_attempted").

    Fixture: NOT-blocked workspace, exec_status="failed", rva.result_valid=False.
    Provenance: real-task-derived (see _make_result_validity_audit_invalid()).

    Asserts per spec 7.12 invalid shape:
      - interpretation.json is written
      - benchmark_result_claimed is False
      - primary_metric_value is None
      - can_conclude is []
      - cannot_conclude is non-empty (notes validity failure)
    """
    from sobench.steps import s12_write_interpretation

    ws = _build_not_blocked_workspace(
        tmp_path,
        exec_status="failed",
        rva=_make_result_validity_audit_invalid(),
    )
    assert ws.blocked is False, "Precondition: workspace must NOT be blocked"

    s12_write_interpretation.run(ws)

    interp_path = ws.artifact_path("interpretation")
    assert interp_path.exists(), (
        "s12 must write interpretation.json when execution was attempted "
        "(even if result_valid is False)"
    )

    interp = ws.read_artifact("interpretation", Interpretation)
    assert interp.task == REAL_TASK
    assert interp.method == REAL_METHOD
    assert interp.case == REAL_CASE
    assert interp.benchmark_result_claimed is False, (
        "benchmark_result_claimed must be False when result_valid is False"
    )
    assert interp.primary_metric_value is None, (
        "primary_metric_value must be null in minimal interpretation"
    )
    assert interp.can_conclude == [], (
        "can_conclude must be [] in minimal interpretation"
    )
    assert isinstance(interp.cannot_conclude, list) and len(interp.cannot_conclude) > 0, (
        "cannot_conclude must be non-empty (notes validity failure)"
    )
    assert isinstance(interp.interpretation, str) and interp.interpretation


# ---------------------------------------------------------------------------
# Test 3 — Execution attempted + result_valid:true (LLM; skip if no API key)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)
def test_s12_full_interpretation_when_result_valid(tmp_path):
    """
    s12 writes a FULL interpretation when result_valid:true and execution was
    attempted.

    Fixture: NOT-blocked workspace, exec_status="success", rva.result_valid=True.
    Provenance: real-task-derived (see _make_result_validity_audit_valid()).

    Asserts per spec 7.12 normal shape:
      - interpretation.json is written
      - benchmark_result_claimed is True
      - can_conclude is a list (may be empty if LLM is conservative)
      - cannot_conclude is a list
      - interpretation is a non-empty string
    """
    from sobench.steps import s12_write_interpretation

    ws = _build_not_blocked_workspace(
        tmp_path,
        exec_status="success",
        rva=_make_result_validity_audit_valid(),
    )
    assert ws.blocked is False, "Precondition: workspace must NOT be blocked"

    s12_write_interpretation.run(ws)

    interp_path = ws.artifact_path("interpretation")
    assert interp_path.exists(), (
        "s12 must write interpretation.json when execution was attempted and result is valid"
    )

    interp = ws.read_artifact("interpretation", Interpretation)
    assert interp.task == REAL_TASK
    assert interp.method == REAL_METHOD
    assert interp.case == REAL_CASE
    assert interp.benchmark_result_claimed is True, (
        "benchmark_result_claimed must be True when result_valid is True"
    )
    assert isinstance(interp.can_conclude, list)
    assert isinstance(interp.cannot_conclude, list)
    assert isinstance(interp.interpretation, str) and interp.interpretation
    assert isinstance(interp.open_questions, list)
