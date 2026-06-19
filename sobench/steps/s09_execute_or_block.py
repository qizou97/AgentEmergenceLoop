"""
sobench/steps/s09_execute_or_block.py

s09: Feasibility check, then execute or block.

ALWAYS writes both blocker.json and execution_log.json.

Reads FIVE artifacts (all via workspace.read_artifact):
  task_spec, evaluation_contract, risk_audit, data_manifest, repo_evidence.
  repo_evidence is read specifically for entry_points (spec section 8),
  which resolves the "entry point known" feasibility criterion.

Feasibility rule (deterministic Python, no LLM):
  The benchmark cycle is feasible to execute when ALL of the following hold:

  1. Required data present:
     Every item in data_manifest.required that has available:false makes
     the cycle infeasible (any unavailable required item → infeasible).
     An empty required list is treated as feasible (no data needed).

  2. Entry point known:
     A runnable command is derived primarily from repo_evidence.entry_points
     (e.g. the first entry point — a .py → "python <entry>",
     a .sh → "bash <entry>"). Falls back to a task_spec heuristic only if
     repo_evidence yields nothing. If no command can be derived, infeasible.

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
import shlex
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
    RepoEvidence,
    RiskAudit,
    TaskSpec,
)
from sobench.steps._common import set_blocker

_STEP_NAME = "s09_execute_or_block"

# Maximum length of captured stdout / stderr excerpt stored in execution_log.
_EXCERPT_MAX = 4096

# Subprocess timeout in seconds (10 minutes — spatial-omics pipelines can be slow).
_SUBPROCESS_TIMEOUT = 600

# Maximum number of output files to collect (avoids listing huge trees).
_OUTPUT_FILES_CAP = 200


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
# Command derivation
# ---------------------------------------------------------------------------

def _derive_command_from_repo_evidence(repo_evidence: RepoEvidence) -> str:
    """
    Derive a runnable command from repo_evidence.entry_points.

    Takes the first entry point that ends with .py or .sh:
      - .py  → "python <entry>"
      - .sh  → "bash <entry>"
    Returns empty string if nothing usable is found.
    """
    for entry in repo_evidence.entry_points:
        if not isinstance(entry, str):
            continue
        ep = entry.strip()
        if ep.endswith(".py"):
            return f"python {ep}"
        if ep.endswith(".sh"):
            return f"bash {ep}"
    return ""


def _derive_command_from_task_spec(task_spec: TaskSpec) -> str:
    """
    Fallback: derive a command from task_spec text fields.

    Scans input_description, assumptions, and unresolved for .py/.sh references.
    This is intentionally conservative: unknown commands should not run.
    """
    sources = (
        [task_spec.input_description]
        + list(task_spec.assumptions)
        + list(task_spec.unresolved)
    )
    for text in sources:
        if not isinstance(text, str):
            continue
        for word in text.split():
            stripped = word.strip(".,;:\"'()")
            if stripped.endswith(".py"):
                return f"python {stripped}"
            if stripped.endswith(".sh"):
                return f"bash {stripped}"
    return ""


def _derive_command(task_spec: TaskSpec, repo_evidence: RepoEvidence) -> str:
    """
    Derive an entry-point command.

    Primary: repo_evidence.entry_points (spec section 8 — entry_points are
    extracted by s04 into repo_evidence).
    Fallback: task_spec text heuristic.
    Returns empty string if nothing is found.
    """
    cmd = _derive_command_from_repo_evidence(repo_evidence)
    if cmd:
        return cmd
    return _derive_command_from_task_spec(task_spec)


# ---------------------------------------------------------------------------
# Feasibility check
# ---------------------------------------------------------------------------

def _check_feasibility(
    dm: DataManifest,
    task_spec: TaskSpec,
    ec: EvaluationContract,
    ra: RiskAudit,
    repo_evidence: RepoEvidence,
) -> tuple[bool, str, str, str, str]:
    """
    Deterministic feasibility check.

    Returns (feasible, reason, detail, evidence, command) where
    reason/detail/evidence are populated only when infeasible, and command
    is the derived entry-point (non-empty iff feasible on that criterion).
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
            "",
        )

    # Rule 2: entry point known
    command = _derive_command(task_spec, repo_evidence)
    if not command:
        return (
            False,
            "no entry point command known",
            "Could not determine a runnable entry-point command from repo_evidence or task_spec",
            "repo_evidence.entry_points empty or unrecognised; no .py/.sh in task_spec fields",
            "",
        )

    # Rule 3: no unresolved blocker risks
    if ra.blocker_risk_ids:
        ids = ", ".join(ra.blocker_risk_ids)
        return (
            False,
            "unresolved high-severity blocker risks",
            f"risk_audit.blocker_risk_ids is non-empty: [{ids}]",
            f"risk_audit.blocker_risk_ids=[{ids}]",
            command,
        )

    return (True, "", "", "", command)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(workspace: Workspace) -> None:
    """
    s09: Feasibility check → execute or block.

    Reads: task_spec.json, evaluation_contract.json, risk_audit.json,
           data_manifest.json, repo_evidence.json (all via workspace.read_artifact).
    Always writes: blocker.json, execution_log.json.

    Guard: if an upstream step has already set blocked:true in blocker.json,
    preserve it and write execution_log with status="not_attempted". Do not
    overwrite the upstream blocker or launch a subprocess.
    """
    # Guard: respect an upstream blocker raised before s09 runs.
    existing_blocker = workspace.read_blocker()
    if existing_blocker is not None and existing_blocker.blocked:
        # Preserve blocker.json as-is; do not overwrite it.
        _write_not_attempted(workspace, "")
        return

    task_spec = workspace.read_artifact("task_spec", TaskSpec)
    ec = workspace.read_artifact("evaluation_contract", EvaluationContract)
    ra = workspace.read_artifact("risk_audit", RiskAudit)
    dm = workspace.read_artifact("data_manifest", DataManifest)
    repo_evidence = workspace.read_artifact("repo_evidence", RepoEvidence)

    feasible, reason, detail, evidence, command = _check_feasibility(
        dm, task_spec, ec, ra, repo_evidence
    )

    if not feasible:
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
        _write_not_attempted(workspace, command)
        return

    # Feasible path: write blocker.json with blocked:false
    _clear_blocker(workspace)

    # Parse the command safely — no shell=True
    args = shlex.split(command)
    if not args:
        # Defensive: should never happen because _check_feasibility already
        # verifies the command is non-empty before reaching here.
        set_blocker(
            workspace,
            raised_by_step=_STEP_NAME,
            reason="no entry point command known",
            detail="shlex.split yielded empty args from derived command",
            evidence=f"command={command!r}",
            resolution="Inspect repo_evidence.entry_points and task_spec fields.",
            human_action_required=True,
        )
        _write_not_attempted(workspace, command)
        return

    start = time.monotonic()
    try:
        result = subprocess.run(
            args,
            shell=False,
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
        stdout_excerpt = _truncate(exc.stdout if isinstance(exc.stdout, str) else "")
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
    Searches recursively; capped at _OUTPUT_FILES_CAP entries.
    """
    try:
        files = []
        for p in sorted(workspace.dir.rglob("*")):
            if p.is_file() and not p.name.endswith(".json"):
                files.append(str(p.relative_to(workspace.dir)))
                if len(files) >= _OUTPUT_FILES_CAP:
                    break  # cap: avoid listing thousands of files
        return files
    except OSError:
        return []
