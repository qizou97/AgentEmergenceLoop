"""
Tests for s13_write_experience_record.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.
Follows workspace-building style of test_s09.py / test_s12.py.

Test 1 (primary — LLM; MUST RUN when OPENAI_API_KEY present; skip otherwise):
  BLOCKED cycle. Build a real-task-derived workspace with:
    - paper_evidence, repo_evidence, data_manifest, task_spec, evaluation_contract,
      risk_audit — all derived from the real spatial_domain_identification_task.
    - blocker.json: blocked:true (DLPFC .h5ad genuinely absent)
    - execution_log.json: status="not_attempted"
  s13 ALWAYS RUNS regardless of blocked state.
  Assert:
    - experience_record.json is written
    - status == "hypothesis" (hardcoded by s13, not LLM-overridable)
    - required fields present and well-typed (id, task, method, case, tags,
      finding, evidence, confidence, failure_conditions, created)
    - evidence list is non-empty (references back into available artifacts)
    - created is a non-empty ISO-like date string (not exact — real date)

Provenance: data/spatial_domain_identification_task/ (STAGATE repo + papers)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sobench.workspace import Workspace
from sobench.models import (
    Blocker,
    DataManifest,
    EvaluationContract,
    ExecutionLog,
    ExperienceRecord,
    PaperEvidence,
    RepoEvidence,
    RiskAudit,
    TaskSpec,
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

ABSENT_H5AD = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"

llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)


# ---------------------------------------------------------------------------
# Real-task-derived artifact factories
# ---------------------------------------------------------------------------

def _make_paper_evidence() -> PaperEvidence:
    """Derived from STAGATE.pdf section 4.1: DLPFC evaluation with ARI."""
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
                    {"name": "ARI", "confidence": "high", "quote": "we report ARI across all slices"}
                ],
                "downstream_tasks": [],
                "notes": "primary evaluation; k=7 used for DLPFC slices",
            }
        ],
        coordinate_evidence="paper references spatial coordinates; coordinate space unspecified",
        coordinate_open_questions=["pixel vs array coordinates?"],
        ambiguities=["k selection procedure not described"],
        missing=["no train/test split described"],
    )


def _make_repo_evidence() -> RepoEvidence:
    """Derived from STAGATE repo structure: entry_points from README + tutorial notebooks."""
    return RepoEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        entry_points=["run_STAGATE.py"],
        dependencies={
            "python": "3.7",
            "tensorflow": "1.15.0",
            "scanpy": ">=1.5",
            "torch": "1.8.0",
        },
        hardcoded_paths=["./data/DLPFC/", "./results/"],
        metric_implementations=["sklearn.metrics.adjusted_rand_score"],
        deviations_from_paper=["default k=7 used in repo tutorial; paper varies by slice"],
        coordinate_evidence="repo loads obsm['spatial'] from .h5ad in preprocessing step",
        coordinate_open_questions=["pixel vs array space — not documented in repo"],
        ambiguities=["ground_truth column name varies across slices"],
        missing=[],
    )


def _make_data_manifest() -> DataManifest:
    """Data manifest reflecting genuine absence of DLPFC .h5ad."""
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
        open_questions=["ground truth column name"],
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
                "description": "DLPFC 151673 .h5ad absent from data directory",
                "severity": "high",
                "evidence": "data_manifest.required[0].available=false",
                "mitigation": "Download from spatialLIBD",
            }
        ],
        overall_confidence="low",
        blocker_risk_ids=["risk-001"],
    )


def _build_blocked_workspace(tmp_path: Path) -> Workspace:
    """
    Workspace representing a BLOCKED cycle grounded in the real task.
    Pre-execution artifacts are present (s01-s08 completed).
    blocker.json blocked:true + execution_log status="not_attempted"
    (DLPFC .h5ad genuinely absent).
    """
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    ws.write_artifact("risk_audit", _make_risk_audit())

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

    return ws


# ---------------------------------------------------------------------------
# Test 1 — Blocked cycle (PRIMARY; LLM required; MUST run when API key present)
# ---------------------------------------------------------------------------

@llm_required
def test_s13_writes_experience_record_for_blocked_cycle(tmp_path):
    """
    s13 ALWAYS runs regardless of blocked state and writes experience_record.json.

    Fixture: BLOCKED cycle grounded in the real spatial_domain_identification_task.
    Real-task ground truth: ABSENT_H5AD does not exist on disk.

    Asserts:
      - experience_record.json is written
      - status == "hypothesis" (hardcoded; LLM cannot override)
      - id, task, method, case, tags, finding, evidence, confidence,
        failure_conditions, created all present and well-typed
      - evidence is non-empty (references available artifacts, e.g.
        data_manifest.required[0] or blocker.detail)
      - created is a non-empty ISO-like date string (YYYY-MM-DD format)
      - task == REAL_TASK, method == REAL_METHOD, case == REAL_CASE
    """
    assert not Path(ABSENT_H5AD).exists(), (
        f"Assumption violated: {ABSENT_H5AD!r} now exists on disk. "
        "Update the test — designed for genuinely-absent DLPFC data."
    )

    from sobench.steps import s13_write_experience_record

    ws = _build_blocked_workspace(tmp_path)
    assert ws.blocked is True, "Precondition: workspace must be blocked"

    s13_write_experience_record.run(ws)

    rec_path = ws.artifact_path("experience_record")
    assert rec_path.exists(), "s13 MUST write experience_record.json (always runs, even when blocked)"

    rec = ws.read_artifact("experience_record", ExperienceRecord)

    # Identity
    assert rec.task == REAL_TASK
    assert rec.method == REAL_METHOD
    assert rec.case == REAL_CASE

    # status MUST be "hypothesis" — hardcoded, not LLM-overridable
    assert rec.status == "hypothesis", (
        f"status must be 'hypothesis' (hardcoded by s13), got: {rec.status!r}"
    )

    # Required fields must be non-empty and well-typed
    assert isinstance(rec.id, str) and rec.id, "id must be a non-empty string"
    assert isinstance(rec.finding, str) and rec.finding, "finding must be a non-empty string"
    assert isinstance(rec.tags, list) and len(rec.tags) > 0, "tags must be a non-empty list"
    assert isinstance(rec.evidence, list) and len(rec.evidence) > 0, (
        "evidence must be non-empty — references back into available artifacts"
    )
    assert isinstance(rec.confidence, str) and rec.confidence, "confidence must be non-empty string"
    assert isinstance(rec.failure_conditions, list), "failure_conditions must be a list"

    # created must be a non-empty ISO-like date string (YYYY-MM-DD or similar)
    import re
    assert isinstance(rec.created, str) and rec.created, "created must be a non-empty string"
    assert re.match(r"\d{4}-\d{2}-\d{2}", rec.created), (
        f"created must match YYYY-MM-DD format, got: {rec.created!r}"
    )
