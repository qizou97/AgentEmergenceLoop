"""
Tests for s08_draft_risk_audit.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

Tests:
1. Happy path: real LLM over real prior artifacts → risk_audit.json written
   even when risks list may be empty.
2. Explicit assertion: risk_audit.json ALWAYS written; valid RiskAudit regardless
   of len(risks).

LLM tests skip if OPENAI_API_KEY is absent.
Provenance: data/spatial_domain_identification_task/
"""

import os
import pytest
from pathlib import Path

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

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)


def _make_parsed_intent() -> ParsedIntent:
    return ParsedIntent(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        paper_path="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        repo_path="data/spatial_domain_identification_task/codes/STAGATE",
        data_notes="DLPFC slice 151673 required.",
        reconstruction_goal="Reproduce spatial domain identification on DLPFC 151673 using ARI.",
        human_observations="Real task fixture for s08 test.",
    )


def _make_paper_evidence() -> PaperEvidence:
    return PaperEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        source="STAGATE.pdf",
        evaluation_contexts=[
            {
                "id": "ctx-001",
                "task": "spatial_domain_identification",
                "cases": ["DLPFC_151673"],
                "metrics": [{"name": "ARI", "confidence": "high", "quote": "ARI reported"}],
                "downstream_tasks": [],
                "notes": "primary evaluation",
            }
        ],
        coordinate_evidence="paper references spatial coordinates",
        coordinate_open_questions=["which coordinate space?"],
        ambiguities=["k selection not described"],
        missing=[],
    )


def _make_repo_evidence() -> RepoEvidence:
    return RepoEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        entry_points=["run_STAGATE.py"],
        dependencies={"python": "3.8", "packages": ["scanpy", "torch"]},
        hardcoded_paths=["./data/DLPFC/"],
        metric_implementations=[{"name": "ARI", "file": "utils.py", "line": 42, "matches_paper": True}],
        deviations_from_paper=["tutorial uses raw counts"],
        coordinate_evidence="spatial coords loaded from obsm['spatial']",
        coordinate_open_questions=["pixel vs array space?"],
        ambiguities=["tutorial uses different slice"],
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
                "expected_path": "data/spatial_domain_identification_task/DLPFC/151673.h5ad",
                "available": False,
                "notes": "not found locally",
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
        input_description="AnnData with expression matrix and spatial coordinates",
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
        metric={"name": "ARI", "resolved": True, "implementation": "sklearn.metrics.adjusted_rand_score",
                "provenance": "stated in paper ctx-001", "known_risks": ["sensitive to k"]},
        data_requirements_resolved=False,
        data_blockers=["expression file not found locally"],
        open_questions=["ground truth column name", "k selection"],
    )


def _make_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.write_artifact("parsed_intent", _make_parsed_intent())
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    ws.write_artifact("task_spec", _make_task_spec())
    ws.write_artifact("evaluation_contract", _make_evaluation_contract())
    return ws


@llm_required
def test_s08_always_writes_risk_audit(tmp_path):
    """
    s08 runs on real prior artifacts and ALWAYS writes risk_audit.json,
    even if the risks list is empty.
    Asserts: artifact written, valid RiskAudit (identity fields, risks is list,
    overall_confidence present, blocker_risk_ids is list).
    """
    from sobench.steps import s08_draft_risk_audit

    ws = _make_workspace(tmp_path)
    s08_draft_risk_audit.run(ws)

    artifact_path = ws.artifact_path("risk_audit")
    assert artifact_path.exists(), "risk_audit.json must ALWAYS be written"

    ra = ws.read_artifact("risk_audit", RiskAudit)
    assert ra.task, f"task field empty: {ra.task!r}"
    assert ra.method, f"method field empty: {ra.method!r}"
    assert ra.case, f"case field empty: {ra.case!r}"

    # risks may be empty — that is valid per spec
    assert isinstance(ra.risks, list), "risks must be a list (may be empty)"

    # overall_confidence must be a non-empty string
    assert isinstance(ra.overall_confidence, str) and ra.overall_confidence, (
        f"overall_confidence must be a non-empty string, got: {ra.overall_confidence!r}"
    )

    # blocker_risk_ids must be a list
    assert isinstance(ra.blocker_risk_ids, list), "blocker_risk_ids must be a list"

    # No blocker set by s08
    # (s08 never sets a blocker per spec section 8)
    # Note: workspace may have no blocker.json at all — that is fine


@llm_required
def test_s08_risk_structure_when_risks_present(tmp_path):
    """
    When the LLM enumerates risks, each risk must have the required fields
    (id, category, description, severity, evidence, mitigation) per spec 7.7.
    """
    from sobench.steps import s08_draft_risk_audit

    ws = _make_workspace(tmp_path)
    s08_draft_risk_audit.run(ws)

    ra = ws.read_artifact("risk_audit", RiskAudit)

    for risk in ra.risks:
        assert "id" in risk, f"risk missing 'id': {risk}"
        assert "category" in risk, f"risk missing 'category': {risk}"
        assert "description" in risk, f"risk missing 'description': {risk}"
        assert "severity" in risk, f"risk missing 'severity': {risk}"
        assert "evidence" in risk, f"risk missing 'evidence': {risk}"
        assert "mitigation" in risk, f"risk missing 'mitigation': {risk}"
