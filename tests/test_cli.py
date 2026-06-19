"""
tests/test_cli.py — CLI + scaffold subcommand tests.

Uses the REAL task identity from data/:
  task    = spatial_domain_identification
  method  = STAGATE
  case    = DLPFC_151673

All workspace I/O goes to pytest tmp_path (temporary output dirs allowed by
testing policy). No mocks, no monkeypatching — cli.main() is driven directly.
"""

import pytest
from pathlib import Path

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"

DATA_ROOT = Path(__file__).parent.parent / "data" / "spatial_domain_identification_task"
PAPER_PATH = DATA_ROOT / "papers" / "STAGATE.pdf"
REPO_PATH = DATA_ROOT / "codes" / "STAGATE"

# Required section headings per spec section 6
REQUIRED_HEADINGS = [
    "## Task",
    "## Method",
    "## Case",
    "## Paper",
    "## Repository",
    "## Data",
    "## What to reconstruct",
    "## Human observations",
]


def test_scaffold_creates_workspace_directory(tmp_path):
    """scaffold creates workspaces/task/case/method/ under root."""
    from sobench import cli

    exit_code = cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code == 0

    # layout: root/task/case/method/
    expected_dir = tmp_path / TASK / CASE / METHOD
    assert expected_dir.is_dir(), f"Expected workspace dir at {expected_dir}"


def test_scaffold_writes_benchmark_intent(tmp_path):
    """scaffold writes benchmark_intent.md inside the workspace directory."""
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    assert intent_file.exists(), "benchmark_intent.md not written"


def test_scaffold_intent_has_all_required_headings(tmp_path):
    """benchmark_intent.md contains all required section headings."""
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    content = intent_file.read_text(encoding="utf-8")

    for heading in REQUIRED_HEADINGS:
        assert heading in content, f"Required heading missing: {heading!r}"


def test_scaffold_prefills_task_method_case(tmp_path):
    """benchmark_intent.md has task/method/case values pre-filled."""
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    content = intent_file.read_text(encoding="utf-8")

    assert TASK in content, "Task value not pre-filled in intent"
    assert METHOD in content, "Method value not pre-filled in intent"
    assert CASE in content, "Case value not pre-filled in intent"


def test_scaffold_exits_nonzero_if_workspace_exists(tmp_path):
    """scaffold exits non-zero when the workspace directory already exists."""
    from sobench import cli

    args = [
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ]

    # First call creates it
    first_exit = cli.main(args)
    assert first_exit == 0

    # Second call must exit non-zero (do not clobber)
    with pytest.raises(SystemExit) as exc_info:
        cli.main(args)
    assert exc_info.value.code != 0


def test_scaffold_with_paper_flag_populates_convenience_line(tmp_path):
    """--paper flag writes a convenience path: line under ## Paper."""
    assert PAPER_PATH.exists(), f"Real paper not found at {PAPER_PATH}"
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
        "--paper", str(PAPER_PATH),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    content = intent_file.read_text(encoding="utf-8")

    assert str(PAPER_PATH) in content, (
        f"Paper path {PAPER_PATH} not found in benchmark_intent.md"
    )


def test_scaffold_with_repo_flag_populates_convenience_line(tmp_path):
    """--repo flag writes a convenience path: line under ## Repository."""
    assert REPO_PATH.exists(), f"Real repo not found at {REPO_PATH}"
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
        "--repo", str(REPO_PATH),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    content = intent_file.read_text(encoding="utf-8")

    assert str(REPO_PATH) in content, (
        f"Repo path {REPO_PATH} not found in benchmark_intent.md"
    )


def test_scaffold_with_data_flag_populates_convenience_line(tmp_path):
    """--data flag writes a convenience path: line under ## Data."""
    data_path = DATA_ROOT  # use the real data root as a convenience path
    assert data_path.exists(), f"Real data dir not found at {data_path}"
    from sobench import cli

    cli.main([
        "scaffold",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
        "--data", str(data_path),
    ])

    intent_file = tmp_path / TASK / CASE / METHOD / "benchmark_intent.md"
    content = intent_file.read_text(encoding="utf-8")

    assert str(data_path) in content, (
        f"Data path {data_path} not found in benchmark_intent.md"
    )


def test_run_stub_prints_not_implemented(tmp_path, capsys):
    """run subcommand is a stub and exits 0."""
    from sobench import cli

    exit_code = cli.main([
        "run",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out.lower()


def test_check_stub_prints_not_implemented(tmp_path, capsys):
    """check subcommand is a stub and exits 0."""
    from sobench import cli

    exit_code = cli.main([
        "check",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out.lower()


def test_report_stub_prints_not_implemented(tmp_path, capsys):
    """report subcommand is a stub and exits 0."""
    from sobench import cli

    exit_code = cli.main([
        "report",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.out.lower()
