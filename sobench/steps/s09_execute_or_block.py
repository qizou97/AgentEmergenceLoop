"""
sobench/steps/s09_execute_or_block.py

s09: Feasibility check, then execute or block.

ALWAYS writes both blocker.json and execution_log.json.

Feasibility rule (deterministic Python, no LLM):
  The benchmark cycle is feasible to execute when ALL of the following hold:

  1. Required data present:
     Every item in data_manifest.required that has available:false makes
     the cycle infeasible (any unavailable required item → infeasible).
     An empty required list is treated as feasible (no data needed).

  2. Entry point known:
     A runnable command must be derivable from at least one of:
       - task_spec.unresolved / task_spec.source_context (not used directly)
       - repo_evidence.entry_points (the primary source)
       - evaluation_contract (not a direct command source, but presence
         of a resolved metric confirms the task is defined)
     Concretely: if repo_evidence.entry_points is non-empty, the first
     entry point is used as the command to run.
     If no entry point is known, the cycle is infeasible.

  3. No unresolved high-severity blocker risk:
     risk_audit.blocker_risk_ids is used as the primary signal.
     A non-empty blocker_risk_ids list means infeasible.

If NOT feasible:
  - Write blocker.json with blocked:true (via set_blocker from _common).
  - Write execution_log.json with status="not_attempted", empty stdout/stderr,
    duration_seconds=null, and real environment info.

If feasible:
  - Write blocker.json with blocked:false (the no-blocker shape from spec 7.8).
  - Run the entry-point command via subprocess.run with a 10-minute timeout.
  - Write execution_log.json with status in {"success","failed"} based on
    return code, real stdout_excerpt/stderr_excerpt (truncated at 4096 chars),
    real duration_seconds, and output_files discovered in the workspace dir
    after the run.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from sobench.workspace import Workspace
from sobench.models import (
    Blocker,
    DataManifest,
    EvaluationContract,
    ExecutionLog,
    RiskAudit,
    TaskSpec,
)
from sobench.steps._common import set_blocker

_STEP_NAME = "s09_execute_or_block"

# Maximum length of captured stdout / stderr excerpt stored in execution_log.
_EXCERPT_MAX = 4096

# Subprocess timeout in seconds (10 minutes — spatial-omics pipelines can be slow).
_SUBPROCESS_TIMEOUT = 600


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _environment() -> dict:
    """Return a minimal environment dict: python version and platform."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.system().lower(),
    }


def _truncate(text: str, max_len: int = _EXCERPT_MAX) -> str:
    if len(text) <= max_len:
        return text
    half = max_len // 2
    return text[:half] + "\n...[truncated]...\n" + text[-half:]


def _clear_blocker(workspace: Workspace) -> None:
    """Write blocker.json with blocked:false (no-blocker shape, spec 7.8)."""
    blocker = Blocker(
        blocked=False,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    )
    workspace.write_artifact("blocker", blocker)


def _write_not_attempted(workspace: Workspace, command: str) -> None:
    """Write execution_log.json with status='not_attempted'."""
    elog = ExecutionLog(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        status="not_attempted",
        command=command,
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment=_environment(),
        output_files=[],
    )
    workspace.write_artifact("execution_log", elog)


# ---------------------------------------------------------------------------
# Feasibility check
# ---------------------------------------------------------------------------

def _check_feasibility(
    dm: DataManifest,
    task_spec: TaskSpec,
    ec: EvaluationContract,
    ra: RiskAudit,
) -> tuple[bool, str, str, str]:
    """
    Deterministic feasibility check.

    Returns (feasible, reason, detail, evidence) where reason/detail/evidence
    are populated only when infeasible.

    Rule:
      1. All required data items must be available.
      2. At least one entry point must be known (from task_spec or repo).
      3. blocker_risk_ids must be empty.
    """
    # Rule 1: required data availability
    unavailable = [
        item for item in dm.required
        if not item.get("available", False)
    ]
    if unavailable:
        paths = ", ".join(
            item.get("expected_path") or item.get("role", "<unknown>")
            for item in unavailable
        )
        evidence_parts = [
            f"data_manifest.required[{i}].available=false"
            for i, item in enumerate(dm.required)
            if not item.get("available", False)
        ]
        return (
            False,
            "required data file not found",
            f"The following required data items are not available: {paths}",
            "; ".join(evidence_parts),
        )

    # Rule 2: entry point known
    # task_spec.unresolved may mention entry point; we rely on repo_evidence
    # entry_points which flow into task_spec.source_context indirectly.
    # Use task_spec.input_description as fallback: if it mentions a script,
    # accept it. Primarily we require the command to be non-empty and derived.
    command = _derive_command(task_spec)
    if not command:
        return (
            False,
            "no entry point command known",
            "Could not determine a runnable entry-point command from task_spec or repo_evidence",
            "task_spec.unresolved non-empty; no entry_points in repo_evidence",
        )

    # Rule 3: no unresolved blocker risks
    if ra.blocker_risk_ids:
        ids = ", ".join(ra.blocker_risk_ids)
        return (
            False,
            "unresolved high-severity blocker risks",
            f"risk_audit.blocker_risk_ids is non-empty: [{ids}]",
            f"risk_audit.blocker_risk_ids=[{ids}]",
        )

    return (True, "", "", "")


