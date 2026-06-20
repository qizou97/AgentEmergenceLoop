"""
sobench/runner.py — full benchmark execution + BenchRecord writing (spec §9–§10).

The runner owns all orchestration: load frozen contracts, select each method's
interpreter from env_record.json, run the driver as a subprocess, validate output
via checker.py, align driver cell_ids with ground truth BY JOIN (not list order),
compute metrics, and write one BenchRecord JSON per method×case.

build_record() is the deterministic core (no subprocess) and is unit-tested
against the real task. run() adds contract loading + the live driver subprocess
(exercised by the opt-in integration test). Ground truth is read directly from
each case's h5ad using the frozen data_contract's ground_truth_column, keyed by
obs_names — independent of the agent's data_adapter.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sobench.atomicio import write_json_atomic
from sobench.checker import check_output
from sobench.contracts.bench_record import BenchRecord, SpatialMetrics
from sobench.metrics import AlignmentError, compute

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Generous ceiling for a full method run; tunable later. Smoke uses its own path.
_DEFAULT_TIMEOUT_SECONDS = 3 * 60 * 60


def _excerpt(text: str, limit: int = 4000) -> str:
    text = text or ""
    return text if len(text) <= limit else "...(truncated)... " + text[-limit:]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_record(
    *,
    output_path: str | Path,
    ground_truth: dict[str, int | str],
    metrics: list[str],
    returncode: int,
    method: str,
    dataset: str,
    case: str,
    task: str,
    project_id: str,
    env_name: str,
    stderr: str = "",
    duration_seconds: float | None = None,
    driver_repair_count: int = 0,
) -> BenchRecord:
    """Turn one driver invocation's result into a BenchRecord. No subprocess here."""
    record_id = f"{method}__{dataset}__{case}"
    common = dict(
        record_id=record_id, project_id=project_id, task=task, method=method,
        dataset=dataset, case=case, env_name=env_name,
        duration_seconds=duration_seconds, driver_repair_count=driver_repair_count,
        created_at=_now_iso(),
    )

    # Driver crashed: never trust partial output.
    if returncode != 0:
        return BenchRecord(
            metrics=SpatialMetrics(), status="failed",
            failure_detail=f"driver exited {returncode}: {_excerpt(stderr)}", **common,
        )

    # Output well-formed and cell_ids match the ground-truth obs_names exactly?
    failures = check_output(output_path, list(ground_truth))
    if failures:
        return BenchRecord(
            metrics=SpatialMetrics(), status="invalid_output",
            failure_detail="; ".join(failures), **common,
        )

    data = json.loads(Path(output_path).read_text(encoding="utf-8"))
    pred = dict(zip(data["cell_ids"], data["labels"]))
    try:
        scores = compute(pred, ground_truth, metrics)
    except AlignmentError as exc:  # defensive — checker should have caught this
        return BenchRecord(
            metrics=SpatialMetrics(), status="invalid_output",
            failure_detail=f"alignment failed: {exc}", **common,
        )

    return BenchRecord(
        metrics=SpatialMetrics(ARI=scores.get("ARI"), NMI=scores.get("NMI")),
        status="success", **common,
    )


def _load_frozen(project_dir: Path) -> tuple[dict, dict, dict]:
    paths = {
        "task": project_dir / "task_contract.json",
        "data": project_dir / "data_contract.json",
        "metric": project_dir / "metric_contract.json",
    }
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "frozen contract(s) not found: " + ", ".join(missing)
            + " — run `sobench validate` until freeze passes before running."
        )
    return tuple(json.loads(p.read_text(encoding="utf-8")) for p in paths.values())  # type: ignore[return-value]


def _resolve(repo_relative: str) -> Path:
    p = Path(repo_relative)
    return p if p.is_absolute() else (_REPO_ROOT / p)


def _ground_truth_for_case(case_data: dict) -> dict[str, str]:
    import anndata as ad

    adata = ad.read_h5ad(_resolve(case_data["h5ad_path"]))
    labels = adata.obs[case_data["ground_truth_column"]].astype(str).tolist()
    return dict(zip(adata.obs_names, labels))


