"""
sobench/workspace.py — workspace path resolution, artifact I/O, blocked property.

Workspace dir layout: root/task/case/method/
Artifact files: <name>.json (e.g. paper_evidence.json)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Type, TypeVar

from sobench.models import Blocker

T = TypeVar("T")


class Workspace:
    """Resolve and manage a single task/method/case workspace."""

    def __init__(self, task: str, method: str, case: str, root: str = "workspaces") -> None:
        self.task = task
        self.method = method
        self.case = case
        self.root = Path(root)
        # spec section 3: root/task/case/method/
        self.dir = self.root / task / case / method

    def artifact_path(self, name: str) -> Path:
        """Return the Path for artifact <name> (appends .json)."""
        return self.dir / f"{name}.json"

    def write_artifact(self, name: str, obj) -> None:
        """Serialize obj.to_dict() to JSON under the workspace dir."""
        path = self.artifact_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj.to_dict(), indent=2), encoding="utf-8")

    def read_artifact(self, name: str, cls: Type[T]) -> T:
        """Load JSON from <name>.json and return cls.from_dict(...)."""
        path = self.artifact_path(name)
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(d)

    def read_blocker(self) -> Optional[Blocker]:
        """Return Blocker if blocker.json exists, else None."""
        path = self.artifact_path("blocker")
        if not path.exists():
            return None
        return self.read_artifact("blocker", Blocker)

    @property
    def blocked(self) -> bool:
        """True when blocker.json exists and has blocked: true."""
        b = self.read_blocker()
        if b is None:
            return False
        return b.blocked
