"""
Tests for s09_execute_or_block.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.

Test 1 (primary, deterministic — MUST RUN, no skip):
  Blocked path.  The DLPFC 151673 .h5ad is genuinely absent under data/.
  Build real-task-derived artifacts directly (data_manifest with required .h5ad
  available:false, matching the known path that does not exist on disk).
  repo_evidence is written with the real STAGATE entry_points (grounded in
  the STAGATE repo) so that s09's new repo_evidence read does not break this path.
  Assert:
    - blocker.json exists with blocked:true
    - execution_log.json exists with status == "not_attempted"
    - workspace.blocked is True

Test 2 (feasible path — skipped explicitly if entry-point cannot run):
  The real STAGATE pipeline requires tensorflow==1.15.0 + scanpy + torch, none
  of which are installed in this environment (Python 3.13).  Therefore we skip
  this path with an explicit reason rather than mocking subprocess.
  Body is correct and grounded in real-task artifacts (including repo_evidence
  with real entry_points).  Remove the skip when the environment ships the deps.

Provenance: data/spatial_domain_identification_task/ (STAGATE repo + papers)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sobench.workspace import Workspace
from sobench.models import (
    DataManifest,
    EvaluationContract,
    ExecutionLog,
    Blocker,
    RepoEvidence,
    RiskAudit,
    TaskSpec,
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# The .h5ad path that STAGATE expects — genuinely absent on disk.
# Derived from: STAGATE repo hard-coded paths ("./data/DLPFC/") and the
# standard spatialLIBD filename for slice 151673.
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
        data_blockers=["DLPFC 151673 .h5ad not found locally"],
        open_questions=["ground truth column name", "k selection"],
    )


def _make_risk_audit_with_blockers() -> RiskAudit:
    """Risk audit where data absence has been escalated to blocker_risk_ids."""
    return RiskAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        risks=[
            {
                "id": "risk-001",
                "category": "data",
                "description": "DLPFC 151673 .h5ad absent from data directory",
                "severity": "high",
                "evidence": "data_manifest.required[0].available=false",
                "mitigation": "Download from spatialLIBD",
            }
        ],
        overall_confidence="low",
        blocker_risk_ids=["risk-001"],
    )


def _make_risk_audit_no_blockers() -> RiskAudit:
    """Risk audit with no blocker_risk_ids (all risks mitigated or low severity)."""
    return RiskAudit(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        risks=[
            {
                "id": "risk-002",
                "category": "software",
                "description": "tensorflow==1.15.0 requires Python < 3.9",
                "severity": "medium",
                "evidence": "PyPI metadata for tensorflow 1.15.0",
                "mitigation": "Use conda environment with Python 3.7",
            }
        ],
        overall_confidence="medium",
        blocker_risk_ids=[],
    )


def _make_data_manifest_unavailable() -> DataManifest:
    """Data manifest reflecting the genuine absence of the DLPFC .h5ad."""
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
        coordinate_assumptions="none made yet",
        coordinate_open_questions=["pixel vs array space?"],
        coordinate_checks=[],
        open_questions=["ground truth column name in .h5ad?"],
    )


def _make_data_manifest_available(h5ad_path: str) -> DataManifest:
    """Data manifest where the required .h5ad is available (for feasible-path test)."""
    return DataManifest(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        required=[
            {
                "role": "expression_matrix_with_coords",
                "format": "AnnData .h5ad",
                "expected_path": h5ad_path,
                "available": True,
                "notes": "spatialLIBD DLPFC slice 151673 — present on disk",
            }
        ],
        coordinate_evidence="repo loads obsm['spatial'] from .h5ad",
        coordinate_assumptions="coordinates in obsm['spatial'] as pixel coordinates",
        coordinate_open_questions=[],
        coordinate_checks=["obsm['spatial'] confirmed present"],
        open_questions=[],
    )


def _make_repo_evidence_stagate() -> RepoEvidence:
    """
    Real-task RepoEvidence grounded in the STAGATE repository.

    entry_points derived from STAGATE repo structure:
      - run_STAGATE.py is the top-level training script referenced in
        README.md and used across DLPFC tutorial notebooks.
    missing: [] — repo was cloned successfully by s04.
    """
    return RepoEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        entry_points=["run_STAGATE.py"],
        dependencies={
            "python": "3.7",
            "tensorflow": "1.15.0",
            "scanpy": ">=1.5",
            "torch": "1.8.0",
            "torch-geometric": "unspecified",
        },
        hardcoded_paths=["./data/DLPFC/", "./results/"],
        metric_implementations=["sklearn.metrics.adjusted_rand_score"],
        deviations_from_paper=["default k=7 used in repo tutorial, paper varies by slice"],
        coordinate_evidence="repo loads obsm['spatial'] from .h5ad in preprocessing step",
        coordinate_open_questions=["pixel vs array space — not documented in repo"],
        ambiguities=["ground_truth column name varies across slices"],
        missing=[],
    )


def _build_blocked_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit_with_blockers())
    ws.write_artifact("data_manifest", _make_data_manifest_unavailable())
    ws.write_artifact("repo_evidence", _make_repo_evidence_stagate())
    return ws


# ---------------------------------------------------------------------------
# Test 1 — Blocked path (PRIMARY, deterministic, NO skip allowed)
# ---------------------------------------------------------------------------

def test_s09_blocked_when_required_data_absent(tmp_path):
    """
    s09 sets blocked:true when a required data item is available:false.

    Real-task ground truth: ABSENT_H5AD does not exist on disk.
    This test is deterministic — no LLM calls, no skip.

    repo_evidence is written (entry_points populated from STAGATE repo) so
    the new repo_evidence read in s09 does not break this path.

    Asserts:
      - workspace.blocked is True after run
      - blocker.json exists with blocked=True
      - execution_log.json exists with status == "not_attempted"
      - execution_log has empty stdout_excerpt and stderr_excerpt
      - execution_log.duration_seconds is None
      - ABSENT_H5AD genuinely does not exist on disk (guard against future data addition)
    """
    # Guard: confirm the real .h5ad is genuinely absent on disk
    assert not Path(ABSENT_H5AD).exists(), (
        f"Assumption violated: {ABSENT_H5AD!r} now exists on disk. "
        "The test was designed for the genuinely-absent data scenario. "
        "Update the test if the real data has been added."
    )

    from sobench.steps import s09_execute_or_block

    ws = _build_blocked_workspace(tmp_path)
    s09_execute_or_block.run(ws)

    # blocker.json must exist and be blocked:true
    blocker_path = ws.artifact_path("blocker")
    assert blocker_path.exists(), "blocker.json must always be written by s09"

    blocker = ws.read_artifact("blocker", Blocker)
    assert blocker.blocked is True, f"Expected blocked=True, got: {blocker.blocked}"
    assert blocker.raised_by_step == "s09_execute_or_block"
    assert blocker.reason, "Blocker must have a non-empty reason"
    assert blocker.detail, "Blocker must have non-empty detail"
    assert blocker.human_action_required is True

    # execution_log.json must exist with status "not_attempted"
    elog_path = ws.artifact_path("execution_log")
    assert elog_path.exists(), "execution_log.json must always be written by s09"

    elog = ws.read_artifact("execution_log", ExecutionLog)
    assert elog.status == "not_attempted", (
        f"Expected status='not_attempted', got: {elog.status!r}"
    )
    assert elog.stdout_excerpt == "", f"Expected empty stdout_excerpt, got: {elog.stdout_excerpt!r}"
    assert elog.stderr_excerpt == "", f"Expected empty stderr_excerpt, got: {elog.stderr_excerpt!r}"
    assert elog.duration_seconds is None, (
        f"Expected duration_seconds=None, got: {elog.duration_seconds!r}"
    )
    assert isinstance(elog.output_files, list) and len(elog.output_files) == 0

    # workspace.blocked must be True
    assert ws.blocked is True, "workspace.blocked must be True after s09 sets blocker"


# ---------------------------------------------------------------------------
# Test 2 — Feasible path (SKIPPED — real STAGATE pipeline cannot run here)
# ---------------------------------------------------------------------------

@pytest.mark.skip(
    reason=(
        "Feasible-path test skipped: the real STAGATE pipeline requires "
        "tensorflow==1.15.0 + scanpy + torch, none of which are installed in "
        "this environment (Python 3.13). Subprocess is NOT mocked. "
        "Remove this skip when the environment ships the required dependencies."
    )
)
def test_s09_feasible_path_runs_real_subprocess(tmp_path):
    """
    s09 runs the real entry-point command when all required data is present.

    Skipped because STAGATE's deps (tensorflow==1.15.0, scanpy, torch) are
    absent.  Body is correct and grounded in real-task artifacts; remove the
    skip to exercise the feasible path when deps are installed.

    Setup:
      - repo_evidence with entry_points=["run_STAGATE.py"] (STAGATE repo)
      - data_manifest with available:true (pointing at a real existing .h5ad)
      - risk_audit with blocker_risk_ids=[] (no blockers)
      - task_spec and evaluation_contract grounded in the real task

    The .h5ad used here must genuinely exist on disk (spatialLIBD DLPFC 151673).
    If the file is absent, this test would fail at data_manifest validation
    inside s09 (available:true but file absent won't be caught by s09 itself —
    s09 trusts the manifest — so the subprocess would fail with "not found"
    and execution_log.status would be "failed", which is still a valid result).
    """
    from sobench.steps import s09_execute_or_block

    # Real .h5ad path — must exist when this test is enabled.
    real_h5ad = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit_no_blockers())
    ws.write_artifact("data_manifest", _make_data_manifest_available(real_h5ad))
    ws.write_artifact("repo_evidence", _make_repo_evidence_stagate())

    s09_execute_or_block.run(ws)

    # Both artifacts must be written
    assert ws.artifact_path("blocker").exists()
    assert ws.artifact_path("execution_log").exists()

    blocker = ws.read_artifact("blocker", Blocker)
    assert blocker.blocked is False, f"Expected blocked=False, got: {blocker.blocked}"

    elog = ws.read_artifact("execution_log", ExecutionLog)
    assert elog.status in {"success", "failed"}, (
        f"Expected status in {{success, failed}}, got: {elog.status!r}"
    )
    # Real stdout/stderr captured from subprocess (may be empty if command silent)
    assert isinstance(elog.stdout_excerpt, str)
    assert isinstance(elog.stderr_excerpt, str)
    assert elog.duration_seconds is not None and elog.duration_seconds >= 0
    assert isinstance(elog.output_files, list)

    # workspace.blocked must be False on the feasible path
    assert ws.blocked is False
