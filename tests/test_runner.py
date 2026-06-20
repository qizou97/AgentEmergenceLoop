"""
test_runner.py — BenchRecord construction from driver output (spec §9–§10).

build_record is the deterministic core of the runner: given a driver's output
JSON + the real ground truth, it validates (via checker), aligns by cell_id join,
computes metrics, and produces a BenchRecord. The live subprocess path (a real
driver in a conda env) is exercised only by the opt-in integration test.

Ground truth derives from the real MERFISH_0.04.h5ad. No mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sobench.runner import build_record, run

REAL_H5AD = (
    Path(__file__).parents[1]
    / "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
)

IDENT = dict(
    method="STAGATE_pyG",
    dataset="MERFISH",
    case="MERFISH_0.04",
    task="spatial_domain_identification",
    project_id="spatial_domain_identification_20260620",
    env_name="sobench_STAGATE_pyG",
)


def _ground_truth() -> dict[str, str]:
    import anndata as ad

    adata = ad.read_h5ad(REAL_H5AD)
    return dict(zip(adata.obs_names, adata.obs["ground_truth"].astype(str).tolist()))


def _write_output(tmp_path: Path, cell_ids, labels, status="success") -> Path:
    p = tmp_path / "result.json"
    p.write_text(json.dumps({"cell_ids": list(cell_ids), "labels": list(labels),
                             "status": status, "metadata": {}}))
    return p


def test_success_record_has_real_metrics(tmp_path):
    true = _ground_truth()
    # A perfect predictor: integer-encode the true labels (real cluster labels).
    order = {lbl: i for i, lbl in enumerate(sorted(set(true.values())))}
    ids = list(true)
    out = _write_output(tmp_path, ids, [order[true[i]] for i in ids])

    rec = build_record(output_path=out, ground_truth=true, metrics=["ARI", "NMI"],
                        returncode=0, **IDENT)

    assert rec.status == "success"
    assert rec.metrics.ARI == pytest.approx(1.0)
    assert rec.metrics.NMI == pytest.approx(1.0)
    assert rec.record_id == "STAGATE_pyG__MERFISH__MERFISH_0.04"
    assert rec.failure_detail is None


def test_id_mismatch_is_invalid_output(tmp_path):
    true = _ground_truth()
    ids = list(true)[:-1]  # drop one cell -> check 7 fails
    out = _write_output(tmp_path, ids, [0] * len(ids))

    rec = build_record(output_path=out, ground_truth=true, metrics=["ARI", "NMI"],
                       returncode=0, **IDENT)

    assert rec.status == "invalid_output"
    assert rec.metrics.ARI is None and rec.metrics.NMI is None
    assert rec.failure_detail and "check 7" in rec.failure_detail


def test_nonzero_returncode_is_failed(tmp_path):
    true = _ground_truth()
    out = tmp_path / "missing.json"  # driver crashed, wrote nothing
    rec = build_record(output_path=out, ground_truth=true, metrics=["ARI"],
                       returncode=1, stderr="Traceback: boom", **IDENT)

    assert rec.status == "failed"
    assert rec.metrics.ARI is None
    assert "boom" in rec.failure_detail


def test_duplicate_ids_is_invalid_output(tmp_path):
    true = _ground_truth()
    ids = list(true)
    ids[1] = ids[0]  # duplicate id, correct length
    out = _write_output(tmp_path, ids, [0] * len(ids))
    rec = build_record(output_path=out, ground_truth=true, metrics=["ARI"],
                       returncode=0, **IDENT)
    assert rec.status == "invalid_output"
    assert rec.metrics.ARI is None


def test_mixed_type_cell_ids_is_invalid_output_not_crash(tmp_path):
    """A driver emitting heterogeneous cell_ids must yield invalid_output, never crash."""
    true = _ground_truth()
    out = _write_output(tmp_path, ["spot1", 2, "spot3"], [0, 1, 2])
    rec = build_record(output_path=out, ground_truth=true, metrics=["ARI"],
                       returncode=0, **IDENT)
    assert rec.status == "invalid_output"
    assert rec.metrics.ARI is None


def test_run_errors_clearly_when_contracts_absent(tmp_path):
    """Spec §9: runner exits with a clear error before touching data."""
    with pytest.raises(FileNotFoundError) as exc:
        run(tmp_path / "empty_project")
    assert "contract" in str(exc.value).lower()
