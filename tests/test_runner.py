"""
tests/test_runner.py — Runner tests.

Real task identity (per testing policy):
  task   = spatial_domain_identification
  method = STAGATE
  case   = DLPFC_151673

Two test groups:

1. Static structure (no I/O, fast): asserts runner.STEPS names + order and
   runner.SKIP_WHEN_BLOCKED membership — reads the real runner config.

2. Real blocked-cycle behavior (LLM required): builds a real-task workspace
   under tmp_path with a provenance-correct benchmark_intent.md pointing at
   the REAL paper PDF and REAL repo dir.  Runs the full pipeline.  Because the
   DLPFC 151673 .h5ad is genuinely absent, s09 writes blocked:true and the
   runner skips s10/s11/s12.  Asserts the exact executed list, artifact
   presence/absence, and structural_check.passed.

   Gate: requires OPENAI_API_KEY (present this session — must run, not skip).

   Note on the "not-blocked" case: it cannot be produced here because the real
   benchmark data (.h5ad) is absent.  Coverage of the unblocked path is
   structural (test 1 shows s10/s11/s12 are not in SKIP_WHEN_BLOCKED) and the
   real run shows s01–s09 + s13 + s14 all execute as expected.
"""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures and constants
# ---------------------------------------------------------------------------

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"

DATA_ROOT = Path(__file__).parent.parent / "data" / "spatial_domain_identification_task"
PAPER_PATH = DATA_ROOT / "papers" / "STAGATE.pdf"
REPO_PATH = DATA_ROOT / "codes" / "STAGATE"

REAL_API_KEY_PRESENT = bool(os.environ.get("OPENAI_API_KEY"))

# The 14 step names in exact s01→s14 order
EXPECTED_STEP_NAMES = [
    "s01_ensure_workspace",
    "s02_parse_intent",
    "s03_extract_paper_evidence",
    "s04_inspect_repo_evidence",
    "s05_build_data_manifest",
    "s06_draft_task_spec",
    "s07_draft_evaluation_contract",
    "s08_draft_risk_audit",
    "s09_execute_or_block",
    "s10_record_raw_observations",
    "s11_audit_result_validity",
    "s12_write_interpretation",
    "s13_write_experience_record",
    "s14_structural_check",
]

EXPECTED_SKIP_SET = {
    "s10_record_raw_observations",
    "s11_audit_result_validity",
    "s12_write_interpretation",
}

# Steps expected in the executed list after a blocked run (s01–s09 + s13 + s14)
EXPECTED_BLOCKED_EXECUTED = [
    "s01_ensure_workspace",
    "s02_parse_intent",
    "s03_extract_paper_evidence",
    "s04_inspect_repo_evidence",
    "s05_build_data_manifest",
    "s06_draft_task_spec",
    "s07_draft_evaluation_contract",
    "s08_draft_risk_audit",
    "s09_execute_or_block",
    "s13_write_experience_record",
    "s14_structural_check",
]


# ---------------------------------------------------------------------------
# 1. Static structure tests (no I/O, always run)
# ---------------------------------------------------------------------------

def test_skip_when_blocked_set():
    """SKIP_WHEN_BLOCKED matches the exact spec-prescribed set."""
    from sobench import runner
    assert runner.SKIP_WHEN_BLOCKED == EXPECTED_SKIP_SET


def test_steps_names_order():
    """STEPS contains exactly 14 steps in s01→s14 order."""
    from sobench import runner
    names = [name for name, _ in runner.STEPS]
    assert names == EXPECTED_STEP_NAMES, (
        f"STEPS names/order mismatch.\nExpected: {EXPECTED_STEP_NAMES}\nGot:      {names}"
    )


def test_steps_callables_are_callable():
    """Every run callable in STEPS is actually callable."""
    from sobench import runner
    for name, fn in runner.STEPS:
        assert callable(fn), f"STEPS entry '{name}' run callable is not callable"


