"""
test_metrics.py — ARI/NMI computation by cell_id join, against the real task.

Labels come from the real MERFISH_0.04 ground_truth column (8 spatial domains).
No mocks, no synthetic arrays (docs/TESTING_POLICY.md).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sobench.metrics import AlignmentError, compute

REAL_H5AD = (
    Path(__file__).parents[1]
    / "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"
)


def _real_ground_truth() -> dict[str, str]:
    """{cell_id: ground_truth_label} from the real h5ad, JSON/join-safe str labels."""
    import anndata as ad

    adata = ad.read_h5ad(REAL_H5AD)
    labels = adata.obs["ground_truth"].astype(str).tolist()
    return dict(zip(adata.obs_names, labels))


def test_perfect_prediction_scores_one():
    true = _real_ground_truth()
    pred = dict(true)  # identical labels
    out = compute(pred, true, ["ARI", "NMI"])
    assert out["ARI"] == pytest.approx(1.0)
    assert out["NMI"] == pytest.approx(1.0)


def test_relabel_is_invariant_under_permutation():
    """ARI/NMI are invariant to label renaming — a consistent relabel still scores 1.0."""
    true = _real_ground_truth()
    relabel = {lbl: f"cluster_{i}" for i, lbl in enumerate(sorted(set(true.values())))}
    pred = {cid: relabel[lbl] for cid, lbl in true.items()}
    out = compute(pred, true, ["ARI", "NMI"])
    assert out["ARI"] == pytest.approx(1.0)
    assert out["NMI"] == pytest.approx(1.0)


def test_matches_sklearn_on_a_degraded_prediction():
    """A deterministic partial-merge prediction matches a direct sklearn computation."""
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

    true = _real_ground_truth()
    # Collapse every label to one of two buckets by sorted-label parity — deterministic.
    order = {lbl: i for i, lbl in enumerate(sorted(set(true.values())))}
    pred = {cid: str(order[lbl] % 2) for cid, lbl in true.items()}

    ids = sorted(true)
    t = [true[i] for i in ids]
    p = [pred[i] for i in ids]
    out = compute(pred, true, ["ARI", "NMI"])
    assert out["ARI"] == pytest.approx(adjusted_rand_score(t, p))
    assert out["NMI"] == pytest.approx(normalized_mutual_info_score(t, p))


def test_integer_labels_supported():
    """Drivers emit integer cluster labels (label_type=integer_cluster_labels)."""
    true = _real_ground_truth()
    order = {lbl: i for i, lbl in enumerate(sorted(set(true.values())))}
    pred = {cid: order[lbl] for cid, lbl in true.items()}  # int labels
    out = compute(pred, true, ["ARI", "NMI"])
    assert out["ARI"] == pytest.approx(1.0)


def test_missing_cell_id_raises():
    true = _real_ground_truth()
    pred = dict(true)
    pred.pop(next(iter(pred)))  # drop one
    with pytest.raises(AlignmentError):
        compute(pred, true, ["ARI"])


def test_extra_cell_id_raises():
    true = _real_ground_truth()
    pred = dict(true)
    pred["__not_a_real_cell__"] = "MPA"
    with pytest.raises(AlignmentError):
        compute(pred, true, ["ARI"])


def test_unknown_metric_raises():
    true = _real_ground_truth()
    with pytest.raises(ValueError):
        compute(dict(true), true, ["FOO"])
