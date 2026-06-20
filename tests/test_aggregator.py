"""
test_aggregator.py — BenchRecord JSONs -> results.csv (spec §4.4).

Records carry real task identifiers (STAGATE_pyG / MENDER, MERFISH cases). The
aggregator never invents data; it flattens written BenchRecords. No mocks.
"""

from __future__ import annotations

import csv

from sobench.aggregator import EXPECTED_COLUMNS, aggregate
from sobench.atomicio import write_json_atomic
from sobench.contracts.bench_record import BenchRecord


def _record(method, case, *, status, ari, nmi, **over) -> dict:
    base = {
        "record_id": f"{method}__MERFISH__{case}",
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "method": method,
        "dataset": "MERFISH",
        "case": case,
        "metrics": {"ARI": ari, "NMI": nmi},
        "status": status,
        "skip_reason": None,
        "failure_detail": None,
        "duration_seconds": 12.0,
        "driver_repair_count": 0,
        "env_name": f"sobench_{method}",
        "created_at": "2026-06-20T14:30:00Z",
    }
    base.update(over)
    return BenchRecord.model_validate(base).model_dump(mode="json")


def _seed_results(project_dir):
    results = project_dir / "results"
    write_json_atomic(
        results / "STAGATE_pyG_MERFISH_0.04.json",
        _record("STAGATE_pyG", "MERFISH_0.04", status="success", ari=0.71, nmi=0.83),
    )
    write_json_atomic(
        results / "MENDER_MERFISH_0.09.json",
        _record(
            "MENDER", "MERFISH_0.09", status="invalid_output", ari=None, nmi=None,
            failure_detail="cell_ids mismatch: 2 missing",
        ),
    )
    return results


def test_aggregate_writes_results_csv(tmp_path):
    proj = tmp_path / "spatial_domain_identification"
    _seed_results(proj)

    out = aggregate(proj)
    assert out == proj / "results" / "results.csv"
    assert out.exists()


def test_results_csv_has_fixed_column_order(tmp_path):
    proj = tmp_path / "p"
    _seed_results(proj)
    out = aggregate(proj)

    with out.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == EXPECTED_COLUMNS


def test_success_row_has_float_metrics(tmp_path):
    proj = tmp_path / "p"
    _seed_results(proj)
    aggregate(proj)

    rows = _read_rows(proj / "results" / "results.csv")
    succ = next(r for r in rows if r["method"] == "STAGATE_pyG")
    assert succ["status"] == "success"
    assert float(succ["ARI"]) == 0.71
    assert float(succ["NMI"]) == 0.83


def test_null_metric_is_empty_cell_not_dropped(tmp_path):
    proj = tmp_path / "p"
    _seed_results(proj)
    aggregate(proj)

    rows = _read_rows(proj / "results" / "results.csv")
    bad = next(r for r in rows if r["method"] == "MENDER")
    assert bad["status"] == "invalid_output"
    assert bad["ARI"] == ""  # null metric -> empty cell, column NOT shifted
    assert bad["NMI"] == ""
    assert bad["failure_detail"] == "cell_ids mismatch: 2 missing"


def test_row_count_matches_record_count(tmp_path):
    proj = tmp_path / "p"
    _seed_results(proj)
    aggregate(proj)
    rows = _read_rows(proj / "results" / "results.csv")
    assert len(rows) == 2


def _read_rows(csv_path):
    with csv_path.open(newline="") as fh:
        return list(csv.DictReader(fh))
