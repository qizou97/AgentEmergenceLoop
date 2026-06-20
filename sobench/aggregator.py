"""
sobench/aggregator.py — flatten BenchRecord JSONs into results.csv (spec §3/§4.4).

Reads every BenchRecord JSON under <project_dir>/results/ and writes results.csv
with a FIXED column order. Metrics are flattened to top-level ARI/NMI columns; a
null metric is an empty cell, never a dropped or shifted column. Rows are sorted
by record_id for deterministic output.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from sobench.contracts.bench_record import BenchRecord

# Fixed column order (spec §4.4: "Column order is fixed"). Metrics flattened out
# of SpatialMetrics into ARI / NMI.
EXPECTED_COLUMNS = [
    "record_id",
    "project_id",
    "task",
    "method",
    "dataset",
    "case",
    "status",
    "ARI",
    "NMI",
    "skip_reason",
    "failure_detail",
    "duration_seconds",
    "driver_repair_count",
    "env_name",
    "created_at",
]


def _row(rec: BenchRecord) -> dict:
    d = rec.model_dump(mode="json")
    metrics = d.pop("metrics")
    d["ARI"] = metrics.get("ARI")
    d["NMI"] = metrics.get("NMI")
    # None -> "" so a missing metric is an empty cell, not the literal "None".
    return {col: ("" if d.get(col) is None else d.get(col)) for col in EXPECTED_COLUMNS}


def to_rows(records: list[BenchRecord]) -> list[dict]:
    return [_row(r) for r in sorted(records, key=lambda r: r.record_id)]


def aggregate(project_dir: str | Path) -> Path:
    """Read all BenchRecord JSONs under results/ and write results.csv. Returns its path."""
    project_dir = Path(project_dir)
    results_dir = project_dir / "results"

    records: list[BenchRecord] = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name == "results.csv":  # defensive; glob is *.json
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        records.append(BenchRecord.model_validate(raw))

    out = results_dir / "results.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPECTED_COLUMNS)
        writer.writeheader()
        for row in to_rows(records):
            writer.writerow(row)
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.aggregator --project-dir <p>."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.aggregator")
    ap.add_argument("--project-dir", required=True)
    args = ap.parse_args(argv)
    out = aggregate(args.project_dir)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
