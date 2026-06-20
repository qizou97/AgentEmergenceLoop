#!/usr/bin/env python3
"""sobench unified agent entry point — one command for the whole substrate.

The external coding agent invokes ONLY this script; it never calls internal
sobench modules directly. Pure standard library (argparse + subprocess): each
subcommand forwards to a `python -m sobench.<module>` subprocess, so the agent
operates the deterministic substrate without importing it. No LLM calls.

Usage:
    python tool/sobench.py <command> [args...]

Commands:
    scaffold    --project-dir <p> [--task <name>]      write project tree + run_benchmark.py
    validate    --project-dir <p>                      validate+freeze drafts against real h5ad
    env         --project-dir <p> --method <M>          create/cache conda env; write env_record
    smoke       --project-dir <p> --method <M> --case <C>  deterministic 100-spot smoke check
    run         --project-dir <p>                      run full method×case matrix; write BenchRecords
    aggregate   --project-dir <p>                      BenchRecords -> results.csv
    experience  --project-dir <p> [--store-dir <s>]    append experience entries

Run `python tool/sobench.py <command> --help` for a command's own flags.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# command name -> internal module run as `python -m <module>`
COMMANDS = {
    "scaffold": "sobench.scaffold",
    "validate": "sobench.contracts.freeze",
    "env": "sobench.env_builder",
    "smoke": "sobench.smoke",
    "run": "sobench.runner",
    "aggregate": "sobench.aggregator",
    "experience": "sobench.experience",
}


def _dispatch(module: str, rest: list[str]) -> int:
    env = os.environ.copy()
    # Ensure the subprocess can import the sobench package regardless of cwd.
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    argv = [sys.executable, "-m", module, *rest]
    return subprocess.run(argv, cwd=ROOT, env=env).returncode


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd!r}\n", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        return 2
    return _dispatch(COMMANDS[cmd], rest)


if __name__ == "__main__":
    raise SystemExit(main())
