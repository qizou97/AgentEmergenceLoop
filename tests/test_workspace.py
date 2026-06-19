"""
Tests for sobench/workspace.py — path resolution, artifact I/O, blocked property.

Per docs/TESTING_POLICY.md: no mocks; real filesystem via tmp_path (explicitly allowed).
All identity values drawn from the real benchmark task:
  data/spatial_domain_identification_task/
  task: spatial_domain_identification, method: STAGATE, case: DLPFC_151673
"""

import json
import pytest
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import (
    Blocker,
    ExecutionLog,
    ParsedIntent,
)

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def test_workspace_dir_is_task_case_method(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    expected = tmp_path / TASK / CASE / METHOD
    assert ws.dir == expected


def test_artifact_path_is_under_workspace_dir(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    p = ws.artifact_path("paper_evidence")
    assert p == ws.dir / "paper_evidence.json"


# ---------------------------------------------------------------------------
# write_artifact / read_artifact round-trip
# ---------------------------------------------------------------------------

def test_write_and_read_artifact_roundtrip(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    obj = ParsedIntent(
        task=TASK,
        method=METHOD,
        case=CASE,
        paper_path="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        repo_path="data/spatial_domain_identification_task/codes/STAGATE",
        data_notes="DLPFC slice 151673 required.",
        reconstruction_goal="Reproduce spatial domain identification result.",
        human_observations="",
    )
    ws.write_artifact("parsed_intent", obj)
    restored = ws.read_artifact("parsed_intent", ParsedIntent)
    assert restored == obj


def test_write_artifact_creates_parent_dirs(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    # dir does not exist yet
    assert not ws.dir.exists()
    obj = ParsedIntent(
        task=TASK, method=METHOD, case=CASE,
        paper_path="", repo_path="", data_notes="",
        reconstruction_goal="", human_observations="",
    )
    ws.write_artifact("parsed_intent", obj)
    assert ws.dir.exists()
    assert ws.artifact_path("parsed_intent").exists()


def test_write_artifact_produces_valid_json(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    obj = ExecutionLog(
        task=TASK, method=METHOD, case=CASE,
        status="not_attempted",
        command="python run_STAGATE.py --slice 151673",
        stdout_excerpt="", stderr_excerpt="",
        duration_seconds=None,
        environment={"python": "3.10", "platform": "linux"},
        output_files=[],
    )
    ws.write_artifact("execution_log", obj)
    raw = ws.artifact_path("execution_log").read_text()
    parsed = json.loads(raw)
    assert parsed["status"] == "not_attempted"
    assert parsed["task"] == TASK


# ---------------------------------------------------------------------------
# read_blocker
# ---------------------------------------------------------------------------

def test_read_blocker_returns_none_when_absent(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    assert ws.read_blocker() is None


def test_read_blocker_returns_blocker_when_present(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    blocker = Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail="data/DLPFC/151673.h5ad does not exist",
        evidence="data_manifest.required[0].available=false",
        resolution="download from spatialLIBD",
        human_action_required=True,
    )
    ws.write_artifact("blocker", blocker)
    result = ws.read_blocker()
    assert result is not None
    assert result == blocker


def test_read_blocker_not_blocked(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
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
    result = ws.read_blocker()
    assert result is not None
    assert result.blocked is False


# ---------------------------------------------------------------------------
# blocked property
# ---------------------------------------------------------------------------

def test_blocked_false_when_no_blocker_file(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    assert ws.blocked is False


def test_blocked_false_when_blocker_json_blocked_false(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    ws.write_artifact("blocker", Blocker(
        blocked=False, raised_by_step=None, reason=None,
        detail=None, evidence=None, resolution=None,
        human_action_required=False,
    ))
    assert ws.blocked is False


def test_blocked_true_when_blocker_json_blocked_true(tmp_path):
    ws = Workspace(TASK, METHOD, CASE, root=str(tmp_path))
    ws.write_artifact("blocker", Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail="data/DLPFC/151673.h5ad does not exist",
        evidence="data_manifest.required[0].available=false",
        resolution="download from spatialLIBD",
        human_action_required=True,
    ))
    assert ws.blocked is True
