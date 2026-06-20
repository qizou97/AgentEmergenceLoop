"""
test_cli.py — tool/sobench.py, the single agent entry point (spec §3).

Pure-stdlib argparse + subprocess wrapper. These tests exercise the deterministic
commands that need neither conda nor a driver: --help, scaffold, and validate
(which freezes contracts against the REAL MERFISH_0.04.h5ad). env/smoke/run are
covered by the opt-in integration test. The CLI is invoked as a subprocess, as
the agent invokes it. No mocks.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
CLI = REPO_ROOT / "tool" / "sobench.py"
REAL_H5AD = "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad"


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args],
                          cwd=REPO_ROOT, capture_output=True, text=True)


def test_help_lists_seven_commands():
    proc = _run("--help")
    assert proc.returncode == 0
    for cmd in ("scaffold", "validate", "env", "smoke", "run", "aggregate", "experience"):
        assert cmd in proc.stdout


def test_unknown_command_errors():
    proc = _run("frobnicate")
    assert proc.returncode != 0


def test_scaffold_creates_project(tmp_path):
    proj = tmp_path / "spatial_domain_identification"
    proc = _run("scaffold", "--project-dir", str(proj))
    assert proc.returncode == 0, proc.stderr
    assert (proj / "run_benchmark.py").is_file()
    assert (proj / "methods").is_dir()


def _write_valid_drafts(proj: Path) -> None:
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "task_contract_draft.json").write_text(json.dumps({
        "project_id": "spatial_domain_identification_20260620",
        "task": "spatial_domain_identification",
        "dataset": "MERFISH",
        "cases": ["MERFISH_0.04"],
        "methods": [{
            "name": "STAGATE_pyG",
            "repo_path": "data/spatial_domain_identification_task/codes/STAGATE_pyG",
            "driver_path": "methods/STAGATE_pyG/driver.py",
            "env_file": "methods/STAGATE_pyG/env.yml",
            "env_record": "methods/STAGATE_pyG/env_record.json",
        }],
    }))
    (proj / "data_contract_draft.json").write_text(json.dumps({
        "cases": {"MERFISH_0.04": {
            "h5ad_path": REAL_H5AD,
            "obs_columns": ["cell_class", "ground_truth"],
            "spatial_key": "spatial",
            "ground_truth_column": "ground_truth",
        }},
    }))
    (proj / "metric_contract_draft.json").write_text(json.dumps({
        "metrics": ["ARI", "NMI"], "implementation": "sobench.metrics",
        "label_type": "integer_cluster_labels",
    }))


def test_validate_pass_exit_zero_and_freezes(tmp_path):
    proj = tmp_path / "p"
    _write_valid_drafts(proj)
    proc = _run("validate", "--project-dir", str(proj))
    assert proc.returncode == 0, proc.stderr
    assert (proj / "task_contract.json").exists()
    assert json.loads((proj / "freeze_report.json").read_text())["passed"] is True


def test_validate_fail_exit_nonzero(tmp_path):
    proj = tmp_path / "p"
    _write_valid_drafts(proj)
    # Break the ground-truth column (the stale spec example) -> freeze must fail.
    d = json.loads((proj / "data_contract_draft.json").read_text())
    d["cases"]["MERFISH_0.04"]["ground_truth_column"] = "Cell_class"
    (proj / "data_contract_draft.json").write_text(json.dumps(d))

    proc = _run("validate", "--project-dir", str(proj))
    assert proc.returncode != 0
    assert json.loads((proj / "freeze_report.json").read_text())["passed"] is False
    assert not (proj / "task_contract.json").exists()
