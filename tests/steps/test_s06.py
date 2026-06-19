"""
Tests for s06_draft_task_spec.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

Tests:
1. Happy path: real LLM over real prior artifacts → task_spec.json written,
   source_context selected.
2. Blocked case: prior artifacts with NO selectable evaluation context
   (paper_evidence with empty evaluation_contexts) → blocker set.

All LLM tests skip if OPENAI_API_KEY is absent.
Provenance: data/spatial_domain_identification_task/
"""

import os
import json
import pytest
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import (
    ParsedIntent,
    PaperEvidence,
    RepoEvidence,
    DataManifest,
    TaskSpec,
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

REPO_ROOT = Path(__file__).parents[2]

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
        human_observations="Real task fixture for s06 test.",
    )


def _make_paper_evidence_with_contexts() -> PaperEvidence:
    """Paper evidence with a real evaluation context (happy path)."""
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


def _make_paper_evidence_no_contexts() -> PaperEvidence:
    """Paper evidence with empty evaluation_contexts (blocked case)."""
    return PaperEvidence(
        task=REAL_TASK,
        method=REAL_METHOD,
        source="STAGATE.pdf",
        evaluation_contexts=[],  # empty → no selectable context
        coordinate_evidence="",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=["no evaluation contexts found in paper"],
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


def _make_workspace(tmp_path: Path, paper_evidence: PaperEvidence) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.write_artifact("parsed_intent", _make_parsed_intent())
    ws.write_artifact("paper_evidence", paper_evidence)
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    ws.write_artifact("data_manifest", _make_data_manifest())
    return ws


@llm_required
def test_s06_writes_task_spec_and_selects_context(tmp_path):
    """
    s06 runs on real prior artifacts (with evaluation context) and writes task_spec.json.
    Asserts: artifact written, identity fields present, source_context is non-empty,
    primary_metric is a dict with 'name' key.
    """
    from sobench.steps import s06_draft_task_spec

    ws = _make_workspace(tmp_path, _make_paper_evidence_with_contexts())
    s06_draft_task_spec.run(ws)

    artifact_path = ws.artifact_path("task_spec")
    assert artifact_path.exists(), "task_spec.json was not written"

    ts = ws.read_artifact("task_spec", TaskSpec)
    assert ts.task, f"task field empty: {ts.task!r}"
    assert ts.method, f"method field empty: {ts.method!r}"
    assert ts.case, f"case field empty: {ts.case!r}"
    assert ts.source_context, f"source_context must be set, got: {ts.source_context!r}"
    assert isinstance(ts.primary_metric, dict), "primary_metric must be a dict"
    assert "name" in ts.primary_metric, "primary_metric must have 'name' key"
    assert isinstance(ts.assumptions, list)
    assert isinstance(ts.unresolved, list)


@llm_required
def test_s06_sets_blocker_when_no_evaluation_context(tmp_path):
    """
    When paper_evidence has empty evaluation_contexts, s06 cannot select a context
    and must set a blocker. task_spec.json is still written.
    """
    from sobench.steps import s06_draft_task_spec

    ws = _make_workspace(tmp_path, _make_paper_evidence_no_contexts())
    s06_draft_task_spec.run(ws)

    # task_spec.json must still be written even when blocked
    artifact_path = ws.artifact_path("task_spec")
    assert artifact_path.exists(), "task_spec.json must be written even when setting blocker"

    # Blocker must be set
    assert ws.blocked, "s06 must set blocker when no evaluation context is selectable"
    blocker = ws.read_blocker()
    assert blocker is not None
    assert blocker.blocked is True
    assert blocker.raised_by_step is not None
