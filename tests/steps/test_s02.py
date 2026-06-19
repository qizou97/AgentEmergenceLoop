"""
Tests for s02_parse_intent.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673
Derived from data/spatial_domain_identification_task/ — real paths used throughout.

LLM tests use the real LLM (deepseek-v4-pro). Skipped with explicit reason if
OPENAI_API_KEY is absent.
"""

import os
import json
import pytest
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import ParsedIntent


REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# Real-task benchmark_intent.md derived from data/spatial_domain_identification_task/
REAL_BENCHMARK_INTENT = """\
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
Real task derived fixture for s02 test. Provenance: data/spatial_domain_identification_task/
"""

# Intentionally stripped of Task and Method — blocker case
INTENT_NO_TASK_METHOD = """\
## Case
DLPFC_151673

## Paper
path: data/spatial_domain_identification_task/papers/STAGATE.pdf
notes: Some paper notes.

## Repository
path: data/spatial_domain_identification_task/codes/STAGATE
notes: Some repo notes.

## Data
notes: DLPFC slice 151673 required.

## What to reconstruct
Unknown — task and method sections deliberately omitted for blocker test.

## Human observations
Blocker test: Task and Method sections removed.
"""


def make_workspace(tmp_path: Path, intent_text: str) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    (ws.dir / "benchmark_intent.md").write_text(intent_text)
    return ws


llm_required = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — LLM tests skipped",
)


@llm_required
def test_s02_happy_path(tmp_path):
    """
    s02 parses the real benchmark_intent.md and writes parsed_intent.json.
    Asserts: artifact written, task contains 'spatial', method == 'STAGATE'.
    """
    from sobench.steps import s02_parse_intent

    ws = make_workspace(tmp_path, REAL_BENCHMARK_INTENT)
    s02_parse_intent.run(ws)

    artifact_path = ws.artifact_path("parsed_intent")
    assert artifact_path.exists(), "parsed_intent.json was not written"

    pi = ws.read_artifact("parsed_intent", ParsedIntent)
    assert "spatial" in pi.task.lower(), f"Expected 'spatial' in task, got: {pi.task!r}"
    assert pi.method.upper() == "STAGATE", f"Expected method STAGATE, got: {pi.method!r}"
    assert pi.case, "case field is empty"
    assert pi.paper_path, "paper_path is empty"
    assert pi.repo_path, "repo_path is empty"

    # No blocker should be set on happy path
    assert not ws.blocked, "Workspace should not be blocked on happy path"


@llm_required
def test_s02_sets_blocker_when_task_method_missing(tmp_path):
    """
    When Task and Method sections are absent from benchmark_intent.md,
    s02 must write blocker.json with blocked: true.
    parsed_intent.json should still be written (scratchpad).
    """
    from sobench.steps import s02_parse_intent
    from sobench.models import Blocker

    ws = make_workspace(tmp_path, INTENT_NO_TASK_METHOD)
    s02_parse_intent.run(ws)

    # parsed_intent.json should still be written
    assert ws.artifact_path("parsed_intent").exists(), "parsed_intent.json was not written"

    # Blocker must be set
    assert ws.blocked, "Workspace should be blocked when task/method cannot be parsed"

    blocker = ws.read_blocker()
    assert blocker is not None
    assert blocker.blocked is True
    assert blocker.raised_by_step is not None
    assert blocker.reason is not None
