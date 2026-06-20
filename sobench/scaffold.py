"""
sobench/scaffold.py — write the project skeleton + fixed run_benchmark.py (spec §9).

The agent fills in drafts, data_adapter.py, and per-method driver/env files. The
scaffold owns only the directory tree and the fixed run_benchmark.py entrypoint,
which the agent must never modify: it loads frozen contracts and delegates all
orchestration to sobench.runner. No method-specific logic lives here.
"""

from __future__ import annotations

from pathlib import Path

# Fixed thin entrypoint. Resolves the repo root (the dir containing the `sobench`
# package) and puts it on sys.path so `import sobench.runner` works no matter the
# cwd. The runner + metrics run under THIS (dev) interpreter; only the per-method
# driver subprocess runs under the method's conda interpreter (env_record.json).
_RUN_BENCHMARK_TEMPLATE = '''\
#!/usr/bin/env python
"""run_benchmark.py — fixed thin entrypoint written by `sobench scaffold`.

DO NOT EDIT. All orchestration lives in sobench.runner. This file only locates
the sobench package, loads the frozen contracts (implicitly, via the runner),
and runs the benchmark for this project directory.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent


def _find_repo_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / "sobench" / "__init__.py").exists():
            return parent
    raise RuntimeError("could not locate the sobench package above " + str(start))


def main() -> int:
    repo_root = _find_repo_root(PROJECT_DIR)
    sys.path.insert(0, str(repo_root))

    from sobench.runner import run

    records = run(PROJECT_DIR)
    print(f"wrote {len(records)} BenchRecord(s) for {PROJECT_DIR.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def scaffold(project_dir: str | Path, task: str = "spatial_domain_identification") -> Path:
    """Create the project tree and write the fixed run_benchmark.py. Idempotent."""
    project_dir = Path(project_dir)
    (project_dir / "methods").mkdir(parents=True, exist_ok=True)
    (project_dir / "results").mkdir(parents=True, exist_ok=True)
    (project_dir / "run_benchmark.py").write_text(_RUN_BENCHMARK_TEMPLATE, encoding="utf-8")
    return project_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry: python -m sobench.scaffold --project-dir <p> [--task <name>]."""
    import argparse

    ap = argparse.ArgumentParser(prog="sobench.scaffold")
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--task", default="spatial_domain_identification")
    args = ap.parse_args(argv)
    proj = scaffold(args.project_dir, args.task)
    print(f"scaffolded {proj}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
