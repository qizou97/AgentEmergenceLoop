"""
sobench/steps/s05_build_data_manifest.py

s05: Enumerate required data roles via LLM, check each expected_path with
Path.exists() directly in Python, write data_manifest.json.

NEVER sets a blocker — missing data is recorded here; the blocking decision
is made later at s09.

Path availability check:
  - expected_path is resolved relative to the repo root (cwd).
  - null / empty expected_path → available: false (no check needed).
"""

from __future__ import annotations

import json as _json
from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import ParsedIntent, PaperEvidence, RepoEvidence, DataManifest
from sobench.steps._common import llm_json

_STEP_NAME = "s05_build_data_manifest"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark construction. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
You are building a data manifest for a spatial-omics benchmark reconstruction.

Given the evidence below, enumerate all data files/objects required to run this
benchmark. For each required item, infer the most likely expected_path relative
to the repository root (e.g. "data/DLPFC/151673.h5ad") — use paths that match
what is referenced in the repo code and paper. If the path is genuinely unknown,
use null.

Return ONLY a JSON object with exactly these keys:

{{
  "task": "{task}",
  "method": "{method}",
  "case": "{case}",
  "required": [
    {{
      "role": "<role name, e.g. expression_matrix_with_coords>",
      "format": "<file format, e.g. AnnData .h5ad>",
      "expected_path": "<relative path from repo root, or null if unknown>",
      "available": false,
      "notes": "<notes about this data item>"
    }}
  ],
  "coordinate_evidence": "<how coordinates are represented based on evidence>",
  "coordinate_assumptions": "<any assumptions made about coordinate space>",
  "coordinate_open_questions": ["<unanswered coordinate question>"],
  "coordinate_checks": [],
  "open_questions": ["<open question about data>"]
}}

IMPORTANT:
- Set available: false for ALL items — availability will be verified separately.
- expected_path MUST use real paths referenced in the repo hardcoded_paths or
  paper evidence, NOT invented paths. If you see "./data/DLPFC/" in the repo,
  infer "data/DLPFC/151673.h5ad" for a DLPFC 151673 .h5ad file.
- Enumerate ALL distinct data requirements (expression matrix, ground truth
  labels, spatial coordinates file if separate, etc.).

Task: {task}
Method: {method}
Case: {case}

Paper evidence:
{paper_evidence_json}

Repo evidence:
{repo_evidence_json}

Parsed intent:
{parsed_intent_json}
"""


def run(workspace: Workspace) -> None:
    """Enumerate data roles via LLM, check availability via Path.exists(), write data_manifest.json."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)
    pe = workspace.read_artifact("paper_evidence", PaperEvidence)
    re = workspace.read_artifact("repo_evidence", RepoEvidence)

    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        case=pi.case,
        paper_evidence_json=_json.dumps(pe.to_dict(), indent=2),
        repo_evidence_json=_json.dumps(re.to_dict(), indent=2),
        parsed_intent_json=_json.dumps(pi.to_dict(), indent=2),
    )

    data = llm_json(prompt, system=_SYSTEM)

    # Resolve identity fields (fall back to workspace if LLM returns empty)
    task = data.get("task") or pi.task
    method = data.get("method") or pi.method
    case = data.get("case") or pi.case

    # Apply real Path.exists() check to each required item
    required_raw = data.get("required", [])
    required: list = []
    for item in required_raw:
        ep = item.get("expected_path") or ""
        if ep:
            available = Path(ep).exists()
        else:
            available = False
        required.append({
            "role": item.get("role", ""),
            "format": item.get("format", ""),
            "expected_path": item.get("expected_path"),
            "available": available,
            "notes": item.get("notes", ""),
        })

    dm = DataManifest(
        task=task,
        method=method,
        case=case,
        required=required,
        coordinate_evidence=data.get("coordinate_evidence", ""),
        coordinate_assumptions=data.get("coordinate_assumptions", ""),
        coordinate_open_questions=data.get("coordinate_open_questions", []),
        coordinate_checks=data.get("coordinate_checks", []),
        open_questions=data.get("open_questions", []),
    )

    workspace.write_artifact("data_manifest", dm)
    # NEVER set a blocker from s05 — blocking decision is at s09
