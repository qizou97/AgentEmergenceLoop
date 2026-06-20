"""
test_smoke.py — deterministic smoke h5ad + driver_record append (spec §7).

make_smoke_h5ad subsamples a REAL case h5ad to a fixed, deterministic ~100-spot
file that a driver can actually train on; check 7 later compares the driver's
cell_ids against this file's obs_names. The full smoke() driver subprocess is
integration-only. Inputs are the real MERFISH_0.04.h5ad. No mocks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sobench.smoke import append_attempt, make_smoke_h5ad

REAL_H5AD = (
    Path(__file__).parents[1]
    / "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
)


def test_make_smoke_h5ad_is_deterministic(tmp_path):
    out1 = tmp_path / "s1.h5ad"
    out2 = tmp_path / "s2.h5ad"
    ids1 = make_smoke_h5ad(REAL_H5AD, out1)
    ids2 = make_smoke_h5ad(REAL_H5AD, out2)
    assert ids1 == ids2
    assert len(ids1) == 100


def test_smoke_h5ad_preserves_real_structure(tmp_path):
    import anndata as ad

    out = tmp_path / "s.h5ad"
    ids = make_smoke_h5ad(REAL_H5AD, out)

    smoke = ad.read_h5ad(out)
    real = ad.read_h5ad(REAL_H5AD)
    assert list(smoke.obs_names) == ids
    assert smoke.n_obs == 100
    assert smoke.n_vars == real.n_vars               # genes preserved
    assert list(smoke.obsm.keys()) == list(real.obsm.keys())
    assert smoke.obsm["spatial"].shape == (100, 2)
    assert "ground_truth" in smoke.obs.columns       # ground truth preserved
    # the subsampled cells are a genuine subset of the real cells
    assert set(ids).issubset(set(real.obs_names))


def test_smoke_subset_rows_align(tmp_path):
    """obs_names / spatial / X rows stay aligned to the same real cells."""
    import anndata as ad
    import numpy as np

    out = tmp_path / "s.h5ad"
    ids = make_smoke_h5ad(REAL_H5AD, out)
    smoke = ad.read_h5ad(out)
    real = ad.read_h5ad(REAL_H5AD)

    # Pick the smoke file's first cell; its spatial coords must match the real row.
    cid = ids[0]
    real_row = list(real.obs_names).index(cid)
    np.testing.assert_array_equal(smoke.obsm["spatial"][0], real.obsm["spatial"][real_row])


def test_make_smoke_h5ad_handles_fewer_than_n(tmp_path):
    """When the source has fewer than n cells, take them all (no error, no padding)."""
    import anndata as ad

    real = ad.read_h5ad(REAL_H5AD)
    small = real[:50].copy()
    small_path = tmp_path / "small.h5ad"
    small.write_h5ad(small_path)

    out = tmp_path / "s.h5ad"
    ids = make_smoke_h5ad(small_path, out, n=100)
    assert len(ids) == 50


def test_append_attempt_creates_and_grows_record(tmp_path):
    import json

    rec_path = tmp_path / "driver_record.json"

    append_attempt(rec_path, method="STAGATE_pyG", case="MERFISH_0.04",
                   command="py driver.py --smoke", stdout="", stderr="boom",
                   validation_failures=["check 7 failed: cell_ids mismatch"],
                   status="invalid_output")
    rec = json.loads(rec_path.read_text())
    assert rec["method"] == "STAGATE_pyG"
    assert rec["final_status"] == "invalid_output"
    assert rec["repair_count"] == 0
    assert rec["attempts"][0]["attempt"] == 1

    append_attempt(rec_path, method="STAGATE_pyG", case="MERFISH_0.04",
                   command="py driver.py --smoke", stdout="", stderr="",
                   validation_failures=[], status="smoke_valid")
    rec = json.loads(rec_path.read_text())
    assert len(rec["attempts"]) == 2
    assert rec["attempts"][1]["attempt"] == 2
    assert rec["final_status"] == "smoke_valid"  # reflects most recent attempt
    assert rec["repair_count"] == 1              # attempts after the first
    assert list(rec_path.parent.glob("*.tmp")) == []
