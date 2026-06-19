"""
sobench/steps/s04_inspect_repo_evidence.py

s04: Walk repo directory, collect key file listing + contents, extract evidence via LLM.
Writes repo_evidence.json.

NEVER sets a blocker — missing repo is a risk (recorded in missing field), not a cycle blocker.

Repo input bounds:
  - File listing: up to 60 files (relative paths only, sorted)
  - Key file contents (README, setup.py, requirements*.txt, *.py entry scripts):
    up to 3000 chars per file, up to 5 key files total
  - Total context sent to LLM: bounded by these limits (~20K chars max)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from sobench.workspace import Workspace
from sobench.models import ParsedIntent, RepoEvidence
from sobench.steps._common import llm_json

_STEP_NAME = "s04_inspect_repo_evidence"

# Bounds on repo context sent to LLM
_MAX_FILE_LISTING = 60          # number of file paths to list
_MAX_KEY_FILES = 5              # number of key files to include content for
_MAX_CONTENT_CHARS = 3000       # chars per key file

# File patterns considered "key" for initial inspection
_KEY_FILE_PATTERNS = (
    "README*",
    "readme*",
    "setup.py",
    "requirements*.txt",
    "requirement*.txt",
    "*.cfg",
    "*.toml",
    "environment*.yml",
    "*.sh",
)

# Python entry-script patterns (tried after key file patterns)
_ENTRY_PATTERNS = ("run_*.py", "train_*.py", "main.py", "cli.py", "__main__.py")

_SYSTEM = (
    "You are a precise JSON extractor for software repositories. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
Inspect this repository and extract evidence about how the benchmark code works.
Return ONLY a JSON object with exactly these keys:

{{
  "task": "<spatial-omics task name>",
  "method": "<method name>",
  "entry_points": ["<file that runs the method>"],
  "dependencies": {{"python": "<version if found>", "packages": ["<pkg==version>"]}},
  "hardcoded_paths": ["<hardcoded data path found in code>"],
  "metric_implementations": [
    {{"name": "<metric>", "file": "<file>", "line": <line_number_or_null>, "matches_paper": true}}
  ],
  "deviations_from_paper": ["<deviation found>"],
  "coordinate_evidence": "<how repo handles spatial coordinates>",
  "coordinate_open_questions": ["<question>"],
  "ambiguities": ["<ambiguity>"],
  "missing": ["<information not found or absent>"]
}}

Task: {task}
Method: {method}
Repo path: {repo_path}

File listing ({n_files} files shown):
{file_listing}

Key file contents:
{key_contents}
"""


def _collect_file_listing(repo: Path) -> List[str]:
    """Return sorted relative paths of all files (up to _MAX_FILE_LISTING)."""
    paths = []
    for p in sorted(repo.rglob("*")):
        if p.is_file() and "__pycache__" not in str(p) and ".git" not in str(p):
            paths.append(str(p.relative_to(repo)))
            if len(paths) >= _MAX_FILE_LISTING:
                break
    return paths


def _collect_key_contents(repo: Path) -> List[Tuple[str, str]]:
    """
    Return (relative_path, content_excerpt) pairs for key files.
    Priority: README*, setup.py, requirements*.txt, entry scripts.
    Up to _MAX_KEY_FILES files, _MAX_CONTENT_CHARS per file.
    """
    seen: set[Path] = set()
    results: List[Tuple[str, str]] = []

    def _add(p: Path) -> None:
        if p in seen or not p.is_file():
            return
        seen.add(p)
        try:
            content = p.read_text(encoding="utf-8", errors="replace")[:_MAX_CONTENT_CHARS]
        except Exception:
            content = "<unreadable>"
        results.append((str(p.relative_to(repo)), content))

    # Key config / doc files
    for pattern in _KEY_FILE_PATTERNS:
        for p in sorted(repo.glob(pattern)):
            if len(results) >= _MAX_KEY_FILES:
                return results
            _add(p)

    # Entry scripts
    for pattern in _ENTRY_PATTERNS:
        for p in sorted(repo.rglob(pattern)):
            if len(results) >= _MAX_KEY_FILES:
                return results
            _add(p)

    return results


def run(workspace: Workspace) -> None:
    """Inspect repo and write repo_evidence.json. Never sets a blocker."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)

    repo_path_str = pi.repo_path.strip()
    repo_path = Path(repo_path_str) if repo_path_str else None

    # Check if repo is accessible
    if not repo_path or not repo_path.exists():
        missing_desc = (
            "repo_path is empty"
            if not repo_path_str
            else f"repo path does not exist: {repo_path}"
        )
        re = RepoEvidence(
            task=pi.task,
            method=pi.method,
            entry_points=[],
            dependencies={},
            hardcoded_paths=[],
            metric_implementations=[],
            deviations_from_paper=[],
            coordinate_evidence="",
            coordinate_open_questions=[],
            ambiguities=[],
            missing=[f"repository not accessible: {missing_desc}"],
        )
        workspace.write_artifact("repo_evidence", re)
        # NEVER set blocker — missing repo is a risk, not a cycle blocker
        return

    # Collect repo context
    file_listing = _collect_file_listing(repo_path)
    key_contents = _collect_key_contents(repo_path)

    file_listing_text = "\n".join(file_listing) if file_listing else "(empty repository)"
    key_contents_text = ""
    for rel_path, content in key_contents:
        key_contents_text += f"\n--- {rel_path} ---\n{content}\n"

    if not key_contents_text:
        key_contents_text = "(no key files found)"

    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        repo_path=str(repo_path),
        n_files=len(file_listing),
        file_listing=file_listing_text,
        key_contents=key_contents_text,
    )
    data = llm_json(prompt, system=_SYSTEM)

    re = RepoEvidence(
        task=data.get("task", pi.task),
        method=data.get("method", pi.method),
        entry_points=data.get("entry_points", []),
        dependencies=data.get("dependencies", {}),
        hardcoded_paths=data.get("hardcoded_paths", []),
        metric_implementations=data.get("metric_implementations", []),
        deviations_from_paper=data.get("deviations_from_paper", []),
        coordinate_evidence=data.get("coordinate_evidence", ""),
        coordinate_open_questions=data.get("coordinate_open_questions", []),
        ambiguities=data.get("ambiguities", []),
        missing=data.get("missing", []),
    )

    workspace.write_artifact("repo_evidence", re)
    # NEVER set blocker from s04
