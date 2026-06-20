"""
test_checker.py — the 7-check smoke output validator (spec §7).

expected_cell_ids derives from the REAL MERFISH_0.04 obs_names (the first 100 —
a deterministic real subset, the same shape the smoke h5ad will have). No mocks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sobench.checker import check_output

REAL_H5AD = (
    Path(__file__).parents[1]
    / "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
)


@pytest.fixture(scope="module")
def expected_ids() -> list[str]:
    import anndata as ad

    adata = ad.read_h5ad(REAL_H5AD)
    return list(adata.obs_names[:100])


def _write(tmp_path: Path, obj) -> Path:
    p = tmp_path / "result.json"
    p.write_text(json.dumps(obj))
    return p


def _valid_output(ids: list[str]) -> dict:
    return {
        "cell_ids": list(ids),
        "labels": [i % 3 for i in range(len(ids))],
        "status": "success",
        "metadata": {},
    }


def test_valid_output_passes(tmp_path, expected_ids):
    p = _write(tmp_path, _valid_output(expected_ids))
    assert check_output(p, expected_ids) == []


def test_check1_missing_file(tmp_path, expected_ids):
    failures = check_output(tmp_path / "nope.json", expected_ids)
    assert len(failures) == 1 and "1" in failures[0]


def test_check1_invalid_json(tmp_path, expected_ids):
    p = tmp_path / "result.json"
    p.write_text("{not json")
    failures = check_output(p, expected_ids)
    assert any("1" in f for f in failures)


def test_check2_missing_keys(tmp_path, expected_ids):
    p = _write(tmp_path, {"cell_ids": list(expected_ids)})  # labels missing
    failures = check_output(p, expected_ids)
    assert any("2" in f for f in failures)


def test_check3_length_mismatch(tmp_path, expected_ids):
    out = _valid_output(expected_ids)
    out["labels"] = out["labels"][:-1]  # one short
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("3" in f for f in failures)


def test_check4_empty_labels(tmp_path, expected_ids):
    out = {"cell_ids": [], "labels": [], "status": "success", "metadata": {}}
    failures = check_output(_write(tmp_path, out), [])
    assert any("4" in f for f in failures)


def test_check5_null_in_labels(tmp_path, expected_ids):
    out = _valid_output(expected_ids)
    out["labels"][0] = None
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("5" in f for f in failures)


def test_check6_mixed_label_types(tmp_path, expected_ids):
    out = _valid_output(expected_ids)
    out["labels"] = [str(x) for x in out["labels"]]
    out["labels"][0] = 0  # one int among strs
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("6" in f for f in failures)


def test_check6_float_labels_rejected(tmp_path, expected_ids):
    out = _valid_output(expected_ids)
    out["labels"] = [float(x) for x in out["labels"]]
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("6" in f for f in failures)


def test_check6_uniform_string_labels_pass(tmp_path, expected_ids):
    out = _valid_output(expected_ids)
    out["labels"] = [f"domain_{x}" for x in out["labels"]]
    assert check_output(_write(tmp_path, out), expected_ids) == []


def test_check7_missing_id_fails(tmp_path, expected_ids):
    short = expected_ids[:-1]
    out = _valid_output(short)
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("7" in f for f in failures)


def test_check7_extra_id_fails(tmp_path, expected_ids):
    out = _valid_output(expected_ids + ["__ghost__"])
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("7" in f for f in failures)


def test_check7_duplicate_id_fails(tmp_path, expected_ids):
    dup = list(expected_ids)
    dup[1] = dup[0]  # duplicate id, same length
    out = _valid_output(dup)
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert any("7" in f for f in failures)


def test_check7_reordered_ids_pass(tmp_path, expected_ids):
    """Order-independent: alignment is by join (§10), so a reorder is valid."""
    reordered = list(reversed(expected_ids))
    out = _valid_output(reordered)
    assert check_output(_write(tmp_path, out), expected_ids) == []


def test_mixed_type_cell_ids_returns_failure_not_crash(tmp_path, expected_ids):
    """A driver emitting heterogeneous cell_ids must be a recorded failure, not a crash.

    sorted() would raise TypeError comparing int vs str; the checker must instead
    return a check-7 failure string (its whole contract is "return failures").
    """
    out = _valid_output(expected_ids)
    out["cell_ids"] = ["spot1", 2, "spot3"]  # mixed scalar types
    out["labels"] = [0, 1, 2]
    failures = check_output(_write(tmp_path, out), expected_ids)
    assert failures  # non-empty, and no exception escaped
    assert any("7" in f for f in failures)
