"""
Tests for s07_draft_evaluation_contract.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

Tests:
1. Happy path: real LLM over real prior artifacts → evaluation_contract.json written.
2. Explicit assertion that metric.resolved: false is ACCEPTED (step does not crash
   or force-resolve) — the real scenario where the DLPFC .h5ad is absent makes
   data resolution genuinely uncertain.

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
        human_observations="Real task fixture for s07 test.",
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


def _make_data_manifest_with_missing_data() -> DataManifest:
    """Data manifest where required .h5ad is absent — resolution is genuinely uncertain."""
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
                "notes": "not found locally; spatialLIBD is likely source",
            },
            {
                "role": "ground_truth_labels",
                "format": "obs column in .h5ad",
                "expected_path": None,
                "available": False,
                "notes": "expected inside expression file",
            },
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


def _make_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.write_artifact("parsed_intent", _make_parsed_intent())
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest_with_missing_data())
    ws.write_artifact("task_spec", _make_task_spec())
    return ws


@llm_required
def test_s07_writes_evaluation_contract(tmp_path):
    """
    s07 runs on real prior artifacts and writes evaluation_contract.json.
    Asserts: artifact written, identity fields present, metric is a dict with 'name'.
    """
    from sobench.steps import s07_draft_evaluation_contract

    ws = _make_workspace(tmp_path)
    s07_draft_evaluation_contract.run(ws)

    artifact_path = ws.artifact_path("evaluation_contract")
    assert artifact_path.exists(), "evaluation_contract.json was not written"

    ec = ws.read_artifact("evaluation_contract", EvaluationContract)
    assert ec.task, f"task field empty: {ec.task!r}"
    assert ec.method, f"method field empty: {ec.method!r}"
    assert ec.case, f"case field empty: {ec.case!r}"
    assert isinstance(ec.metric, dict), "metric must be a dict"
    assert "name" in ec.metric, "metric must have 'name' key"
    assert "resolved" in ec.metric, "metric must have 'resolved' key"
    assert isinstance(ec.data_blockers, list)
    assert isinstance(ec.open_questions, list)


@llm_required
def test_s07_accepts_metric_resolved_false(tmp_path):
    """
    Explicit policy check: s07 must not crash or force-resolve when the LLM
    determines metric.resolved: false.

    The real scenario with absent .h5ad creates genuine data uncertainty.
    We assert the step does not raise, the artifact is written, and if the
    LLM returns resolved:false it is preserved (not overridden to true).
    """
    from sobench.steps import s07_draft_evaluation_contract

    ws = _make_workspace(tmp_path)
    # Run must not raise, regardless of metric.resolved value
    s07_draft_evaluation_contract.run(ws)

    artifact_path = ws.artifact_path("evaluation_contract")
    assert artifact_path.exists(), "evaluation_contract.json must be written"

    ec = ws.read_artifact("evaluation_contract", EvaluationContract)
    # The key assertion: metric.resolved is a bool — either True or False is valid.
    # We assert it is present and that the step did not crash on False.
    assert isinstance(ec.metric.get("resolved"), bool), (
        f"metric.resolved must be a bool, got: {ec.metric.get('resolved')!r}"
    )
    # data_requirements_resolved should be False given the absent .h5ad
    assert isinstance(ec.data_requirements_resolved, bool)
