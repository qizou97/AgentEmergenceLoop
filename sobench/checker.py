"""
sobench/checker.py — the 7-check smoke output validator (spec §7).

Validates a driver's output JSON against the deterministic smoke h5ad's cell ids.
Returns a list of human-readable failure strings (each prefixed "check N:");
an empty list means all checks passed. The contract is never relaxed for smoke —
--smoke must still produce real, well-formed cluster labels.

Check 7 is order-independent multiset equality (alignment is by cell_id join, not
list order — spec §10), so it catches missing, extra, and duplicate ids while
allowing a valid reordering.
"""

from __future__ import annotations

import json
from pathlib import Path


def check_output(output_path: str | Path, expected_cell_ids: list[str]) -> list[str]:
    output_path = Path(output_path)
    failures: list[str] = []

    # Check 1: file exists and JSON parses.
    if not output_path.exists():
        return [f"check 1 failed: output file does not exist: {output_path}"]
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"check 1 failed: output is not valid JSON: {exc}"]

    # Check 2: cell_ids and labels keys present.
    if not isinstance(data, dict) or "cell_ids" not in data or "labels" not in data:
        return ["check 2 failed: 'cell_ids' and/or 'labels' key missing"]
    cell_ids = data["cell_ids"]
    labels = data["labels"]
    if not isinstance(cell_ids, list) or not isinstance(labels, list):
        return ["check 2 failed: 'cell_ids' and 'labels' must both be lists"]

    # Check 3: equal lengths.
    if len(cell_ids) != len(labels):
        failures.append(
            f"check 3 failed: len(cell_ids)={len(cell_ids)} != len(labels)={len(labels)}"
        )

    # Check 4: at least one label.
    if len(labels) == 0:
        failures.append("check 4 failed: labels is empty")

    # Check 5: no null values in either list.
    if any(v is None for v in cell_ids) or any(v is None for v in labels):
        failures.append("check 5 failed: null value present in cell_ids or labels")

    # Check 6: labels uniformly str or uniformly int (bool/float excluded).
    if labels:
        non_null = [v for v in labels if v is not None]
        types = {type(v) for v in non_null}
        if not (types == {int} or types == {str}):
            failures.append(
                f"check 6 failed: labels must be uniformly int or str, got types {sorted(t.__name__ for t in types)}"
            )

    # Check 7: cell_ids multiset matches expected obs_names exactly (order-free).
    if sorted(cell_ids) != sorted(expected_cell_ids):
        failures.append(
            f"check 7 failed: cell_ids do not match expected obs_names "
            f"(got {len(cell_ids)}, expected {len(expected_cell_ids)})"
        )

    return failures
