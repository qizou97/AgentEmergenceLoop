"""
sobench/contracts/freeze.py — the freeze flow (spec §5).

Validates the agent-written draft contracts against the REAL h5ad files, and on
success freezes them. This is the deterministic gate between "agent proposes" and
"runner executes": the runner reads ONLY the frozen *_contract.json. Column and
key names are never hardcoded — they are checked against each file's actual
obs.columns / obsm.keys().

PASS  -> writes task_contract.json, data_contract.json, metric_contract.json
         (frozen) + freeze_report.json {passed:true, timestamp, contract_hashes};
         drafts are preserved as-is.
FAIL  -> writes only freeze_report.json {passed:false, errors:[...]}; no frozen
         files; drafts preserved. The agent reads errors and revises drafts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from sobench.atomicio import write_json_atomic
from sobench.contracts.data_contract import DataContract
from sobench.contracts.metric_contract import MetricContract
from sobench.contracts.task_contract import TaskContract

ALLOWED_METRICS = {"ARI", "NMI"}

# Repo root = the directory containing the `sobench/` package. h5ad_path entries
# are repo-root-relative (spec §4.2). Standalone packaging is post-M1 (spec §2).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _canonical_hash(obj: dict) -> str:
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _resolve_h5ad(h5ad_path: str) -> Path:
    p = Path(h5ad_path)
    return p if p.is_absolute() else (_REPO_ROOT / p)


def _load_draft(path: Path, model, label: str, errors: list[str]):
    """Load + schema-validate one draft. Append an error and return None on failure."""
    if not path.exists():
        errors.append(f"{label}: draft file missing ({path.name})")
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: draft is not valid JSON: {exc}")
        return None
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        errors.append(f"{label}: schema validation failed: {exc.errors()}")
        return None


def freeze(project_dir: str | Path) -> dict:
    """Validate drafts against real h5ad files; freeze on pass. Returns the report dict."""
    project_dir = Path(project_dir)
    errors: list[str] = []

    task = _load_draft(project_dir / "task_contract_draft.json", TaskContract, "task_contract", errors)
    data = _load_draft(project_dir / "data_contract_draft.json", DataContract, "data_contract", errors)
    metric = _load_draft(project_dir / "metric_contract_draft.json", MetricContract, "metric_contract", errors)

    # Cross-contract + real-data checks only run when all drafts parsed.
    if task is not None and data is not None and metric is not None:
        # metrics subset of {ARI, NMI}
        for m in metric.metrics:
            if m not in ALLOWED_METRICS:
                errors.append(f"metric_contract: metric {m!r} not in allowed set {sorted(ALLOWED_METRICS)}")

        task_cases = set(task.cases)
        for case_key, case in data.cases.items():
            # every data-contract case must be declared in the task matrix
            if case_key not in task_cases:
                errors.append(
                    f"data_contract: case {case_key!r} not in task_contract.cases {sorted(task_cases)}"
                )

            h5ad = _resolve_h5ad(case.h5ad_path)
            if not h5ad.exists():
                errors.append(f"data_contract[{case_key}]: h5ad not found at {case.h5ad_path}")
                continue

            try:
                import anndata as ad

                adata = ad.read_h5ad(h5ad)
            except Exception as exc:  # noqa: BLE001 — surface any read failure as a contract error
                errors.append(f"data_contract[{case_key}]: failed to open h5ad: {exc}")
                continue

            obs_cols = list(adata.obs.columns)
            obsm_keys = list(adata.obsm.keys())
            if case.ground_truth_column not in obs_cols:
                errors.append(
                    f"data_contract[{case_key}]: ground_truth_column "
                    f"{case.ground_truth_column!r} not in obs.columns {obs_cols}"
                )
            if case.spatial_key not in obsm_keys:
                errors.append(
                    f"data_contract[{case_key}]: spatial_key "
                    f"{case.spatial_key!r} not in obsm.keys() {obsm_keys}"
                )

    timestamp = datetime.now(timezone.utc).isoformat()

    if errors:
        # Spec §5: a FAIL leaves no frozen contracts. Remove any stale ones from a
        # prior PASS so the runner (which gates on file presence) can never execute
        # against contracts the current drafts no longer satisfy.
        for name in ("task_contract.json", "data_contract.json", "metric_contract.json"):
            stale = project_dir / name
            if stale.exists():
                stale.unlink()
        report = {"passed": False, "timestamp": timestamp, "errors": errors}
        write_json_atomic(project_dir / "freeze_report.json", report)
        return report

    # PASS — freeze the validated, normalized contract dicts.
    frozen = {
        "task_contract": task.model_dump(mode="json"),
        "data_contract": data.model_dump(mode="json"),
        "metric_contract": metric.model_dump(mode="json"),
    }
    for name, obj in frozen.items():
        write_json_atomic(project_dir / f"{name}.json", obj)

    report = {
        "passed": True,
        "timestamp": timestamp,
        "contract_hashes": {name: _canonical_hash(obj) for name, obj in frozen.items()},
    }
    write_json_atomic(project_dir / "freeze_report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.contracts.freeze --project-dir <p>.

    Exits 0 when the contracts froze, 1 when validation failed — so the agent's
    `validate` skill can branch on the exit code as well as freeze_report.json.
    """
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.contracts.freeze")
    ap.add_argument("--project-dir", required=True)
    args = ap.parse_args(argv)
    report = freeze(args.project_dir)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
