"""
conftest.py — load .env at session start so OPENAI_API_KEY is available for
skipif markers that run at collection time.

Also provides shared fixtures used across multiple test modules.
"""

from pathlib import Path

DATA_ROOT = Path(__file__).parent.parent / "data" / "spatial_domain_identification_task"
PAPER_PATH = DATA_ROOT / "papers" / "STAGATE.pdf"
REPO_PATH = DATA_ROOT / "codes" / "STAGATE"


def benchmark_intent_content(
    task: str = "spatial_domain_identification",
    method: str = "STAGATE",
    case: str = "DLPFC_151673",
) -> str:
    """
    Return a real-task-derived benchmark_intent.md content string.

    Provenance: task/method/case from the genuine spatial_domain_identification
    benchmark; data notes reference the genuinely-absent DLPFC 151673 .h5ad.
    Used by both test_runner.py and test_cli.py to avoid duplication.
    """
    return f"""\
## Task
{task}

## Method
{method}

## Case
{case}

## Paper
path: {PAPER_PATH}
notes: Section 4.1 describes DLPFC evaluation. ARI mentioned as primary metric.

## Repository
path: {REPO_PATH}
notes: Entry point unclear. Tutorial notebook exists.

## Data
notes: DLPFC slice 151673 required. File location unknown locally.

## What to reconstruct
Reproduce the spatial domain identification result on {case} as reported
in the paper, using ARI as the primary metric if evidence supports it.

## Human observations
(fill in after run, or add any prior knowledge to guide reconstruction)
"""


def pytest_configure(config):
    """Load .env from repo root before collection so env-gated tests are not skipped falsely."""
    try:
        from dotenv import load_dotenv
        repo_root = Path(__file__).parents[1]
        load_dotenv(repo_root / ".env")
    except Exception:
        pass
