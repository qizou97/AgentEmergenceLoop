"""
sobench/env_builder.py — per-method conda env creation + record (spec §3 `env`).

Each benchmark method gets ONE isolated conda/mamba env built from its env.yml.
The env is created at a path-deterministic prefix keyed on the env.yml content
hash, so an unchanged env.yml reuses the existing env (idempotent). The recorded
interpreter_path (<prefix>/bin/python) is what smoke.py and runner.py use to
invoke the driver — never the development or agent interpreter.

env_yml_hash() and env_record_is_current() are pure and unit-tested. build_env()
shells out to mamba/conda and is exercised by the opt-in integration test.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from sobench.atomicio import write_json_atomic


def env_yml_hash(env_yml_path: str | Path) -> str:
    data = Path(env_yml_path).read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def env_record_is_current(env_record_path: str | Path, env_yml_path: str | Path) -> bool:
    """True iff env_record exists and was built from the current env.yml content."""
    env_record_path = Path(env_record_path)
    if not env_record_path.exists():
        return False
    try:
        rec = json.loads(env_record_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return rec.get("env_yml_hash") == env_yml_hash(env_yml_path)


def _conda_tool() -> str:
    for tool in ("mamba", "conda"):
        if shutil.which(tool):
            return tool
    raise RuntimeError("neither mamba nor conda found on PATH")


def build_env(project_dir: str | Path, method: str, *, envs_root: str | Path | None = None) -> dict:
    """Create (or reuse) the method's conda env and write env_record.json.

    The env prefix lives under <project_dir>/methods/<method>/.env-<shorthash> by
    default. Returns the env_record dict.
    """
    project_dir = Path(project_dir)
    mdir = project_dir / "methods" / method
    env_yml = mdir / "env.yml"
    if not env_yml.exists():
        raise FileNotFoundError(f"env.yml not found for method {method}: {env_yml}")
    env_record_path = mdir / "env_record.json"

    if env_record_is_current(env_record_path, env_yml):
        rec = json.loads(env_record_path.read_text(encoding="utf-8"))
        if Path(rec.get("interpreter_path", "")).exists():
            return rec  # cached and intact

    yml_hash = env_yml_hash(env_yml)
    short = yml_hash.split(":")[1][:12]
    env_name = f"sobench_{method}_{short}"
    base = Path(envs_root) if envs_root is not None else mdir
    prefix = (base / f".env-{short}").resolve()

    tool = _conda_tool()
    subprocess.run(
        [tool, "env", "create", "--yes", "--prefix", str(prefix), "--file", str(env_yml)],
        check=True, capture_output=True, text=True,
    )
    interpreter = prefix / "bin" / "python"

    rec = {
        "method": method,
        "env_name": env_name,
        "prefix": str(prefix),
        "interpreter_path": str(interpreter),
        "env_yml_hash": yml_hash,
        "tool": tool,
    }
    write_json_atomic(env_record_path, rec)
    return rec


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.env_builder --project-dir <p> --method <M>."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.env_builder")
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--method", required=True)
    args = ap.parse_args(argv)
    rec = build_env(args.project_dir, args.method)
    print(json.dumps(rec, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