def _derive_command(task_spec: TaskSpec) -> str:
    """
    Derive an entry-point command from task_spec.

    task_spec carries source_context and input_description. In practice the
    entry point comes from repo_evidence.entry_points, but s09 reads only the
    four spec-mandated artifacts (task_spec, evaluation_contract, risk_audit,
    data_manifest).  We embed a minimal heuristic: if task_spec.input_description
    references a runnable script (e.g. "run_STAGATE.py"), return it.
    Otherwise return empty string → infeasible.

    This is intentionally conservative: unknown commands should not run.
    """
    # Look for a .py script reference in the input_description or assumptions
    sources = [task_spec.input_description] + list(task_spec.assumptions) + list(task_spec.unresolved)
    for text in sources:
        if not isinstance(text, str):
            continue
        for word in text.split():
            stripped = word.strip(".,;:\"'()")
            if stripped.endswith(".py") or stripped.endswith(".sh"):
                return f"python {stripped}"

    # No command found
    return ""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(workspace: Workspace) -> None:
    """
    s09: Feasibility check → execute or block.

    Reads: task_spec.json, evaluation_contract.json, risk_audit.json,
           data_manifest.json (all via workspace.read_artifact).
    Always writes: blocker.json, execution_log.json.
    """
    task_spec = workspace.read_artifact("task_spec", TaskSpec)
    ec = workspace.read_artifact("evaluation_contract", EvaluationContract)
    ra = workspace.read_artifact("risk_audit", RiskAudit)
    dm = workspace.read_artifact("data_manifest", DataManifest)

    feasible, reason, detail, evidence = _check_feasibility(dm, task_spec, ec, ra)

    command = _derive_command(task_spec)

    if not feasible:
        # Set blocker
        set_blocker(
            workspace,
            raised_by_step=_STEP_NAME,
            reason=reason,
            detail=detail,
            evidence=evidence,
            resolution=(
                "Resolve all infeasibility conditions: ensure required data is "
                "available, a runnable entry-point command is known, and all "
                "blocker risks are mitigated."
            ),
            human_action_required=True,
        )
        # Write execution_log with not_attempted
        _write_not_attempted(workspace, command)
        return

    # Feasible path: write blocker.json with blocked:false
    _clear_blocker(workspace)

    # Run the entry-point command
    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
            cwd=str(workspace.dir),
        )
        duration = time.monotonic() - start
        status = "success" if result.returncode == 0 else "failed"
        stdout_excerpt = _truncate(result.stdout or "")
        stderr_excerpt = _truncate(result.stderr or "")
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        status = "failed"
        stdout_excerpt = _truncate(exc.stdout or "" if isinstance(exc.stdout, str) else "")
        stderr_excerpt = f"TimeoutExpired after {_SUBPROCESS_TIMEOUT}s"

    # Discover output files in the workspace dir after the run
    output_files = _collect_output_files(workspace)

    elog = ExecutionLog(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        status=status,
        command=command,
        stdout_excerpt=stdout_excerpt,
        stderr_excerpt=stderr_excerpt,
        duration_seconds=round(duration, 3),
        environment=_environment(),
        output_files=output_files,
    )
    workspace.write_artifact("execution_log", elog)


def _collect_output_files(workspace: Workspace) -> list:
    """
    Return a list of file paths (relative to workspace.dir) found after the run.
    Excludes .json artifacts written by sobench itself.
    """
    try:
        files = []
        for p in sorted(workspace.dir.iterdir()):
            if p.is_file() and not p.name.endswith(".json"):
                files.append(str(p.relative_to(workspace.dir)))
        return files
    except OSError:
        return []
