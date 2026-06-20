"""
test_integration.py — full agent-construction loop (spec §13 integration test).

SKIP unless ALL of:
  - conda/mamba on PATH,
  - the 3 method repos present under data/,
  - opt-in: env var SOBENCH_RUN_INTEGRATION=1 (this test builds real conda envs
    and runs torch/scanpy/tensorflow drivers — minutes, network, disk).

When it runs it asserts the spec §13 end-state: a 15-row results.csv (3 methods ×
5 MERFISH cases), concrete statuses, ≥1 real ARI/NMI per method, all BenchRecords
present, experience entries in all three indexes, freeze passed. The construction
artifacts (contracts, drivers, env.yml, data_adapter.py) are produced by the
external coding agent operating tool/sobench.py — they are NOT part of this
deterministic substrate, so this test only runs once those artifacts exist in the
project under test (pointed to by SOBENCH_INTEGRATION_PROJECT, default
benchmark_projects/spatial_domain_identification).
"""

from __future__ import annotations

import csv
import os
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[1]
DATA_TASK = REPO_ROOT / "data" / "spatial_domain_identification_task"
METHODS = ["STAGATE_pyG", "MENDER", "SpaGCN"]
CASES = ["MERFISH_0.04", "MERFISH_0.09", "MERFISH_0.14", "MERFISH_0.19", "MERFISH_0.24"]


def _skip_reason() -> str | None:
    if not (shutil.which("mamba") or shutil.which("conda")):
        return "neither mamba nor conda on PATH"
    missing = [m for m in METHODS if not (DATA_TASK / "codes" / m).is_dir()]
    if missing:
        return f"method repos absent from data/: {missing}"
    if os.environ.get("SOBENCH_RUN_INTEGRATION") != "1":
        return "opt-in: set SOBENCH_RUN_INTEGRATION=1 to run the full conda+driver loop"
    return None


pytestmark = pytest.mark.skipif(_skip_reason() is not None, reason=_skip_reason() or "")


def _project_dir() -> Path:
    return Path(os.environ.get(
        "SOBENCH_INTEGRATION_PROJECT",
        str(REPO_ROOT / "benchmark_projects" / "spatial_domain_identification"),
    ))


def test_full_benchmark_matrix_end_state():
    proj = _project_dir()
    assert proj.is_dir(), (
        f"project {proj} not constructed — the agent must run "
        "construct/validate/env/smoke/execute first"
    )

    # freeze passed
    import json

    freeze_report = json.loads((proj / "freeze_report.json").read_text())
    assert freeze_report["passed"] is True

    # 15-row results.csv
    csv_path = proj / "results" / "results.csv"
    assert csv_path.exists(), "results.csv missing — run aggregate"
    with csv_path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(METHODS) * len(CASES) == 15

    # every row has a concrete status; non-success rows carry a reason
    for r in rows:
        assert r["status"], f"row {r['record_id']} has empty status"
        if r["status"] != "success":
            assert r["skip_reason"] or r["failure_detail"], (
                f"non-success row {r['record_id']} has no reason"
            )

    # at least one real (non-null) ARI+NMI success per method, and the BenchRecord exists
    for method in METHODS:
        succ = [r for r in rows if r["method"] == method and r["status"] == "success"]
        assert succ, f"no successful row for method {method}"
        assert any(r["ARI"] and r["NMI"] for r in succ), f"no real ARI/NMI for {method}"

    for r in rows:
        method, case = r["method"], r["case"]
        assert (proj / "results" / f"{method}_{case}.json").exists()

    # experience store populated in all three indexes
    store = REPO_ROOT / "experience_store"
    assert any((store / "methods").glob("*.json"))
    assert any((store / "datasets").glob("*.json"))
    assert any((store / "metrics").glob("*.json"))
