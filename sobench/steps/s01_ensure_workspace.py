"""
sobench/steps/s01_ensure_workspace.py

s01: Validate workspace directory and benchmark_intent.md exist.
Raises FileNotFoundError (not a blocker) if either is missing.
Writes nothing.
"""

from __future__ import annotations

from sobench.workspace import Workspace


def run(workspace: Workspace) -> None:
    """Verify workspace dir and benchmark_intent.md exist; raise if not."""
    if not workspace.dir.exists():
        raise FileNotFoundError(
            f"Workspace directory does not exist: {workspace.dir}"
        )

    intent_path = workspace.dir / "benchmark_intent.md"
    if not intent_path.exists():
        raise FileNotFoundError(
            f"benchmark_intent.md not found in workspace: {intent_path}"
        )
