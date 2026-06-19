"""
Tests for s11_audit_result_validity.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.
Follows the same workspace-building style as test_s09.py and test_s10.py.

Test 1 (primary, deterministic — MUST RUN, no skip):
  Blocked path. Build workspace with blocker.json blocked:true +
  execution_log.json status="not_attempted" (real-task-derived).
  Assert s11 writes NO result_validity_audit.json.
  No LLM, no skip allowed.

Test 2 (not-blocked path — LLM required; skipped if OPENAI_API_KEY absent):
  Build a NOT-blocked workspace with real raw_observations.json, task_spec.json,
  evaluation_contract.json (all real-task-derived).
  Assert result_validity_audit.json is written with required fields.

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
    RawObservations,
    ResultValidityAudit,
    TaskSpec,
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

ABSENT_H5AD = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"


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
    Real-task-derived raw observations for DLPFC 151673 / STAGATE.

    Provenance: STAGATE outputs per-spot cluster labels for DLPFC 151673.
    output_shape rows=10 because the not-blocked test fixture uses a 10-row
    minimal CSV (representing the first 10 spots of DLPFC 151673).
    metric_raw ARI is not computed in s10/s11 (no ground truth available
    in this fixture); we record name only, value null — consistent with
    the evaluation_contract having data_requirements_resolved:false for
    the ground truth column.
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


# ---------------------------------------------------------------------------
# Test 1 — Blocked path (PRIMARY, deterministic, NO skip allowed)
# ---------------------------------------------------------------------------

def test_s11_no_artifact_when_blocked(tmp_path):
    """
    s11 writes NO result_validity_audit.json when workspace.blocked is True.

    Real-task ground truth: ABSENT_H5AD does not exist on disk.
    The workspace state mirrors what s09 produces for the blocked path.
    This test is deterministic — no LLM calls, no skip allowed.

    Asserts: result_validity_audit.json does NOT exist after s11.run().
    """
    assert not Path(ABSENT_H5AD).exists(), (
        f"Assumption violated: {ABSENT_H5AD!r} now exists on disk. "
        "Update the test — it was designed for genuinely-absent DLPFC data."
    )

    from sobench.steps import s11_audit_result_validity

    ws = _build_blocked_workspace(tmp_path)
    assert ws.blocked is True, "Precondition: workspace must be blocked"

    s11_audit_result_validity.run(ws)

    audit_path = ws.artifact_path("result_validity_audit")
    assert not audit_path.exists(), (
        "s11 must NOT write result_validity_audit.json when workspace.blocked is True; "
        f"but file exists at {audit_path}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Not-blocked path (LLM required; skipped if OPENAI_API_KEY absent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)
def test_s11_writes_audit_when_not_blocked(tmp_path):
    """
    s11 writes result_validity_audit.json when workspace is NOT blocked.

    Fixture:
      - blocker.json: blocked:false
      - execution_log.json: status="success"
      - raw_observations.json: real-task-derived (10-spot DLPFC 151673 STAGATE output)
      - task_spec.json + evaluation_contract.json: real-task-derived

    Asserts:
      - result_validity_audit.json is written
      - Contains required fields from spec 7.11
      - task, method, case match expected identity
      - result_valid is bool
      - checks is a non-empty list
    """
    from sobench.steps import s11_audit_result_validity

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    # Write blocker.json with blocked:false
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

    ws.write_artifact("raw_observations", _make_raw_observations())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())

    assert ws.blocked is False, "Precondition: workspace must NOT be blocked"

    s11_audit_result_validity.run(ws)

    audit_path = ws.artifact_path("result_validity_audit")
    assert audit_path.exists(), (
        "s11 must write result_validity_audit.json when not blocked"
    )

    rva = ws.read_artifact("result_validity_audit", ResultValidityAudit)
    assert rva.task == REAL_TASK
    assert rva.method == REAL_METHOD
    assert rva.case == REAL_CASE
    assert isinstance(rva.result_valid, bool)
    assert isinstance(rva.checks, list) and len(rva.checks) > 0, (
        "checks must be a non-empty list per spec 7.11"
    )
    assert isinstance(rva.validity_reasoning, str) and rva.validity_reasoning
    assert isinstance(rva.warnings, list)