# ---------------------------------------------------------------------------
# 2. Real blocked-cycle behavior (LLM required; OPENAI_API_KEY must be present)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_API_KEY_PRESENT,
    reason="OPENAI_API_KEY absent — real pipeline cannot run"
)
def test_real_blocked_pipeline(tmp_path):
    """
    Full pipeline against the real task with DLPFC data absent.

    Provenance:
      - benchmark_intent.md is a real-task-derived fixture pointing to the
        real STAGATE paper PDF at data/spatial_domain_identification_task/papers/STAGATE.pdf
        and the real repo at data/spatial_domain_identification_task/codes/STAGATE.
      - DLPFC 151673 .h5ad is genuinely absent locally → s09 blocks.

    Asserts:
      - workspace.blocked is True after run
      - blocker.json has blocked:true on disk
      - executed list equals EXPECTED_BLOCKED_EXECUTED (s10/s11/s12 absent)
      - s10/s11/s12 artifact files do NOT exist on disk
      - structural_check.json exists with passed == True
      - experience_record.json exists with status == "hypothesis"
    """
    assert PAPER_PATH.exists(), f"Real paper not found: {PAPER_PATH}"
    assert REPO_PATH.exists(), f"Real repo not found: {REPO_PATH}"

    from sobench.workspace import Workspace
    from sobench import runner

    # Build workspace with real-task-derived benchmark_intent.md
    ws = Workspace(task=TASK, method=METHOD, case=CASE, root=str(tmp_path))
    ws.dir.mkdir(parents=True, exist_ok=True)

    intent_content = f"""\
## Task
{TASK}

## Method
{METHOD}

## Case
{CASE}

## Paper
path: {PAPER_PATH}
notes: Section 4.1 describes DLPFC evaluation. ARI mentioned as primary metric.

## Repository
path: {REPO_PATH}
notes: Entry point unclear. Tutorial notebook exists.

## Data
notes: DLPFC slice 151673 required. File location unknown locally.

## What to reconstruct
Reproduce the spatial domain identification result on DLPFC 151673 as reported
in the paper, using ARI as the primary metric if evidence supports it.

## Human observations
(fill in after run, or add any prior knowledge to guide reconstruction)
"""
    (ws.dir / "benchmark_intent.md").write_text(intent_content, encoding="utf-8")

    # Run the full real pipeline
    executed = runner.run(ws)

    # --- workspace.blocked must be True ---
    assert ws.blocked is True, "workspace.blocked should be True after s09 writes blocked:true"

    # --- blocker.json must have blocked:true on disk ---
    blocker_path = ws.artifact_path("blocker")
    assert blocker_path.exists(), "blocker.json not written"
    blocker_data = json.loads(blocker_path.read_text(encoding="utf-8"))
    assert blocker_data["blocked"] is True, f"blocker.json has blocked:{blocker_data['blocked']!r}"

    # --- executed list: s10/s11/s12 absent; s01–s09 + s13 + s14 present in order ---
    assert executed == EXPECTED_BLOCKED_EXECUTED, (
        f"Executed steps mismatch.\nExpected: {EXPECTED_BLOCKED_EXECUTED}\nGot:      {executed}"
    )

    # --- s10/s11/s12 artifact files must NOT exist on disk ---
    for artifact_name in ("raw_observations", "result_validity_audit", "interpretation"):
        artifact_path = ws.artifact_path(artifact_name)
        assert not artifact_path.exists(), (
            f"{artifact_name}.json should NOT exist when blocked, but found at {artifact_path}"
        )

    # --- structural_check.json must exist with passed == True ---
    sc_path = ws.artifact_path("structural_check")
    assert sc_path.exists(), "structural_check.json not written"
    sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
    assert sc_data["passed"] is True, (
        f"structural_check.passed should be True (blocked cycle is structurally complete). "
        f"missing_unacknowledged={sc_data.get('missing_unacknowledged')}"
    )

    # --- experience_record.json must exist with status == "hypothesis" ---
    exp_path = ws.artifact_path("experience_record")
    assert exp_path.exists(), "experience_record.json not written"
    exp_data = json.loads(exp_path.read_text(encoding="utf-8"))
    assert exp_data["status"] == "hypothesis", (
        f"experience_record.status should be 'hypothesis', got {exp_data.get('status')!r}"
    )
