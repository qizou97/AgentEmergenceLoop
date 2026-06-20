"""
sobench/experience.py — append-only experience store (spec §11).

Reads a completed (or partial) benchmark project and appends structured entries
to three git-tracked indexes:

    experience_store/methods/<method>.json
    experience_store/datasets/<dataset_stem>.json
    experience_store/metrics/<metric>.json

Each file is a JSON array, newest-first. Writes are atomic (temp + os.replace).
Every entry carries schema_version "1". env/driver/benchmark statuses are
independent; `partial: true` + `missing_artifacts` flag any absent artifact.
The dataset h5ad_fingerprint is read from the ACTUAL h5ad, never copied from a
draft contract. M1 only WRITES experience; retrieval/reuse is M2.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from sobench.atomicio import write_json_atomic

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _now():
    return datetime.now(timezone.utc)


def _ref(path: Path) -> str:
    """Path as a repo-relative posix string when possible, else absolute."""
    path = path.resolve()
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_array(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _prepend(store_dir: Path, index: str, name: str, kind: str, date_str: str, payload: dict) -> dict:
    """Build an entry (with sequenced entry_id) and atomically prepend it newest-first."""
    path = store_dir / index / f"{name}.json"
    existing = _read_array(path)
    seq = len(existing) + 1
    entry = {
        "schema_version": "1",
        "entry_id": f"{kind}-{name}-{date_str}-{seq:03d}",
        "created_at": payload.pop("_created_at"),
        **payload,
    }
    existing.insert(0, entry)
    write_json_atomic(path, existing)
    return entry


def _resolve(repo_relative: str) -> Path:
    p = Path(repo_relative)
    return p if p.is_absolute() else (_REPO_ROOT / p)


def write_experience(project_dir: str | Path, store_dir: str | Path) -> dict:
    """Append experience entries from one project's run artifacts. Returns a summary."""
    project_dir = Path(project_dir)
    store_dir = Path(store_dir)

    task = json.loads((project_dir / "task_contract.json").read_text(encoding="utf-8"))
    data = json.loads((project_dir / "data_contract.json").read_text(encoding="utf-8"))
    metric = json.loads((project_dir / "metric_contract.json").read_text(encoding="utf-8"))

    now = _now()
    created_at = now.isoformat()
    date_str = now.strftime("%Y%m%d")

    task_name = task["task"]
    dataset = task["dataset"]
    summary = {"methods": 0, "datasets": 0, "metrics": 0, "partial": 0}

    # --- method entries: one per method × case ---------------------------------
    for m in task["methods"]:
        method = m["name"]
        mdir = project_dir / "methods" / method
        env_record_path = project_dir / m["env_record"]
        driver_record_path = mdir / "driver_record.json"
        env_yml_path = mdir / "env.yml"
        driver_path = mdir / "driver.py"
        adapter_path = project_dir / "data_adapter.py"

        for case in task["cases"]:
            bench_path = project_dir / "results" / f"{method}_{case}.json"

            missing: list[str] = []
            for label, p in [
                ("env.yml", env_yml_path),
                ("driver.py", driver_path),
                (f"env_record ({m['env_record']})", env_record_path),
                ("driver_record.json", driver_record_path),
                (f"bench_record ({bench_path.name})", bench_path),
            ]:
                if not p.exists():
                    missing.append(_ref(p) if p.is_absolute() or label.startswith(("env_record", "bench_record")) else label)

            env_status = "env_created" if env_record_path.exists() else "env_missing"

            driver_status = "driver_missing"
            driver_repair_count = 0
            repair_patterns: list[dict] = []
            if driver_record_path.exists():
                dr = json.loads(driver_record_path.read_text(encoding="utf-8"))
                driver_status = dr.get("final_status", "unknown")
                driver_repair_count = dr.get("repair_count", 0)
                for att in dr.get("attempts", []):
                    for vf in att.get("validation_failures", []) or []:
                        repair_patterns.append({"stderr_fragment": vf, "fix_description": ""})

            benchmark_status = "not_executed"
            if bench_path.exists():
                br = json.loads(bench_path.read_text(encoding="utf-8"))
                benchmark_status = "benchmark_executed" if br.get("status") == "success" else "execution_failed"

            partial = bool(missing)
            if partial:
                summary["partial"] += 1
            reason = None
            if partial:
                reason = "missing artifacts: " + ", ".join(missing)

            _prepend(store_dir, "methods", method, "method", date_str, {
                "_created_at": created_at,
                "task": task_name,
                "method": method,
                "dataset": dataset,
                "case": case,
                "source_project": _ref(project_dir),
                "env_status": env_status,
                "driver_status": driver_status,
                "benchmark_status": benchmark_status,
                "driver_repair_count": driver_repair_count,
                "env_yml_ref": _ref(env_yml_path),
                "env_yml_hash": _sha256_file(env_yml_path),
                "driver_snapshot_ref": _ref(driver_path),
                "driver_snapshot_hash": _sha256_file(driver_path),
                "data_adapter_ref": _ref(adapter_path),
                "repair_patterns": repair_patterns,
                "env_record_ref": _ref(env_record_path),
                "driver_record_ref": _ref(driver_record_path),
                "bench_record_ref": _ref(bench_path),
                "partial": partial,
                "missing_artifacts": missing,
                "reason": reason,
            })
            summary["methods"] += 1

    # --- dataset entries: one per case (fingerprint from the REAL h5ad) ---------
    for case, cdata in data["cases"].items():
        h5ad = _resolve(cdata["h5ad_path"])
        missing = []
        fingerprint = None
        shape = None
        size_bytes = None
        mtime = None
        if h5ad.exists():
            import anndata as ad

            adata = ad.read_h5ad(h5ad)
            fingerprint = {
                "obs_columns": list(adata.obs.columns),
                "obsm_keys": list(adata.obsm.keys()),
                "has_raw": adata.raw is not None,
            }
            shape = [int(adata.n_obs), int(adata.n_vars)]
            st = h5ad.stat()
            size_bytes = st.st_size
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        else:
            missing.append(_ref(h5ad))

        adapter_path = project_dir / "data_adapter.py"
        partial = bool(missing)
        if partial:
            summary["partial"] += 1

        _prepend(store_dir, "datasets", dataset, "dataset", date_str, {
            "_created_at": created_at,
            "task": task_name,
            "dataset_stem": dataset,
            "case": case,
            "source_project": _ref(project_dir),
            "h5ad_path": cdata["h5ad_path"],
            "h5ad_size_bytes": size_bytes,
            "h5ad_mtime": mtime,
            "h5ad_shape": shape,
            "h5ad_fingerprint": fingerprint,
            "ground_truth_column": cdata["ground_truth_column"],
            "spatial_key": cdata["spatial_key"],
            "data_adapter_ref": _ref(adapter_path),
            "data_adapter_hash": _sha256_file(adapter_path),
            "contract_ref": _ref(project_dir / "data_contract.json"),
            "freeze_report_ref": _ref(project_dir / "freeze_report.json"),
            "partial": partial,
            "missing_artifacts": missing,
            "reason": ("missing artifacts: " + ", ".join(missing)) if partial else None,
        })
        summary["datasets"] += 1

    # --- metric entries: one per (executed bench record × metric with a value) --
    for m in task["methods"]:
        method = m["name"]
        for case in task["cases"]:
            bench_path = project_dir / "results" / f"{method}_{case}.json"
            if not bench_path.exists():
                continue
            br = json.loads(bench_path.read_text(encoding="utf-8"))
            metrics_obj = br.get("metrics", {})
            gt_col = data["cases"].get(case, {}).get("ground_truth_column")
            for metric_name in metric["metrics"]:
                value = metrics_obj.get(metric_name)
                if value is None:
                    continue  # spec §11: metric entries only for computed metrics
                _prepend(store_dir, "metrics", metric_name, "metric", date_str, {
                    "_created_at": created_at,
                    "task": task_name,
                    "metric": metric_name,
                    "method": method,
                    "case": case,
                    "implementation": "sobench.metrics.compute",
                    "ground_truth_column": gt_col,
                    "label_type": metric.get("label_type"),
                    "alignment": "by_cell_ids",
                    "status": br.get("status"),
                    "value": value,
                    "bench_record_ref": _ref(bench_path),
                    "partial": False,
                    "missing_artifacts": [],
                    "reason": None,
                })
                summary["metrics"] += 1

    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.experience --project-dir <p> [--store-dir <s>]."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.experience")
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--store-dir", default=str(_REPO_ROOT / "experience_store"))
    args = ap.parse_args(argv)
    summary = write_experience(args.project_dir, args.store_dir)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