def run(project_dir: str | Path) -> list[BenchRecord]:
    """Execute every method×case in the frozen matrix; write BenchRecords. Returns them."""
    project_dir = Path(project_dir)
    task, data, metric = _load_frozen(project_dir)

    metrics = metric["metrics"]
    dataset = task["dataset"]
    project_id = task["project_id"]
    task_name = task["task"]
    results_dir = project_dir / "results"
    records: list[BenchRecord] = []

    for m in task["methods"]:
        method = m["name"]
        env_record_path = project_dir / m["env_record"]
        driver_path = project_dir / m["driver_path"]
        repo_path = _resolve(m["repo_path"])

        env_name = ""
        interpreter = None
        if env_record_path.exists():
            env_rec = json.loads(env_record_path.read_text(encoding="utf-8"))
            interpreter = env_rec.get("interpreter_path")
            env_name = env_rec.get("env_name", "")

        for case in task["cases"]:
            case_data = data["cases"].get(case)
            record_id = f"{method}__{dataset}__{case}"
            common = dict(
                record_id=record_id, project_id=project_id, task=task_name,
                method=method, dataset=dataset, case=case, env_name=env_name,
                driver_repair_count=0, created_at=_now_iso(),
            )

            if case_data is None:
                rec = BenchRecord(metrics=SpatialMetrics(), status="skipped",
                                  skip_reason=f"case {case} absent from data_contract", **common)
            elif interpreter is None:
                rec = BenchRecord(metrics=SpatialMetrics(), status="skipped",
                                  skip_reason="env_record.json absent; run `sobench env` first", **common)
            elif not driver_path.exists():
                rec = BenchRecord(metrics=SpatialMetrics(), status="skipped",
                                  skip_reason=f"driver not found at {m['driver_path']}", **common)
            else:
                rec = _run_one(
                    interpreter=interpreter, driver_path=driver_path, repo_path=repo_path,
                    case_data=case_data, results_dir=results_dir, metrics=metrics,
                    method=method, dataset=dataset, case=case, task=task_name,
                    project_id=project_id, env_name=env_name,
                )

            write_json_atomic(results_dir / f"{method}_{case}.json", rec.model_dump(mode="json"))
            records.append(rec)

    return records


def _run_one(*, interpreter, driver_path, repo_path, case_data, results_dir, metrics,
             method, dataset, case, task, project_id, env_name) -> BenchRecord:
    """Run a single driver subprocess and build its BenchRecord. (Integration path.)"""
    work_dir = results_dir / "_work" / f"{method}_{case}"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_path = work_dir / "result.json"
    h5ad = _resolve(case_data["h5ad_path"])
    ground_truth = _ground_truth_for_case(case_data)

    cmd = [
        str(interpreter), str(driver_path),
        "--data", str(h5ad),
        "--output", str(output_path),
        "--method-dir", str(repo_path),
        "--work-dir", str(work_dir),
    ]
    start = datetime.now(timezone.utc)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_DEFAULT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return BenchRecord(
            record_id=f"{method}__{dataset}__{case}", project_id=project_id, task=task,
            method=method, dataset=dataset, case=case, env_name=env_name,
            metrics=SpatialMetrics(), status="timeout", driver_repair_count=0,
            failure_detail=f"driver exceeded {_DEFAULT_TIMEOUT_SECONDS}s", created_at=_now_iso(),
        )
    duration = (datetime.now(timezone.utc) - start).total_seconds()

    return build_record(
        output_path=output_path, ground_truth=ground_truth, metrics=metrics,
        returncode=proc.returncode, stderr=proc.stderr, duration_seconds=duration,
        method=method, dataset=dataset, case=case, task=task,
        project_id=project_id, env_name=env_name,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.runner --project-dir <p>."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.runner")
    ap.add_argument("--project-dir", required=True)
    args = ap.parse_args(argv)
    records = run(args.project_dir)
    print(f"wrote {len(records)} BenchRecord(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
