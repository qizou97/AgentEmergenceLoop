"""
tests/test_integration.py — End-to-end integration smoke test.

Drives the full 14-step pipeline from the provenance-headed fixture file
tests/fixtures/intent_stagate_dlpfc.md and asserts the produced workspace
is an auditable benchmark package.

Real task identity (per testing policy):
  task   = spatial_domain_identification
  method = STAGATE
  case   = DLPFC_151673

Provenance of the fixture:
  - Derived from the real task under data/spatial_domain_identification_task/
  - Points at the real paper: data/spatial_domain_identification_task/papers/STAGATE.pdf
  - Points at the real repo:  data/spatial_domain_identification_task/codes/STAGATE
  - DLPFC 151673 .h5ad is genuinely absent locally → pipeline produces a
    real blocked cycle with structural_check.passed == True

Skip conditions (with explicit reason):
  - OPENAI_API_KEY absent (real LLM cannot run)
  - Real paper or real repo dir absent (fixture would be meaningless)

This is one real full-pipeline run (~minutes of real LLM).
No mocks, no monkeypatching, no fake LLM.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants / gate
# ---------------------------------------------------------------------------

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"

REPO_ROOT = Path(__file__).parent.parent
DATA_ROOT = REPO_ROOT / "data" / "spatial_domain_identification_task"
PAPER_PATH = DATA_ROOT / "papers" / "STAGATE.pdf"
REPO_PATH = DATA_ROOT / "codes" / "STAGATE"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "intent_stagate_dlpfc.md"

REAL_API_KEY_PRESENT = bool(os.environ.get("OPENAI_API_KEY"))
REAL_DATA_PRESENT = PAPER_PATH.exists() and REPO_PATH.exists()

# Steps expected to execute in a blocked run (s10/s11/s12 are skipped)
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
# Integration test
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_API_KEY_PRESENT,
    reason="OPENAI_API_KEY absent — real LLM pipeline cannot run",
)
@pytest.mark.skipif(
    not REAL_DATA_PRESENT,
    reason=(
        "Required real data absent: "
        f"paper={PAPER_PATH} exists={PAPER_PATH.exists()}, "
        f"repo={REPO_PATH} exists={REPO_PATH.exists()}"
    ),
)
def test_integration_auditable_package(tmp_path):
    """
    Full end-to-end pipeline from the provenance-headed fixture file.

    Provenance:
      - Reads tests/fixtures/intent_stagate_dlpfc.md (derived from the real task).
      - Paper path and repo path point at the real files under data/.
      - DLPFC 151673 .h5ad is genuinely absent → s09 writes blocked:true.

    Asserts the produced workspace is an AUDITABLE BENCHMARK PACKAGE:
      - structural_check.json  : exists, passed == True
      - experience_record.json : exists, status == "hypothesis", evidence non-empty
      - blocker.json           : exists, blocked == True, non-empty reason
      - execution_log.json     : exists, status == "not_attempted"
      - Auditable-package artifacts present: paper_evidence, repo_evidence,
        data_manifest, task_spec, evaluation_contract, risk_audit
      - data_manifest reflects the genuinely-absent .h5ad (at least one
        required entry has available: false)
      - s10/s11/s12 artifacts do NOT exist (excused by blocker)
    """
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"

    from sobench.workspace import Workspace
    from sobench import runner

    # --- Build workspace with fixture content ---
    ws = Workspace(task=TASK, method=METHOD, case=CASE, root=str(tmp_path))
    ws.dir.mkdir(parents=True, exist_ok=True)

    fixture_content = FIXTURE_PATH.read_text(encoding="utf-8")
    (ws.dir / "benchmark_intent.md").write_text(fixture_content, encoding="utf-8")

    # --- Run the full real pipeline ---
    executed = runner.run(ws)

    # --- workspace.blocked must be True (real DLPFC .h5ad absent) ---
    assert ws.blocked is True, (
        "workspace.blocked should be True after s09 detects genuinely-absent DLPFC data"
    )

    # --- blocker.json: exists, blocked:true, non-empty reason ---
    blocker_path = ws.artifact_path("blocker")
    assert blocker_path.exists(), "blocker.json not written"
    blocker_data = json.loads(blocker_path.read_text(encoding="utf-8"))
    assert blocker_data["blocked"] is True, (
        f"blocker.json has blocked:{blocker_data['blocked']!r} — expected True"
    )
    assert blocker_data.get("reason"), (
        "blocker.reason should be a non-empty string describing the missing benchmark data"
    )

    # --- execution_log.json: exists, status == "not_attempted" ---
    el_path = ws.artifact_path("execution_log")
    assert el_path.exists(), "execution_log.json not written"
    el_data = json.loads(el_path.read_text(encoding="utf-8"))
    assert el_data["status"] == "not_attempted", (
        f"execution_log.status should be 'not_attempted' when blocked; got {el_data.get('status')!r}"
    )

    # --- structural_check.json: exists, passed == True ---
    sc_path = ws.artifact_path("structural_check")
    assert sc_path.exists(), "structural_check.json not written"
    sc_data = json.loads(sc_path.read_text(encoding="utf-8"))
    assert sc_data["passed"] is True, (
        f"structural_check.passed should be True (real blocked cycle is structurally complete). "
        f"missing_unacknowledged={sc_data.get('missing_unacknowledged')}"
    )

    # --- experience_record.json: exists, status == "hypothesis", evidence non-empty ---
    exp_path = ws.artifact_path("experience_record")
    assert exp_path.exists(), "experience_record.json not written"
    exp_data = json.loads(exp_path.read_text(encoding="utf-8"))
    assert exp_data["status"] == "hypothesis", (
        f"experience_record.status should be 'hypothesis'; got {exp_data.get('status')!r}"
    )
    assert exp_data.get("evidence") and len(exp_data["evidence"]) > 0, (
        "experience_record.evidence should be a non-empty list with real artifact references"
    )

    # --- Auditable-package artifacts present ---
    auditable_artifacts = [
        "paper_evidence",
        "repo_evidence",
        "data_manifest",
        "task_spec",
        "evaluation_contract",
        "risk_audit",
    ]
    for name in auditable_artifacts:
        p = ws.artifact_path(name)
        assert p.exists(), f"{name}.json not found — auditable package incomplete"

    # --- data_manifest reflects genuinely-absent .h5ad: at least one available:false ---
    dm_data = json.loads(ws.artifact_path("data_manifest").read_text(encoding="utf-8"))
    required_items = dm_data.get("required", [])
    assert len(required_items) > 0, "data_manifest.required should list at least one data item"
    unavailable = [r for r in required_items if r.get("available") is False]
    assert len(unavailable) > 0, (
        "data_manifest.required should have at least one item with available:false "
        "(the genuinely-absent DLPFC .h5ad)"
    )

    # --- s10/s11/s12 artifacts must NOT exist (excused by the blocker) ---
    for artifact_name in ("raw_observations", "result_validity_audit", "interpretation"):
        p = ws.artifact_path(artifact_name)
        assert not p.exists(), (
            f"{artifact_name}.json should NOT exist when blocked; found at {p}"
        )

    # --- executed list: s10/s11/s12 absent ---
    assert executed == EXPECTED_BLOCKED_EXECUTED, (
        f"Executed steps mismatch.\nExpected: {EXPECTED_BLOCKED_EXECUTED}\nGot:      {executed}"
    )
