"""
sobench/steps/s10_record_raw_observations.py

s10: Record raw observations from execution output.

SKIP (return without writing) when workspace.blocked.

Otherwise:
  - Read execution_log.json
  - Read the output files listed therein (from workspace.dir)
  - Extract raw observations deterministically where possible:
      outputs_found, output_shape, stdout_summary, stderr_summary, anomalies_observed
  - Calls llm_json ONLY when the output file format or metric column is genuinely
    ambiguous (i.e. cannot be determined from file extension + header row alone)
  - Write raw_observations.json
"""

from __future__ import annotations

import csv
import io
import json as _json
from pathlib import Path
from typing import Optional

from sobench.workspace import Workspace
from sobench.models import ExecutionLog, RawObservations
from sobench.steps._common import llm_json

_STEP_NAME = "s10_record_raw_observations"

_SYSTEM = (
    "You are a precise JSON extractor for spatial-omics benchmark analysis. "
    "Return ONLY a valid JSON object — no prose, no markdown fences."
)

# Maximum bytes to read from an output file for inspection.
_FILE_READ_LIMIT = 65536  # 64 KiB


# ---------------------------------------------------------------------------
# Helpers — deterministic extraction
# ---------------------------------------------------------------------------

def _read_file_head(path: Path, limit: int = _FILE_READ_LIMIT) -> str:
    """Read up to *limit* bytes from *path*, return as UTF-8 string (lossy)."""
    try:
        raw = path.read_bytes()
        return raw[:limit].decode("utf-8", errors="replace")
    except OSError:
        return ""


def _csv_shape(content: str) -> dict:
    """
    Return {"rows": n, "columns": m} from CSV content string.
    rows = data rows (header excluded). Returns empty dict on parse error.
    """
    try:
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return {}
        # First row treated as header if it contains non-numeric items
        ncols = max(len(r) for r in rows) if rows else 0
        nrows = len(rows) - 1  # exclude header
        return {"rows": max(0, nrows), "columns": ncols}
    except Exception:
        return {}


def _detect_metric_deterministic(
    columns: list[str],
    stdout_summary: str,
) -> dict:
    """
    Attempt deterministic metric detection from column names and stdout.

    Returns {"name": ..., "value": ...} if confident, else empty dict.
    Looks for columns matching common spatial-omics metric names.
    """
    metric_col_names = {"ari", "nmi", "ami", "acc", "f1", "jaccard", "silhouette"}
    for col in columns:
        normalized = col.strip().lower().replace("-", "_")
        if normalized in metric_col_names:
            return {"name": col.strip(), "value": None}

    # Scan stdout for explicit metric values (e.g. "ARI=0.52" or "ARI: 0.52")
    import re
    pattern = re.compile(
        r"\b(ARI|NMI|AMI|ACC)\s*[=:]\s*([0-9]+(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    match = pattern.search(stdout_summary)
    if match:
        return {"name": match.group(1).upper(), "value": float(match.group(2))}

    return {}


def _summarize_text(text: str, max_chars: int = 500) -> str:
    """Return the text truncated to max_chars, stripped."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + " ...[truncated]... " + text[-half:]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(workspace: Workspace) -> None:
    """
    s10: Record raw observations from execution outputs.

    Skip silently when workspace.blocked.
    Read execution_log.json and output files; write raw_observations.json.
    """
    if workspace.blocked:
        return

    elog = workspace.read_artifact("execution_log", ExecutionLog)

    outputs_found: list[str] = list(elog.output_files)
    output_shape: dict = {}
    metric_raw: dict = {}
    anomalies_observed: list[str] = []
    stdout_summary = _summarize_text(elog.stdout_excerpt)
    stderr_summary = _summarize_text(elog.stderr_excerpt)

    # Try to extract shape and metric from the first CSV output file.
    first_csv_path: Optional[Path] = None
    first_csv_content: str = ""
    for rel_path in outputs_found:
        p = workspace.dir / rel_path
        if p.suffix.lower() == ".csv" and p.exists():
            first_csv_path = p
            first_csv_content = _read_file_head(p)
            break

    if first_csv_content:
        shape = _csv_shape(first_csv_content)
        if shape:
            output_shape = shape

        # Column names from header row
        try:
            reader = csv.reader(io.StringIO(first_csv_content))
            header = next(reader, [])
        except Exception:
            header = []

        metric_det = _detect_metric_deterministic(header, stdout_summary)
        if metric_det:
            metric_raw = metric_det

    # Detect anomalies deterministically
    if elog.stderr_excerpt.strip():
        anomalies_observed.append("stderr was non-empty during execution")
    if elog.status == "failed":
        anomalies_observed.append("execution exited with non-zero return code")

    # If metric_raw is still empty and the output is ambiguous, call LLM.
    if not metric_raw and (first_csv_content or elog.stdout_excerpt):
        prompt = _build_metric_prompt(
            task=workspace.task,
            method=workspace.method,
            case=workspace.case,
            stdout_excerpt=elog.stdout_excerpt,
            stderr_excerpt=elog.stderr_excerpt,
            output_files=outputs_found,
            first_csv_head=first_csv_content[:2000] if first_csv_content else "",
        )
        data = llm_json(prompt, system=_SYSTEM)
        metric_raw = data.get("metric_raw", {})
        # Also incorporate any anomalies the LLM flagged
        extra_anomalies = data.get("anomalies_observed", [])
        if isinstance(extra_anomalies, list):
            for a in extra_anomalies:
                if isinstance(a, str) and a not in anomalies_observed:
                    anomalies_observed.append(a)

    # Ensure metric_raw has at minimum {"name": ..., "value": ...}
    if not isinstance(metric_raw, dict) or "name" not in metric_raw:
        metric_raw = {"name": "", "value": None}

    ro = RawObservations(
        task=workspace.task,
        method=workspace.method,
        case=workspace.case,
        outputs_found=outputs_found,
        output_shape=output_shape,
        metric_raw=metric_raw,
        stdout_summary=stdout_summary,
        stderr_summary=stderr_summary,
        anomalies_observed=anomalies_observed,
    )
    workspace.write_artifact("raw_observations", ro)


# ---------------------------------------------------------------------------
# LLM prompt (only called when metric is ambiguous)
# ---------------------------------------------------------------------------

def _build_metric_prompt(
    task: str,
    method: str,
    case: str,
    stdout_excerpt: str,
    stderr_excerpt: str,
    output_files: list,
    first_csv_head: str,
) -> str:
    return f"""\
You are recording raw observations from a spatial-omics benchmark execution.

Task: {task}
Method: {method}
Case: {case}

Output files found: {_json.dumps(output_files)}

First output file head (up to 2000 chars):
{first_csv_head}

Execution stdout excerpt:
{stdout_excerpt[:1000]}

Execution stderr excerpt:
{stderr_excerpt[:500]}

Extract raw observations. Return ONLY a JSON object with exactly these keys:

{{
  "metric_raw": {{"name": "<metric name or empty string>", "value": <number or null>}},
  "anomalies_observed": ["<observed anomaly>"]
}}

Rules:
- metric_raw.name: the primary metric name found in output or stdout (e.g. "ARI"). Empty string if undetectable.
- metric_raw.value: numeric value if present, null if not.
- anomalies_observed: list only what is actually present in the output. Empty list if nothing anomalous.
- Do NOT invent values. null is correct when uncertain.
"""
