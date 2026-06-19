"""
sobench/steps/s03_extract_paper_evidence.py

s03: Read paper PDF, extract evidence via LLM, write paper_evidence.json.

PDF input bound: first 8000 chars of extracted text (covers ~4–6 pages of a
typical methods paper, enough for metrics, evaluation contexts, and coordinates).

Sets blocker if paper_path is absent or unreadable.
Always writes paper_evidence.json — with missing populated on failure.
"""

from __future__ import annotations

from pathlib import Path

from sobench.workspace import Workspace
from sobench.models import ParsedIntent, PaperEvidence
from sobench.steps._common import llm_json, set_blocker

_STEP_NAME = "s03_extract_paper_evidence"

# Bound: first N chars of PDF text sent to LLM (~4–6 pages for typical paper)
_PDF_TEXT_LIMIT = 8000

_SYSTEM = (
    "You are a precise JSON extractor for scientific papers. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

_PROMPT_TEMPLATE = """\
Extract benchmark evidence from the paper text below.
Return ONLY a JSON object with exactly these keys:

{{
  "task": "<spatial-omics task name>",
  "method": "<method name>",
  "source": "<PDF filename>",
  "evaluation_contexts": [
    {{
      "id": "ctx-001",
      "task": "<task>",
      "cases": ["<case ids>"],
      "metrics": [
        {{"name": "<metric>", "confidence": "high|medium|low", "quote": "<exact quote>"}}
      ],
      "downstream_tasks": [],
      "notes": "<any notes>"
    }}
  ],
  "coordinate_evidence": "<how the paper uses spatial coordinates>",
  "coordinate_open_questions": ["<question>"],
  "ambiguities": ["<ambiguity>"],
  "missing": ["<information not found in paper>"]
}}

Task: {task}
Method: {method}

Paper text (first {limit} chars):
---
{text}
---
"""


def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF using pypdf; return first _PDF_TEXT_LIMIT chars."""
    import pypdf  # installed per requirements

    reader = pypdf.PdfReader(str(pdf_path))
    parts = []
    total = 0
    for page in reader.pages:
        chunk = page.extract_text() or ""
        parts.append(chunk)
        total += len(chunk)
        if total >= _PDF_TEXT_LIMIT:
            break
    return "".join(parts)[:_PDF_TEXT_LIMIT]


def run(workspace: Workspace) -> None:
    """Extract paper evidence and write paper_evidence.json."""
    pi = workspace.read_artifact("parsed_intent", ParsedIntent)

    paper_path_str = pi.paper_path.strip()
    paper_path = Path(paper_path_str) if paper_path_str else None
    source_name = paper_path.name if paper_path else ""

    # Attempt to extract PDF text
    pdf_text: str | None = None
    error_detail: str | None = None

    if not paper_path or not paper_path.exists():
        error_detail = (
            f"Paper path {'is empty' if not paper_path_str else f'does not exist: {paper_path}'}"
        )
    else:
        try:
            pdf_text = _extract_pdf_text(paper_path)
        except Exception as exc:
            error_detail = f"Failed to read PDF at {paper_path}: {exc}"

    if error_detail is not None:
        # Write paper_evidence with missing populated; then set blocker
        pe = PaperEvidence(
            task=pi.task,
            method=pi.method,
            source=source_name,
            evaluation_contexts=[],
            coordinate_evidence="",
            coordinate_open_questions=[],
            ambiguities=[],
            missing=[f"paper not readable: {error_detail}"],
        )
        workspace.write_artifact("paper_evidence", pe)
        set_blocker(
            workspace,
            raised_by_step=_STEP_NAME,
            reason="Paper path absent or unreadable",
            detail=error_detail,
            evidence="parsed_intent.paper_path",
            resolution=(
                "Provide a valid path to the paper PDF in benchmark_intent.md "
                "under the ## Paper section."
            ),
            human_action_required=True,
        )
        return

    # LLM extraction
    prompt = _PROMPT_TEMPLATE.format(
        task=pi.task,
        method=pi.method,
        limit=_PDF_TEXT_LIMIT,
        text=pdf_text,
    )
    data = llm_json(prompt, system=_SYSTEM)

    pe = PaperEvidence(
        task=data.get("task", pi.task) or pi.task,
        method=data.get("method", pi.method) or pi.method,
        source=data.get("source", source_name) or source_name,
        evaluation_contexts=data.get("evaluation_contexts", []),
        coordinate_evidence=data.get("coordinate_evidence", ""),
        coordinate_open_questions=data.get("coordinate_open_questions", []),
        ambiguities=data.get("ambiguities", []),
        missing=data.get("missing", []),
    )

    workspace.write_artifact("paper_evidence", pe)
