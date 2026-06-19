"""
sobench/cli.py — argparse CLI with four subcommands.

Subcommands:
  scaffold  — creates workspace directory and writes benchmark_intent.md
  run       — execute all 14 benchmark steps for a workspace
  check     — run s14 structural check standalone against an existing workspace
  report    — print human-readable summary from completed workspace artifacts

Usage:
  python -m sobench scaffold --task T --method M --case C [--root R] [--paper P] [--repo R] [--data D]
  python -m sobench run     --task T --method M --case C [--root R]
  python -m sobench check   --task T --method M --case C [--root R]
  python -m sobench report  --task T --method M --case C [--root R]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from sobench.workspace import Workspace
from sobench.models import ExperienceRecord, StructuralCheck

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_INTENT_TEMPLATE = """\
## Task
{task}

## Method
{method}

## Case
{case}

## Paper
{paper_section}

## Repository
{repo_section}

## Data
{data_section}

## What to reconstruct
Reproduce the {task} result on {case} as reported
in the paper, using the primary metric if evidence supports it.

## Human observations
(fill in after run, or add any prior knowledge to guide reconstruction)
"""


def _build_section(path_value: Optional[str]) -> str:
    """Return a section body with a path: convenience line (if path given)."""
    if path_value:
        return f"path: {path_value}\nnotes: (fill in)"
    return "notes: (fill in)"


# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------

def _cmd_scaffold(args: argparse.Namespace) -> int:
    ws = Workspace(
        task=args.task,
        method=args.method,
        case=args.case,
        root=args.root,
    )

    if ws.dir.exists():
        print(
            f"error: workspace already exists: {ws.dir}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    ws.dir.mkdir(parents=True, exist_ok=False)

    intent_content = _INTENT_TEMPLATE.format(
        task=args.task,
        method=args.method,
        case=args.case,
        paper_section=_build_section(args.paper),
        repo_section=_build_section(args.repo),
        data_section=_build_section(args.data),
    )

    intent_path = ws.dir / "benchmark_intent.md"
    intent_path.write_text(intent_content, encoding="utf-8")

    print(f"Scaffolded workspace: {ws.dir}")
    print(f"  benchmark_intent.md written to: {intent_path}")
    return 0


# ---------------------------------------------------------------------------
# run / check / report
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace) -> int:
    """Execute all 14 steps for the given workspace via runner.run()."""
    from sobench import runner

    ws = Workspace(task=args.task, method=args.method, case=args.case, root=args.root)
    executed = runner.run(ws)

    skipped = [name for name, _ in runner.STEPS if name not in executed]
    print(f"Run complete: {args.task}/{args.case}/{args.method}")
    print(f"  Steps executed ({len(executed)}): {', '.join(executed)}")
    if skipped:
        print(f"  Steps skipped ({len(skipped)}): {', '.join(skipped)}")
    if ws.blocked:
        blocker = ws.read_blocker()
        print(f"  Blocked: {blocker.reason}")
    else:
        print("  Blocked: False")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    """Run s14 structural check standalone against an existing workspace."""
    from sobench.steps import s14_structural_check

    ws = Workspace(task=args.task, method=args.method, case=args.case, root=args.root)
    s14_structural_check.run(ws)

    sc_path = ws.artifact_path("structural_check")
    if not sc_path.exists():
        print("error: structural_check.json was not written", file=sys.stderr)
        return 1

    sc = ws.read_artifact("structural_check", StructuralCheck)
    status = "PASSED" if sc.passed else "FAILED"
    print(f"Structural check {status}: {args.task}/{args.case}/{args.method}")
    if sc.missing_unacknowledged:
        print(f"  Missing unacknowledged: {', '.join(sc.missing_unacknowledged)}")
    else:
        print("  Missing unacknowledged: none")
    if sc.warnings:
        for w in sc.warnings:
            print(f"  Warning: {w}")
    return 0 if sc.passed else 1


def _cmd_report(args: argparse.Namespace) -> int:
    """Print a human-readable summary from completed workspace artifacts."""
    ws = Workspace(task=args.task, method=args.method, case=args.case, root=args.root)

    sc_path = ws.artifact_path("structural_check")
    exp_path = ws.artifact_path("experience_record")

    if not sc_path.exists() or not exp_path.exists():
        missing = []
        if not sc_path.exists():
            missing.append("structural_check.json")
        if not exp_path.exists():
            missing.append("experience_record.json")
        print(
            f"error: required artifacts not found in {ws.dir}: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1

    sc = ws.read_artifact("structural_check", StructuralCheck)
    exp = ws.read_artifact("experience_record", ExperienceRecord)

    print(f"Report: {args.task}/{args.case}/{args.method}")
    print(f"  passed:                   {sc.passed}")
    print(f"  completed_with_blocker:   {sc.completed_with_blocker}")
    print(f"  execution_attempted:      {sc.execution_attempted}")
    print(f"  benchmark_result_claimed: {sc.benchmark_result_claimed}")
    print(f"  experience finding:       {exp.finding}")
    print(f"  experience status:        {exp.status}")
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sobench",
        description="Evidence-guided spatial-omics benchmark construction.",
    )
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = True

    # common identity args shared by all subcommands
    def _add_identity(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--task", required=True, help="Benchmark task name")
        sp.add_argument("--method", required=True, help="Method name")
        sp.add_argument("--case", required=True, help="Case identifier")
        sp.add_argument(
            "--root",
            default="workspaces",
            help="Workspace root directory (default: workspaces)",
        )

    # scaffold
    p_scaffold = subparsers.add_parser(
        "scaffold",
        help="Create workspace directory and write benchmark_intent.md template.",
    )
    _add_identity(p_scaffold)
    p_scaffold.add_argument(
        "--paper",
        default=None,
        metavar="PATH",
        help="Optional path to paper PDF; populates convenience line in template.",
    )
    p_scaffold.add_argument(
        "--repo",
        default=None,
        metavar="PATH",
        help="Optional path to method repository; populates convenience line in template.",
    )
    p_scaffold.add_argument(
        "--data",
        default=None,
        metavar="PATH",
        help="Optional path to data directory; populates convenience line in template.",
    )
    p_scaffold.set_defaults(func=_cmd_scaffold)

    # run
    p_run = subparsers.add_parser(
        "run",
        help="Execute all 14 benchmark steps for the specified workspace.",
    )
    _add_identity(p_run)
    p_run.set_defaults(func=_cmd_run)

    # check
    p_check = subparsers.add_parser(
        "check",
        help="Run structural check (s14) standalone against an existing workspace.",
    )
    _add_identity(p_check)
    p_check.set_defaults(func=_cmd_check)

    # report
    p_report = subparsers.add_parser(
        "report",
        help="Print human-readable summary from completed workspace artifacts.",
    )
    _add_identity(p_report)
    p_report.set_defaults(func=_cmd_report)

    return parser


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    """Parse args and dispatch to the appropriate subcommand handler.

    Returns an integer exit code. Callers should pass it to sys.exit().
    Raises SystemExit directly for error conditions (e.g. workspace exists).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
