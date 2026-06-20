"""
sobench/smoke.py — deterministic smoke validation (spec §7).

Before invoking a driver, sobench builds a deterministic ~100-spot smoke h5ad by
subsampling a REAL case h5ad (fixed seed). The driver receives this file as
--data and runs with --smoke (fast mode: reduced epochs, but still REAL cluster
labels — not a dry run). The 7-check validator then compares the driver's output
cell_ids against this file's obs_names. Each invocation appends one attempt to
driver_record.json (atomic). The 3-attempt repair limit is enforced by the agent
skill; the tool always records.

make_smoke_h5ad() and append_attempt() are deterministic and unit-tested. smoke()
runs the driver subprocess and is exercised by the opt-in integration test.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from sobench.atomicio import write_json_atomic
from sobench.checker import check_output

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SMOKE_SEED = 0
_SMOKE_N = 100
_SMOKE_TIMEOUT_SECONDS = 30 * 60


def make_smoke_h5ad(real_h5ad: str | Path, out_path: str | Path, *, n: int = _SMOKE_N,
                    seed: int = _SMOKE_SEED) -> list[str]:
    """Deterministically subsample a real h5ad to n spots. Returns the smoke obs_names."""
    import anndata as ad

    adata = ad.read_h5ad(real_h5ad)
    total = adata.n_obs
    take = min(n, total)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(total, size=take, replace=False))
    subset = adata[idx].copy()

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subset.write_h5ad(out_path)
    return list(subset.obs_names)


def append_attempt(driver_record_path: str | Path, *, method: str, case: str, command: str,
                   stdout: str, stderr: str, validation_failures: list[str], status: str) -> dict:
    """Atomically append one smoke attempt to driver_record.json (read → append → replace)."""
    driver_record_path = Path(driver_record_path)
    if driver_record_path.exists():
        rec = json.loads(driver_record_path.read_text(encoding="utf-8"))
    else:
        rec = {"method": method, "case": case, "attempts": []}

    attempt = {
        "attempt": len(rec["attempts"]) + 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "validation_failures": validation_failures,
        "status": status,
    }
    rec["attempts"].append(attempt)
    rec["final_status"] = status                       # most recent attempt
    rec["repair_count"] = len(rec["attempts"]) - 1     # attempts after the first
    write_json_atomic(driver_record_path, rec)
    return rec


def _resolve(repo_relative: str) -> Path:
    p = Path(repo_relative)
    return p if p.is_absolute() else (_REPO_ROOT / p)


def smoke(project_dir: str | Path, method: str, case: str) -> dict:
    """Build the smoke h5ad, run the driver with --smoke, validate, record. (Integration.)"""
    project_dir = Path(project_dir)
    task = json.loads((project_dir / "task_contract.json").read_text(encoding="utf-8"))
    data = json.loads((project_dir / "data_contract.json").read_text(encoding="utf-8"))

    m = next(x for x in task["methods"] if x["name"] == method)
    env_record_path = project_dir / m["env_record"]
    if not env_record_path.exists():
        raise FileNotFoundError(f"env_record.json absent for {method}; run `sobench env` first")
    interpreter = json.loads(env_record_path.read_text(encoding="utf-8"))["interpreter_path"]
    driver_path = project_dir / m["driver_path"]
    repo_path = _resolve(m["repo_path"])

    case_data = data["cases"][case]
    work_dir = project_dir / "methods" / method / "_smoke" / case
    work_dir.mkdir(parents=True, exist_ok=True)
    smoke_h5ad = work_dir / "smoke.h5ad"
    output_path = work_dir / "result.json"
    smoke_ids = make_smoke_h5ad(_resolve(case_data["h5ad_path"]), smoke_h5ad)

    cmd = [
        str(interpreter), str(driver_path),
        "--data", str(smoke_h5ad),
        "--output", str(output_path),
        "--method-dir", str(repo_path),
        "--work-dir", str(work_dir),
        "--smoke",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_SMOKE_TIMEOUT_SECONDS)
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode, stdout, stderr = -1, exc.stdout or "", (exc.stderr or "") + "\n[timeout]"

    if returncode != 0:
        failures = [f"driver exited {returncode}"]
        status = "driver_error"
    else:
        failures = check_output(output_path, smoke_ids)
        status = "smoke_valid" if not failures else "invalid_output"

    driver_record_path = project_dir / "methods" / method / "driver_record.json"
    return append_attempt(
        driver_record_path,
        method=method, case=case, command=" ".join(cmd),
        stdout=stdout[-4000:], stderr=stderr[-4000:],
        validation_failures=failures, status=status,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.smoke --project-dir <p> --method <M> --case <C>."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.smoke")
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--case", required=True)
    args = ap.parse_args(argv)
    rec = smoke(args.project_dir, args.method, args.case)
    print(json.dumps({"final_status": rec["final_status"], "repair_count": rec["repair_count"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
