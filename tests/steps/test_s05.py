"""
Tests for s05_build_data_manifest.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

Key policy-critical assertion: the REAL Path.exists() check in s05.
  - Items with an expected_path pointing at a genuinely-absent .h5ad file
    must have available: false.
  - Items with an expected_path pointing at a file that REALLY EXISTS under
    data/ must have available: true.
  - s05 NEVER sets a blocker.

LLM tests skip if OPENAI_API_KEY is absent.
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
)

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# --- Real existing files (relative to repo root) ---
REAL_PDF_REL = "data/spatial_domain_identification_task/papers/STAGATE.pdf"
REAL_README_REL = "data/spatial_domain_identification_task/codes/STAGATE/README.md"

# --- Genuinely absent data file (no .h5ad exists anywhere under data/) ---
ABSENT_H5AD_REL = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"

REPO_ROOT = Path(__file__).parents[2]

llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)


def _make_paper_evidence() -> PaperEvidence:
    """Minimal real-task-derived PaperEvidence for s05 inputs."""
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
        missing=["no train/test split described"],
    )


def _make_repo_evidence() -> RepoEvidence:
    """Minimal real-task-derived RepoEvidence for s05 inputs."""
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


def _make_parsed_intent() -> ParsedIntent:
    return ParsedIntent(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        paper_path=REAL_PDF_REL,
        repo_path="data/spatial_domain_identification_task/codes/STAGATE",
        data_notes="DLPFC slice 151673 required.",
        reconstruction_goal="Reproduce spatial domain identification on DLPFC 151673 using ARI.",
        human_observations="Real task fixture for s05 test.",
    )


def _make_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    ws.write_artifact("parsed_intent", _make_parsed_intent())
    ws.write_artifact("paper_evidence", _make_paper_evidence())
    ws.write_artifact("repo_evidence", _make_repo_evidence())
    return ws


@llm_required
def test_s05_writes_data_manifest(tmp_path):
    """
    s05 runs on real prior artifacts, writes data_manifest.json with correct fields.
    Asserts: artifact written, identity fields present, required is a list,
    coordinate fields present, NO blocker written.
    """
    from sobench.steps import s05_build_data_manifest

    ws = _make_workspace(tmp_path)
    s05_build_data_manifest.run(ws)

    artifact_path = ws.artifact_path("data_manifest")
    assert artifact_path.exists(), "data_manifest.json was not written"

    dm = ws.read_artifact("data_manifest", DataManifest)
    assert dm.task, f"task field empty: {dm.task!r}"
    assert dm.method, f"method field empty: {dm.method!r}"
    assert dm.case, f"case field empty: {dm.case!r}"
    assert isinstance(dm.required, list), "required must be a list"

    # Coordinate free-form fields must be present (strings/lists)
    assert isinstance(dm.coordinate_evidence, str)
    assert isinstance(dm.coordinate_open_questions, list)
    assert isinstance(dm.coordinate_assumptions, str)
    assert isinstance(dm.coordinate_checks, list)
    assert isinstance(dm.open_questions, list)

    # s05 NEVER sets a blocker
    assert not ws.blocked, "s05 must NEVER write a blocker"
    assert ws.read_blocker() is None, "s05 must never write blocker.json"


@llm_required
def test_s05_availability_reflects_real_filesystem(tmp_path):
    """
    Core policy-critical test: s05 checks Path.exists() in Python.

    After s05 runs:
    - Any required item whose expected_path is ABSENT on real filesystem
      (e.g. the DLPFC 151673 .h5ad) → available: false
    - Any required item whose expected_path EXISTS on real filesystem
      (e.g. STAGATE.pdf or README.md) → available: true

    Also confirms: null/empty expected_path → available: false.
    """
    from sobench.steps import s05_build_data_manifest

    ws = _make_workspace(tmp_path)
    s05_build_data_manifest.run(ws)

    dm = ws.read_artifact("data_manifest", DataManifest)
    assert isinstance(dm.required, list), "required must be a list"

    # Assert that the availability flag correctly mirrors Path.exists() for
    # each item the LLM produced, regardless of which exact paths it chose.
    for item in dm.required:
        ep = item.get("expected_path") or ""
        if not ep:
            assert item["available"] is False, (
                f"null/empty expected_path must produce available:false, got: {item}"
            )
        else:
            real_path = REPO_ROOT / ep
            expected_available = real_path.exists()
            assert item["available"] == expected_available, (
                f"availability mismatch for {ep!r}: "
                f"Path.exists()={expected_available}, manifest.available={item['available']}"
            )

    # --- Specific real-filesystem assertions ---
    # The DLPFC .h5ad genuinely does not exist anywhere under data/
    absent_path = REPO_ROOT / ABSENT_H5AD_REL
    assert not absent_path.exists(), (
        f"Test assumption broken: {ABSENT_H5AD_REL} now exists — update test"
    )

    # The STAGATE PDF does exist
    real_pdf = REPO_ROOT / REAL_PDF_REL
    assert real_pdf.exists(), (
        f"Test assumption broken: {REAL_PDF_REL} not found — update test"
    )

    # If the LLM produced an item pointing at the absent h5ad, it must be available:false
    h5ad_items = [
        item for item in dm.required
        if item.get("expected_path") and item["expected_path"].endswith(".h5ad")
    ]
    for item in h5ad_items:
        ep = item["expected_path"]
        if not (REPO_ROOT / ep).exists():
            assert item["available"] is False, (
                f"Absent .h5ad {ep!r} must have available:false, got: {item}"
            )

    # If the LLM produced an item whose expected_path points at the real PDF,
    # it must be available:true
    pdf_items = [
        item for item in dm.required
        if item.get("expected_path") and (REPO_ROOT / item["expected_path"]).exists()
    ]
    for item in pdf_items:
        assert item["available"] is True, (
            f"Existing path {item['expected_path']!r} must have available:true, got: {item}"
        )
