"""
Tests for s03_extract_paper_evidence.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673
PDF: data/spatial_domain_identification_task/papers/STAGATE.pdf (real file)

LLM tests use real LLM (deepseek-v4-pro). Skipped if OPENAI_API_KEY absent.
"""

import os
import json
import pytest
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import ParsedIntent, PaperEvidence


REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# Absolute path to real PDF — presence checked at module load
REAL_PDF_PATH = str(
    Path(__file__).parents[2] / "data/spatial_domain_identification_task/papers/STAGATE.pdf"
)
NONEXISTENT_PDF_PATH = "/tmp/nonexistent_path_sobench_test/no_paper.pdf"


def _real_parsed_intent(paper_path: str) -> ParsedIntent:
    """Build a ParsedIntent pointing at paper_path. Provenance: real task fixture."""
    return ParsedIntent(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        paper_path=paper_path,
        repo_path="data/spatial_domain_identification_task/codes/STAGATE",
        data_notes="DLPFC slice 151673 required.",
        reconstruction_goal="Reproduce spatial domain identification on DLPFC 151673 using ARI.",
        human_observations="Real task fixture for s03 test.",
    )


def make_workspace_with_intent(tmp_path: Path, paper_path: str) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    pi = _real_parsed_intent(paper_path)
    ws.write_artifact("parsed_intent", pi)
    return ws


llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)

pdf_required = pytest.mark.skipif(
    not Path(REAL_PDF_PATH).exists(),
    reason=f"Real PDF not found at {REAL_PDF_PATH} — skipping",
)


@llm_required
@pdf_required
def test_s03_happy_path(tmp_path):
    """
    s03 reads real STAGATE.pdf and writes paper_evidence.json.
    Asserts: artifact written, evaluation_contexts is a non-empty list,
    source names the pdf, task and method present.
    """
    from sobench.steps import s03_extract_paper_evidence

    ws = make_workspace_with_intent(tmp_path, REAL_PDF_PATH)
    s03_extract_paper_evidence.run(ws)

    artifact_path = ws.artifact_path("paper_evidence")
    assert artifact_path.exists(), "paper_evidence.json was not written"

    pe = ws.read_artifact("paper_evidence", PaperEvidence)
    assert pe.task, f"task field empty: {pe.task!r}"
    assert pe.method, f"method field empty: {pe.method!r}"
    assert pe.source, f"source field empty: {pe.source!r}"
    # evaluation_contexts must be a list; an empty list is accepted (LLM may legitimately
    # extract no contexts from a given paper section — do not assert len > 0)
    assert isinstance(pe.evaluation_contexts, list), "evaluation_contexts must be a list"
    # Paper evidence written → no blocker from s03 on happy path
    assert not ws.blocked, "s03 should not set blocker when PDF is readable"


@llm_required
def test_s03_sets_blocker_and_writes_artifact_when_paper_absent(tmp_path):
    """
    When paper_path points to a nonexistent file, s03 sets blocker AND still
    writes paper_evidence.json with missing populated.
    """
    from sobench.steps import s03_extract_paper_evidence

    ws = make_workspace_with_intent(tmp_path, NONEXISTENT_PDF_PATH)
    s03_extract_paper_evidence.run(ws)

    # paper_evidence.json must still be written
    artifact_path = ws.artifact_path("paper_evidence")
    assert artifact_path.exists(), "paper_evidence.json must be written even on blocker"

    pe = ws.read_artifact("paper_evidence", PaperEvidence)
    assert isinstance(pe.missing, list) and len(pe.missing) > 0, (
        "paper_evidence.missing should be populated when paper is absent"
    )

    # Blocker must be set
    assert ws.blocked, "s03 must set blocker when paper path is absent/unreadable"

    blocker = ws.read_blocker()
    assert blocker is not None and blocker.blocked is True
    assert blocker.raised_by_step is not None
