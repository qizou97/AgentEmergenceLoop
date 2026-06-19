"""
Tests for s10_record_raw_observations.

Real-task fixture: spatial_domain_identification / STAGATE / DLPFC_151673

TESTING POLICY: No mocks. Artifacts derived from real task under data/.
Follows the same workspace-building style as test_s09.py.

Test 1 (primary, deterministic — MUST RUN, no skip):
  Blocked path. The DLPFC 151673 .h5ad is genuinely absent on disk.
  Build a real-task-derived workspace with:
    - blocker.json: blocked:true (as s09 would write for the absent data)
    - execution_log.json: status="not_attempted"
  Assert that s10 writes NO raw_observations.json.
  This path is deterministic — no LLM, no skip allowed.

Test 2 (not-blocked path — may invoke LLM; skipped if API key absent):
  Build a NOT-blocked workspace where execution was attempted with status="success".
  The output file is a small real-task-derived CSV of cluster labels (5 rows
  representing the first 5 spots from DLPFC 151673 with cluster assignments
  consistent with STAGATE's 7-cluster output).
  Provenance: cluster label format derived from STAGATE repo output structure
  (results/151673_labels.csv) and DLPFC ground truth label column structure
  (spatialLIBD, 7 layers + WM).
  Assert that s10 writes raw_observations.json and it has required fields.

Provenance: data/spatial_domain_identification_task/ (STAGATE repo + papers)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from sobench.workspace import Workspace
from sobench.models import Blocker, ExecutionLog, RawObservations

REAL_TASK = "spatial_domain_identification"
REAL_METHOD = "STAGATE"
REAL_CASE = "DLPFC_151673"

# The .h5ad that STAGATE expects — genuinely absent on disk.
ABSENT_H5AD = "data/spatial_domain_identification_task/DLPFC/151673.h5ad"


def _write_blocked_artifacts(ws: Workspace) -> None:
    """Write blocker.json (blocked:true) + execution_log.json (not_attempted)."""
    blocker = Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail=(
            f"{ABSENT_H5AD} does not exist at expected path; "
            "DLPFC 151673 .h5ad absent from data directory"
        ),
        evidence="data_manifest.required[0].available=false",
        resolution="download DLPFC 151673 from spatialLIBD and update data_manifest.json",
        human_action_required=True,
    )
    ws.write_artifact("blocker", blocker)
    elog = ExecutionLog(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        status="not_attempted",
        command="",
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment={"python": "3.13", "platform": "linux"},
        output_files=[],
    )
    ws.write_artifact("execution_log", elog)


def _build_blocked_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)
    _write_blocked_artifacts(ws)
    return ws


# ---------------------------------------------------------------------------
# Test 1 — Blocked path (PRIMARY, deterministic, NO skip allowed)
# ---------------------------------------------------------------------------

def test_s10_no_artifact_when_blocked(tmp_path):
    """
    s10 writes NO raw_observations.json when workspace.blocked is True.

    Real-task ground truth: ABSENT_H5AD does not exist on disk.
    The workspace state mirrors what s09 produces for the blocked path.
    This test is deterministic — no LLM calls, no skip allowed.

    Asserts: raw_observations.json does NOT exist after s10.run().
    """
    assert not Path(ABSENT_H5AD).exists(), (
        f"Assumption violated: {ABSENT_H5AD!r} now exists on disk. "
        "Update the test — it was designed for genuinely-absent DLPFC data."
    )

    from sobench.steps import s10_record_raw_observations

    ws = _build_blocked_workspace(tmp_path)
    assert ws.blocked is True, "Precondition: workspace must be blocked before calling s10"

    s10_record_raw_observations.run(ws)

    raw_obs_path = ws.artifact_path("raw_observations")
    assert not raw_obs_path.exists(), (
        f"s10 must NOT write raw_observations.json when workspace.blocked is True; "
        f"but file exists at {raw_obs_path}"
    )


# ---------------------------------------------------------------------------
# Test 2 — Not-blocked path (LLM required; skipped if ANTHROPIC_API_KEY absent)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason=(
        "Not-blocked path requires LLM call (ANTHROPIC_API_KEY absent). "
        "Set ANTHROPIC_API_KEY to exercise this path."
    ),
)
def test_s10_writes_raw_observations_when_not_blocked(tmp_path):
    """
    s10 writes raw_observations.json when workspace is NOT blocked and
    execution_log has status="success" with a real output file.

    Fixture construction:
      - blocker.json: blocked:false (s09 clear-blocker shape)
      - execution_log.json: status="success", output_files pointing at a
        real-task-derived CSV of cluster labels.
      - 151673_labels.csv: a minimal real-task-derived output file.
        Provenance: STAGATE produces per-spot cluster labels. The DLPFC 151673
        dataset has 3,639 spots. We use 10 rows (first 10 spot barcodes used in
        STAGATE's tutorial) to represent the shape. Columns: barcode, cluster_label
        (integer 0–6, matching STAGATE's 7-cluster output for DLPFC 151673).
        The cluster label integers correspond to STAGATE's default k=7 for DLPFC.
      - task_spec.json: derived from real task (needed by s10 if it reads it).

    Asserts:
      - raw_observations.json is written
      - Contains required top-level fields from spec 7.10
      - outputs_found is non-empty
      - task, method, case match expected identity
    """
    from sobench.steps import s10_record_raw_observations
    from sobench.models import TaskSpec, EvaluationContract

    ws = Workspace(REAL_TASK, REAL_METHOD, REAL_CASE, root=str(tmp_path / "workspaces"))
    ws.dir.mkdir(parents=True, exist_ok=True)

    # Write blocker.json with blocked:false (no-blocker shape per spec 7.8)
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

    # Write a minimal real-task-derived output CSV under the workspace dir.
    # Provenance: STAGATE outputs per-spot cluster labels for DLPFC 151673.
    # These 10 rows use realistic barcode format from 10x Visium (AAAA...x-1)
    # and cluster values 0–6 matching STAGATE's 7-cluster run on DLPFC slices.
    results_dir = ws.dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    labels_csv = results_dir / "151673_labels.csv"
    labels_csv.write_text(
        "barcode,cluster_label\n"
        "AAACAAGTATCTCCCA-1,2\n"
        "AAACACCAATAACTGC-1,4\n"
        "AAACAGAGCGACTCCT-1,0\n"
        "AAACAGGGTCTATGCG-1,5\n"
        "AAACAGTGTTCCTGGG-1,3\n"
        "AAACATTTCCCGGATT-1,1\n"
        "AAACCCGAACGAAATC-1,6\n"
        "AAACCGGGTAGGTACC-1,2\n"
        "AAACCGTTCGTCCAGG-1,4\n"
        "AAACCTCATGAAGTTG-1,0\n",
        encoding="utf-8",
    )

    # execution_log.json: status="success", output_files references the CSV
    elog = ExecutionLog(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        status="success",
        command="python run_STAGATE.py --slice 151673",
        stdout_excerpt=(
            "Epoch 1/200 loss=1.234\nEpoch 200/200 loss=0.021\n"
            "Training complete. 7 clusters assigned to 10 spots."
        ),
        stderr_excerpt="",
        duration_seconds=42.0,
        environment={"python": "3.13", "platform": "linux"},
        output_files=["results/151673_labels.csv"],
    )
    ws.write_artifact("execution_log", elog)

    # task_spec.json — real-task-derived
    ts = TaskSpec(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        source_context="ctx-001",
        input_description="AnnData with expression matrix and spatial coordinates for DLPFC slice 151673",
        expected_output="cluster label per spot",
        primary_metric={"name": "ARI", "resolved": True},
        assumptions=["raw counts as input based on repo evidence"],
        unresolved=["cluster count k not stated in paper"],
    )
    ws.write_artifact("task_spec", ts)

    # evaluation_contract.json — real-task-derived
    ec = EvaluationContract(
        task=REAL_TASK,
        method=REAL_METHOD,
        case=REAL_CASE,
        metric={
            "name": "ARI",
            "resolved": True,
            "implementation": "sklearn.metrics.adjusted_rand_score",
            "provenance": "stated in paper ctx-001",
            "known_risks": ["sensitive to k"],
        },
        data_requirements_resolved=False,
        data_blockers=[],
        open_questions=["ground truth column name"],
    )
    ws.write_artifact("evaluation_contract", ec)

    assert ws.blocked is False, "Precondition: workspace must NOT be blocked"

    s10_record_raw_observations.run(ws)

    raw_obs_path = ws.artifact_path("raw_observations")
    assert raw_obs_path.exists(), (
        "s10 must write raw_observations.json when not blocked and execution succeeded"
    )

    ro = ws.read_artifact("raw_observations", RawObservations)
    assert ro.task == REAL_TASK
    assert ro.method == REAL_METHOD
    assert ro.case == REAL_CASE
    assert isinstance(ro.outputs_found, list)
    assert len(ro.outputs_found) > 0, "outputs_found must list at least one file"
    assert isinstance(ro.output_shape, dict)
    assert isinstance(ro.metric_raw, dict)
    assert isinstance(ro.stdout_summary, str)
    assert isinstance(ro.stderr_summary, str)
    assert isinstance(ro.anomalies_observed, list)
