"""
Tests for s01_ensure_workspace.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673
The test builds a workspace under tmp_path pointing at real data/ paths.
No LLM calls — s01 is pure file-system validation.
"""

import pytest
from pathlib import Path

from sobench.workspace import Workspace


REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

BENCHMARK_INTENT_CONTENT = """\
## Task
spatial_domain_identification

## Method
STAGATE

## Case
DLPFC_151673

## Paper
path: data/spatial_domain_identification_task/papers/STAGATE.pdf
notes: Section 4.1 describes DLPFC evaluation. ARI mentioned as primary metric.

## Repository
path: data/spatial_domain_identification_task/codes/STAGATE
notes: Entry point unclear. Tutorial notebook exists.

## Data
notes: DLPFC slice 151673 required. File location unknown locally.

## What to reconstruct
Reproduce the spatial domain identification result on DLPFC 151673 as reported
in the paper, using ARI as the primary metric if evidence supports it.

## Human observations
Real task derived fixture for s01 test. Provenance: data/spatial_domain_identification_task/
"""


def make_workspace(tmp_path: Path, with_intent: bool = True) -> Workspace:
    """Build a workspace under tmp_path and optionally write benchmark_intent.md."""
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    if with_intent:
        (ws.dir / "benchmark_intent.md").write_text(BENCHMARK_INTENT_CONTENT)
    return ws


def test_s01_passes_with_valid_workspace(tmp_path):
    """s01 succeeds when workspace dir and benchmark_intent.md are present."""
    from sobench.steps import s01_ensure_workspace
    ws = make_workspace(tmp_path, with_intent=True)
    # Should not raise
    s01_ensure_workspace.run(ws)


def test_s01_raises_when_workspace_dir_missing(tmp_path):
    """s01 raises FileNotFoundError when workspace directory does not exist."""
    from sobench.steps import s01_ensure_workspace
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    # Do NOT create the directory
    with pytest.raises(FileNotFoundError, match="Workspace directory"):
        s01_ensure_workspace.run(ws)


def test_s01_raises_when_benchmark_intent_missing(tmp_path):
    """s01 raises FileNotFoundError when benchmark_intent.md is absent."""
    from sobench.steps import s01_ensure_workspace
    ws = make_workspace(tmp_path, with_intent=False)
    with pytest.raises(FileNotFoundError, match="benchmark_intent.md"):
        s01_ensure_workspace.run(ws)
