"""
sobench/atomicio.py — atomic JSON writes.

Every substrate artifact (frozen contracts, freeze_report, driver_record,
BenchRecord, experience entries) is written atomically: a temp file in the SAME
directory, then os.replace (atomic on POSIX). A crash mid-write never leaves a
half-written artifact, and a reader never observes one. Shared because the same
guarantee is needed in several modules.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_json_atomic(path: str | os.PathLike, obj: Any, *, indent: int = 2) -> Path:
    """Serialize ``obj`` to ``path`` atomically. Returns the written path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=indent, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except BaseException:
        # Best-effort cleanup; never leave a stray .tmp on failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
