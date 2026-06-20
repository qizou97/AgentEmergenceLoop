"""
test_contracts.py — BenchRecord schema + freeze flow against the real task.

Real task: data/spatial_domain_identification_task/ (MERFISH spatial domain
identification). All identifiers and h5ad inspections derive from that task —
no mocks, no synthetic data (docs/TESTING_POLICY.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from sobench.contracts.bench_record import BenchRecord, SpatialMetrics
from sobench.contracts.freeze import freeze


# Real-task identifiers (method names match data/.../codes/, dataset is MERFISH).
RECORD_ID = "STAGATE_pyG__MERFISH__MERFISH_0.04"

# Real h5ad: ground-truth column is 'ground_truth', spatial key is 'spatial'
# (verified by inspection — the spec's §4.2 "Cell_class" example is illustrative).
REAL_H5AD = "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
REAL_GROUND_TRUTH_COL = "ground_truth"
REAL_SPATIAL_KEY = "spatial"


def _valid_record_dict() -> dict:
    return {
        "record_id": RECORD_ID,
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "method": "STAGATE_pyG",
        "dataset": "MERFISH",
        "case": "MERFISH_0.04",
        "metrics": {"ARI": 0.71, "NMI": 0.83},
        "status": "success",
        "skip_reason": None,
        "failure_detail": None,
        "duration_seconds": 42.5,
        "driver_repair_count": 1,
        "env_name": "sobench_STAGATE_pyG",
        "created_at": "2026-06-20T14:30:00Z",
    }


def test_bench_record_round_trip():
    rec = BenchRecord.model_validate(_valid_record_dict())
    again = BenchRecord.model_validate(rec.model_dump(mode="json"))
    assert again == rec
    assert again.metrics.ARI == 0.71
    assert again.record_id == RECORD_ID


def test_bench_record_rejects_extra_field():
    bad = _valid_record_dict()
    bad["unexpected"] = "x"
    with pytest.raises(ValidationError):
        BenchRecord.model_validate(bad)


def test_spatial_metrics_rejects_extra_field():
    with pytest.raises(ValidationError):
        SpatialMetrics.model_validate({"ARI": 0.1, "NMI": 0.2, "FOO": 0.3})


def test_bench_record_allows_null_metrics():
    """A failed/invalid run carries null metrics, not a missing column."""
    d = _valid_record_dict()
    d["metrics"] = {"ARI": None, "NMI": None}
    d["status"] = "invalid_output"
    d["failure_detail"] = "cell_ids mismatch: 3 missing"
    rec = BenchRecord.model_validate(d)
    assert rec.metrics.ARI is None
    assert rec.metrics.NMI is None
    assert rec.status == "invalid_output"


def test_spatial_metrics_defaults_to_null():
    m = SpatialMetrics()
    assert m.ARI is None and m.NMI is None


# ---------------------------------------------------------------------------
# freeze flow (spec §5) — validates agent drafts against the REAL h5ad
# ---------------------------------------------------------------------------

def _write_drafts(project_dir: Path, *, ground_truth_column=REAL_GROUND_TRUTH_COL,
                  spatial_key=REAL_SPATIAL_KEY, metrics=("ARI", "NMI"),
                  data_case="MERFISH_0.04"):
    """Write the three draft contracts for a single real MERFISH case."""
    project_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "dataset": "MERFISH",
        "cases": ["MERFISH_0.04"],
        "methods": [
            {
                "name": "STAGATE_pyG",
                "repo_path": "data/spatial_domain_identification_task/codes/STAGATE_pyG",
                "driver_path": "methods/STAGATE_pyG/driver.py",
                "env_file": "methods/STAGATE_pyG/env.yml",
                "env_record": "methods/STAGATE_pyG/env_record.json",
            }
        ],
    }
    data = {
        "cases": {
            data_case: {
                "h5ad_path": REAL_H5AD,
                "obs_columns": ["cell_class", "ground_truth"],
                "spatial_key": spatial_key,
                "ground_truth_column": ground_truth_column,
            }
        }
    }
    metric = {
        "metrics": list(metrics),
        "implementation": "sobench.metrics",
        "label_type": "integer_cluster_labels",
    }
    (project_dir / "task_contract_draft.json").write_text(json.dumps(task))
    (project_dir / "data_contract_draft.json").write_text(json.dumps(data))
    (project_dir / "metric_contract_draft.json").write_text(json.dumps(metric))


def test_freeze_pass_writes_frozen_contracts(tmp_path):
    proj = tmp_path / "spatial_domain_identification"
    _write_drafts(proj)

    report = freeze(proj)

    assert report["passed"] is True
    for name in ("task_contract.json", "data_contract.json", "metric_contract.json"):
        assert (proj / name).exists(), f"frozen {name} not written"
    fr = json.loads((proj / "freeze_report.json").read_text())
    assert fr["passed"] is True
    assert "timestamp" in fr
    assert set(fr["contract_hashes"]) == {"task_contract", "data_contract", "metric_contract"}
    assert all(h.startswith("sha256:") for h in fr["contract_hashes"].values())
    # drafts preserved
    assert (proj / "task_contract_draft.json").exists()


def test_freeze_fail_bad_ground_truth_column(tmp_path):
    """The spec's stale 'Cell_class' is absent from the real obs — must fail."""
    proj = tmp_path / "p"
    _write_drafts(proj, ground_truth_column="Cell_class")

    report = freeze(proj)

    assert report["passed"] is False
    assert any("Cell_class" in e or "ground_truth_column" in e for e in report["errors"])
    # no frozen files written on failure
    assert not (proj / "task_contract.json").exists()
    assert not (proj / "data_contract.json").exists()
    # report still written
    assert (proj / "freeze_report.json").exists()
    # drafts preserved
    assert (proj / "data_contract_draft.json").exists()


def test_freeze_fail_bad_spatial_key(tmp_path):
    proj = tmp_path / "p"
    _write_drafts(proj, spatial_key="Spatial")  # real key is lowercase 'spatial'
    report = freeze(proj)
    assert report["passed"] is False
    assert any("spatial_key" in e or "Spatial" in e for e in report["errors"])
    assert not (proj / "data_contract.json").exists()


def test_freeze_fail_metric_not_subset(tmp_path):
    proj = tmp_path / "p"
    _write_drafts(proj, metrics=("ARI", "FOO"))
    report = freeze(proj)
    assert report["passed"] is False
    assert any("FOO" in e or "metric" in e.lower() for e in report["errors"])


def test_freeze_fail_data_case_not_in_task(tmp_path):
    proj = tmp_path / "p"
    _write_drafts(proj, data_case="MERFISH_0.99")  # not in task cases
    report = freeze(proj)
    assert report["passed"] is False
    assert any("MERFISH_0.99" in e or "case" in e.lower() for e in report["errors"])


def test_freeze_contract_hash_matches_frozen_bytes(tmp_path):
    """contract_hashes must be the sha256 of the canonical frozen JSON bytes."""
    import hashlib

    proj = tmp_path / "p"
    _write_drafts(proj)
    report = freeze(proj)
    assert report["passed"] is True

    frozen = json.loads((proj / "task_contract.json").read_text())
    canonical = json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()
    expected = "sha256:" + hashlib.sha256(canonical).hexdigest()
    fr = json.loads((proj / "freeze_report.json").read_text())
    assert fr["contract_hashes"]["task_contract"] == expected
