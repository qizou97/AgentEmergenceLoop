"""
sobench/metrics.py — deterministic ARI / NMI computation (spec §10).

Alignment is by cell_id JOIN, never by list order: pred and true are dicts keyed
by cell_id. A missing, extra, or duplicate id is a hard error (AlignmentError) —
never a silently dropped row or a silent None. The runner is responsible for
turning that error into a BenchRecord with status="invalid_output"; the metric
layer's job is only to refuse to score misaligned data.
"""

from __future__ import annotations

from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score


class AlignmentError(ValueError):
    """Raised when pred and true cell_id sets do not match exactly."""


_METRIC_FUNCS = {
    "ARI": adjusted_rand_score,
    "NMI": normalized_mutual_info_score,
}


def compute(
    pred: dict[str, int | str],
    true: dict[str, int | str],
    metrics: list[str],
) -> dict[str, float | None]:
    """Compute the requested metrics over cell_id-aligned labels.

    Parameters
    ----------
    pred, true : {cell_id: label}
        Predicted and ground-truth cluster labels. Keys must match exactly.
    metrics : list[str]
        Subset of {"ARI", "NMI"}.

    Raises
    ------
    AlignmentError
        If the key sets differ (missing or extra cell_ids).
    ValueError
        If an unknown metric is requested.
    """
    unknown = [m for m in metrics if m not in _METRIC_FUNCS]
    if unknown:
        raise ValueError(f"unknown metric(s): {unknown}; allowed: {sorted(_METRIC_FUNCS)}")

    pred_ids = set(pred)
    true_ids = set(true)
    if pred_ids != true_ids:
        missing = sorted(true_ids - pred_ids)
        extra = sorted(pred_ids - true_ids)
        raise AlignmentError(
            f"cell_id mismatch: {len(missing)} missing, {len(extra)} extra "
            f"(missing e.g. {missing[:3]}, extra e.g. {extra[:3]})"
        )

    ids = sorted(true_ids)  # deterministic order
    true_labels = [true[i] for i in ids]
    pred_labels = [pred[i] for i in ids]

    return {m: float(_METRIC_FUNCS[m](true_labels, pred_labels)) for m in metrics}
