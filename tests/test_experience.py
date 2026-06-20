"""
test_experience.py — append-only experience store (spec §11).

Builds a realistic completed-run project (frozen contracts -> the REAL
MERFISH_0.04.h5ad, env/driver records, a BenchRecord) and checks the three
experience indexes. h5ad_fingerprint is read from the real file. No mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

from sobench.atomicio import write_json_atomic
from sobench.contracts.bench_record import BenchRecord
from sobench.experience import write_experience

REAL_H5AD_REL = "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
REAL_OBS_COLUMNS = ["cell_class", "neuron_class", "domain", "Region", "ground_truth"]


def _build_project(project_dir: Path, *, with_env: bool = True) -> None:
    """Write the frozen contracts + per-method run artifacts for one method×case."""
    project_dir.mkdir(parents=True, exist_ok=True)
    method = "STAGATE_pyG"
    case = "MERFISH_0.04"

    write_json_atomic(project_dir / "task_contract.json", {
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "dataset": "MERFISH",
        "cases": [case],
        "methods": [{
            "name": method,
            "repo_path": "data/spatial_domain_identification_task/codes/STAGATE_pyG",
            "driver_path": f"methods/{method}/driver.py",
            "env_file": f"methods/{method}/env.yml",
            "env_record": f"methods/{method}/env_record.json",
        }],
    })
    write_json_atomic(project_dir / "data_contract.json", {
        "cases": {case: {
            "h5ad_path": REAL_H5AD_REL,
            "obs_columns": ["cell_class", "ground_truth"],
            "spatial_key": "spatial",
            "ground_truth_column": "ground_truth",
        }},
    })
    write_json_atomic(project_dir / "metric_contract.json", {
        "metrics": ["ARI", "NMI"],
        "implementation": "sobench.metrics",
        "label_type": "integer_cluster_labels",
    })
    write_json_atomic(project_dir / "freeze_report.json", {"passed": True})

    mdir = project_dir / "methods" / method
    mdir.mkdir(parents=True, exist_ok=True)
    (mdir / "env.yml").write_text("name: sobench_STAGATE_pyG\ndependencies:\n  - python=3.9\n")
    (mdir / "driver.py").write_text("# driver for STAGATE_pyG\n")
    (project_dir / "data_adapter.py").write_text("# data adapter\n")
    write_json_atomic(mdir / "driver_record.json", {
        "method": method, "case": case,
        "attempts": [{"attempt": 1, "validation_failures": [], "status": "smoke_valid"}],
        "final_status": "smoke_valid", "repair_count": 0,
    })
    if with_env:
        write_json_atomic(mdir / "env_record.json", {
            "method": method, "env_name": "sobench_STAGATE_pyG",
            "interpreter_path": "/fake/envs/sobench_STAGATE_pyG/bin/python",
        })

    rec = BenchRecord.model_validate({
        "record_id": f"{method}__MERFISH__{case}",
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "method": method, "dataset": "MERFISH", "case": case,
        "metrics": {"ARI": 0.71, "NMI": 0.83},
        "status": "success", "skip_reason": None, "failure_detail": None,
        "duration_seconds": 42.0, "driver_repair_count": 0,
        "env_name": "sobench_STAGATE_pyG", "created_at": "2026-06-20T14:30:00Z",
    })
    write_json_atomic(project_dir / "results" / f"{method}_MERFISH_0.04.json",
                      rec.model_dump(mode="json"))


def test_writes_all_three_indexes(tmp_path):
    proj = tmp_path / "spatial_domain_identification"
    store = tmp_path / "experience_store"
    _build_project(proj)

    write_experience(proj, store)

    assert (store / "methods" / "STAGATE_pyG.json").exists()
    assert (store / "datasets" / "MERFISH.json").exists()
    assert (store / "metrics" / "ARI.json").exists()
    assert (store / "metrics" / "NMI.json").exists()


def test_entries_have_schema_version(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)

    for rel in ("methods/STAGATE_pyG.json", "datasets/MERFISH.json", "metrics/ARI.json"):
        arr = json.loads((store / rel).read_text())
        assert arr, f"{rel} empty"
        assert all(e["schema_version"] == "1" for e in arr)


def test_method_entry_independent_statuses(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)

    entry = json.loads((store / "methods" / "STAGATE_pyG.json").read_text())[0]
    assert entry["env_status"] == "env_created"
    assert entry["driver_status"] == "smoke_valid"
    assert entry["benchmark_status"] == "benchmark_executed"
    assert entry["partial"] is False
    assert entry["missing_artifacts"] == []


def test_dataset_fingerprint_from_real_h5ad(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)

    entry = json.loads((store / "datasets" / "MERFISH.json").read_text())[0]
    assert entry["h5ad_fingerprint"]["obs_columns"] == REAL_OBS_COLUMNS
    assert entry["h5ad_fingerprint"]["obsm_keys"] == ["spatial"]
    assert entry["h5ad_fingerprint"]["has_raw"] is False
    assert entry["h5ad_shape"][0] == 5488
    assert entry["ground_truth_column"] == "ground_truth"
    assert entry["spatial_key"] == "spatial"


def test_metric_entry_carries_real_value(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)

    ari = json.loads((store / "metrics" / "ARI.json").read_text())[0]
    assert ari["metric"] == "ARI"
    assert ari["value"] == 0.71
    assert ari["method"] == "STAGATE_pyG"
    assert ari["alignment"] == "by_cell_ids"
    assert ari["implementation"] == "sobench.metrics.compute"


def test_partial_when_env_record_absent(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj, with_env=False)  # env_record.json absent
    write_experience(proj, store)

    entry = json.loads((store / "methods" / "STAGATE_pyG.json").read_text())[0]
    assert entry["partial"] is True
    assert any("env_record" in m for m in entry["missing_artifacts"])
    assert entry["reason"]
    assert entry["env_status"] == "env_missing"


def test_newest_first_after_second_write(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)
    write_experience(proj, store)

    arr = json.loads((store / "methods" / "STAGATE_pyG.json").read_text())
    assert len(arr) == 2
    # newest-first: the entry written second has the higher sequence number
    assert arr[0]["entry_id"].endswith("-002")
    assert arr[1]["entry_id"].endswith("-001")


def test_no_leftover_tmp_files(tmp_path):
    proj = tmp_path / "p"
    store = tmp_path / "store"
    _build_project(proj)
    write_experience(proj, store)
    assert list(store.rglob("*.tmp")) == []
