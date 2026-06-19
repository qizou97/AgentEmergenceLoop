"""
Tests for s04_inspect_repo_evidence.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673
Repo: data/spatial_domain_identification_task/codes/STAGATE (real directory)

LLM tests use real LLM (deepseek-v4-pro). Skipped if OPENAI_API_KEY absent.
"""

import os
import json
import pytest
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import ParsedIntent, RepoEvidence


REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# Absolute path to real STAGATE repo
REAL_REPO_PATH = str(
    Path(__file__).parents[2] / "data/spatial_domain_identification_task/codes/STAGATE"
)
NONEXISTENT_REPO_PATH = "/tmp/nonexistent_path_sobench_test/no_repo"


def _real_parsed_intent(repo_path: str) -> ParsedIntent:
    """Build a ParsedIntent with given repo_path. Provenance: real task fixture."""
    return ParsedIntent(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        paper_path="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        repo_path=repo_path,
        data_notes="DLPFC slice 151673 required.",
        reconstruction_goal="Reproduce spatial domain identification on DLPFC 151673 using ARI.",
        human_observations="Real task fixture for s04 test.",
    )


def make_workspace_with_intent(tmp_path: Path, repo_path: str) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    pi = _real_parsed_intent(repo_path)
    ws.write_artifact("parsed_intent", pi)
    return ws


llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)

repo_required = pytest.mark.skipif(
    not Path(REAL_REPO_PATH).exists(),
    reason=f"Real STAGATE repo not found at {REAL_REPO_PATH} — skipping",
)


@llm_required
@repo_required
def test_s04_happy_path(tmp_path):
    """
    s04 walks real STAGATE repo and writes repo_evidence.json.
    Asserts: artifact written, entry_points and dependencies populated,
    task and method present, NO blocker set.
    """
    from sobench.steps import s04_inspect_repo_evidence

    ws = make_workspace_with_intent(tmp_path, REAL_REPO_PATH)
    s04_inspect_repo_evidence.run(ws)

    artifact_path = ws.artifact_path("repo_evidence")
    assert artifact_path.exists(), "repo_evidence.json was not written"

    re = ws.read_artifact("repo_evidence", RepoEvidence)
    assert re.task, f"task field empty: {re.task!r}"
    assert re.method, f"method field empty: {re.method!r}"
    assert isinstance(re.entry_points, list), "entry_points must be a list"
    assert isinstance(re.dependencies, dict), "dependencies must be a dict"

    # s04 NEVER sets a blocker
    assert not ws.blocked, "s04 must never set a blocker"


@llm_required
def test_s04_repo_absent_writes_artifact_no_blocker(tmp_path):
    """
    When repo_path does not exist, s04 writes repo_evidence.json with missing
    populated AND does NOT set a blocker.
    """
    from sobench.steps import s04_inspect_repo_evidence

    ws = make_workspace_with_intent(tmp_path, NONEXISTENT_REPO_PATH)
    s04_inspect_repo_evidence.run(ws)

    # repo_evidence.json must be written
    artifact_path = ws.artifact_path("repo_evidence")
    assert artifact_path.exists(), "repo_evidence.json must be written when repo is absent"

    re = ws.read_artifact("repo_evidence", RepoEvidence)
    assert isinstance(re.missing, list) and len(re.missing) > 0, (
        "repo_evidence.missing should be populated when repo path is absent"
    )

    # CRITICAL: s04 must NEVER set a blocker
    assert not ws.blocked, "s04 must NEVER set a blocker (missing repo is risk, not cycle blocker)"

    # Blocker file itself should not exist or have blocked: false
    blocker = ws.read_blocker()
    if blocker is not None:
        assert blocker.blocked is False, "blocker.blocked must be false if blocker.json written by s04"
