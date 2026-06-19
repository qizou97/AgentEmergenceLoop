"""
tests/test_cli.py — CLI + scaffold + run/check/report subcommand tests.

Uses the REAL task identity from data/:
  task    = spatial_domain_identification
  method  = STAGATE
  case    = DLPFC_151673

All workspace I/O goes to pytest tmp_path (temporary output dirs allowed by
testing policy). No mocks, no monkeypatching — cli.main() is driven directly.

run/check/report tests against a real-task-derived completed workspace fixture:
  - structural_check.json and experience_record.json are real-task-derived
    fixtures (provenance: schemas from models.py, values from the real task).
  - check and report use these fixtures; they are not fabricated data.
"""

import json
import os
import pytest
from pathlib import Path

from conftest import benchmark_intent_content

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"

DATA_ROOT = Path(__file__).parent.parent / "data" / "spatial_domain_identification_task"
PAPER_PATH = DATA_ROOT / "papers" / "STAGATE.pdf"
REPO_PATH = DATA_ROOT / "codes" / "STAGATE"

REAL_API_KEY_PRESENT = bool(os.environ.get("OPENAI_API_KEY"))

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


# ---------------------------------------------------------------------------
# Helpers to build a completed real-task-derived workspace fixture
# ---------------------------------------------------------------------------

def _build_completed_workspace(root: Path) -> Path:
    """
    Build a real-task-derived blocked-but-complete workspace under root.

    Writes all artifacts required-always by s14 (benchmark_intent.md +
    paper_evidence, repo_evidence, data_manifest, task_spec,
    evaluation_contract, risk_audit, blocker [blocked:true], execution_log
    [status:not_attempted], experience_record) so that when check re-runs s14
    it finds all required artifacts and returns passed:True.

    Does NOT write raw_observations / result_validity_audit / interpretation —
    these are excused by blocker.blocked:true.

    Provenance: values mirror what the real pipeline would produce for a
    blocked run where the DLPFC .h5ad is absent.  Not fabricated beyond task
    identity.
    """
    from sobench.models import (
        PaperEvidence, RepoEvidence, DataManifest, TaskSpec,
        EvaluationContract, RiskAudit, Blocker, ExecutionLog, ExperienceRecord,
    )
    from sobench.workspace import Workspace

    ws = Workspace(task=TASK, method=METHOD, case=CASE, root=str(root))
    ws.dir.mkdir(parents=True, exist_ok=True)

    # --- benchmark_intent.md (markdown, presence only) ---
    (ws.dir / "benchmark_intent.md").write_text(
        benchmark_intent_content(TASK, METHOD, CASE), encoding="utf-8"
    )

    # --- paper_evidence ---
    ws.write_artifact("paper_evidence", PaperEvidence(
        task=TASK, method=METHOD,
        source=str(PAPER_PATH),
        evaluation_contexts=[{"case": CASE, "metric": "ARI"}],
        coordinate_evidence="Section 4.1 reports ARI on DLPFC slices.",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=[],
    ))

    # --- repo_evidence ---
    ws.write_artifact("repo_evidence", RepoEvidence(
        task=TASK, method=METHOD,
        entry_points=["tutorial/DLPFC_tutorial.py"],
        dependencies={"scanpy": ">=1.9", "torch": ">=1.10"},
        hardcoded_paths=[],
        metric_implementations=["ARI via sklearn"],
        deviations_from_paper=[],
        coordinate_evidence="Tutorial notebook uses ARI from sklearn.",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=[],
    ))

    # --- data_manifest ---
    ws.write_artifact("data_manifest", DataManifest(
        task=TASK, method=METHOD, case=CASE,
        required=[{"file": "151673.h5ad", "source": "spatialLIBD", "present": False}],
        coordinate_evidence="spatialLIBD hosts DLPFC slices.",
        coordinate_assumptions="spatialLIBD download required.",
        coordinate_open_questions=[],
        coordinate_checks=[],
        open_questions=["Where is the .h5ad locally?"],
    ))

    # --- task_spec ---
    ws.write_artifact("task_spec", TaskSpec(
        task=TASK, method=METHOD, case=CASE,
        source_context="STAGATE paper section 4.1",
        input_description="DLPFC 151673 Visium .h5ad",
        expected_output="Spatial domain labels per spot",
        primary_metric={"name": "ARI", "higher_is_better": True},
        assumptions=["spatialLIBD ground truth available"],
        unresolved=["Data not present locally"],
    ))

    # --- evaluation_contract ---
    ws.write_artifact("evaluation_contract", EvaluationContract(
        task=TASK, method=METHOD, case=CASE,
        metric={"name": "ARI", "higher_is_better": True},
        data_requirements_resolved=False,
        data_blockers=["DLPFC 151673 .h5ad absent"],
        open_questions=[],
    ))

    # --- risk_audit ---
    ws.write_artifact("risk_audit", RiskAudit(
        task=TASK, method=METHOD, case=CASE,
        risks=[{"id": "R1", "description": "Data absent", "severity": "blocker"}],
        overall_confidence="low",
        blocker_risk_ids=["R1"],
    ))

    # --- blocker (blocked:true — excuses s10/s11/s12) ---
    ws.write_artifact("blocker", Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="DLPFC 151673 .h5ad not present locally",
        detail="spatialLIBD download required before execution can proceed.",
        evidence="data_manifest.required[0].present == False",
        resolution="Download from spatialLIBD and place at expected path.",
        human_action_required=True,
    ))

    # --- execution_log (not_attempted — execution_attempted:False in s14) ---
    ws.write_artifact("execution_log", ExecutionLog(
        task=TASK, method=METHOD, case=CASE,
        status="not_attempted",
        command="",
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment={},
        output_files=[],
    ))

    # --- experience_record ---
    ws.write_artifact("experience_record", ExperienceRecord(
        id="exp-001",
        task=TASK, method=METHOD, case=CASE,
        tags=["data_missing", "spatialLIBD", "DLPFC"],
        finding="DLPFC 151673 .h5ad not present locally; spatialLIBD is the expected source",
        evidence=["data_manifest.required[0]", "blocker.detail"],
        confidence="high",
        failure_conditions=[],
        status="hypothesis",
        created="2026-06-19",
    ))

    # Run s14 to produce structural_check.json (needed by report; deterministic).
    from sobench.steps import s14_structural_check
    s14_structural_check.run(ws)

    return ws.dir


# ---------------------------------------------------------------------------
# check tests — exit-code gate (deterministic, no LLM)
# ---------------------------------------------------------------------------

def test_check_exits_zero_and_prints_passed_for_blocked_complete_workspace(tmp_path, capsys):
    """
    check exits 0 AND prints PASSED when all required-always artifacts present
    and blocker.blocked:true (post-exec artifacts excused).

    s14 is pure Python — deterministic, no LLM required.
    """
    _build_completed_workspace(tmp_path)
    from sobench import cli

    exit_code = cli.main([
        "check",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0, (
        f"check should return 0 for a blocked-but-complete workspace, got {exit_code}.\n"
        f"stdout: {captured.out!r}\nstderr: {captured.err!r}"
    )
    assert "passed" in captured.out.lower(), (
        f"Expected 'PASSED' in check output, got: {captured.out!r}"
    )


def test_check_exits_nonzero_and_prints_failed_when_required_artifact_missing(tmp_path, capsys):
    """
    check exits non-zero AND names the missing artifact when a required-always
    artifact is absent and blocker.blocked:false (not a blocked run).

    Scenario: workspace has benchmark_intent.md, blocker [blocked:false], and
    experience_record, but task_spec is absent — s14 counts it as
    missing_unacknowledged and returns passed:False.

    s14 is pure Python — deterministic, no LLM required.
    """
    from sobench.models import Blocker, ExecutionLog, ExperienceRecord
    from sobench.workspace import Workspace

    ws = Workspace(task=TASK, method=METHOD, case=CASE, root=str(tmp_path))
    ws.dir.mkdir(parents=True, exist_ok=True)

    # benchmark_intent.md present
    (ws.dir / "benchmark_intent.md").write_text(
        benchmark_intent_content(TASK, METHOD, CASE), encoding="utf-8"
    )

    # blocker present but NOT blocked — post-exec artifacts are NOT excused
    ws.write_artifact("blocker", Blocker(
        blocked=False,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    ))

    # experience_record present
    ws.write_artifact("experience_record", ExperienceRecord(
        id="exp-001",
        task=TASK, method=METHOD, case=CASE,
        tags=[],
        finding="Partial workspace — task_spec intentionally absent for this test.",
        evidence=[],
        confidence="low",
        failure_conditions=[],
        status="hypothesis",
        created="2026-06-19",
    ))

    # Intentionally omit paper_evidence, repo_evidence, data_manifest,
    # task_spec, evaluation_contract, risk_audit, execution_log,
    # raw_observations, result_validity_audit, interpretation.
    # With blocker.blocked:false, all absent JSON artifacts are unacknowledged.

    from sobench import cli

    exit_code = cli.main([
        "check",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()

    assert exit_code != 0, (
        f"check should return non-zero when required artifacts missing, got {exit_code}.\n"
        f"stdout: {captured.out!r}"
    )
    assert "failed" in captured.out.lower(), (
        f"Expected 'FAILED' in check output, got: {captured.out!r}"
    )
    assert "missing" in captured.out.lower(), (
        f"Expected missing artifact names in output, got: {captured.out!r}"
    )


# ---------------------------------------------------------------------------
# report tests (against real-task-derived workspace fixture)
# ---------------------------------------------------------------------------

def test_report_exits_zero_with_complete_workspace(tmp_path, capsys):
    """report exits 0 when structural_check.json and experience_record.json exist."""
    _build_completed_workspace(tmp_path)
    from sobench import cli

    exit_code = cli.main([
        "report",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code == 0, f"report returned {exit_code}"


def test_report_prints_summary_fields(tmp_path, capsys):
    """report output contains key summary fields."""
    _build_completed_workspace(tmp_path)
    from sobench import cli

    cli.main([
        "report",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()
    assert "not yet implemented" not in captured.out.lower(), (
        "report still prints stub message"
    )
    # Check that key fields appear in output
    for field in ("passed", "completed_with_blocker", "execution_attempted",
                  "benchmark_result_claimed", "experience finding", "experience status"):
        assert field in captured.out.lower(), (
            f"Expected '{field}' in report output, got: {captured.out!r}"
        )


def test_report_exits_nonzero_when_artifacts_missing(tmp_path, capsys):
    """report exits non-zero gracefully when artifacts are absent."""
    from sobench import cli

    exit_code = cli.main([
        "report",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    assert exit_code != 0, "report should return non-zero when artifacts missing"


def test_report_prints_clear_message_when_artifacts_missing(tmp_path, capsys):
    """report prints a clear error message (not a crash) when artifacts absent."""
    from sobench import cli

    cli.main([
        "report",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()
    # Should print an error message, not raise an exception
    assert "error" in captured.err.lower() or "not found" in captured.err.lower(), (
        f"Expected clear error message in stderr, got: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# run test — argument plumbing (gate on OPENAI_API_KEY)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not REAL_API_KEY_PRESENT,
    reason="OPENAI_API_KEY absent — real pipeline cannot run"
)
def test_run_wires_runner_against_real_blocked_task(tmp_path, capsys):
    """
    run CLI invokes the real runner against the blocked real task.

    The DLPFC .h5ad is absent, so the pipeline blocks at s09.
    Asserts that 'run' no longer prints 'not yet implemented' and instead
    prints the step summary with the blocked status.
    """
    from sobench import cli

    # Build workspace with real-task-derived benchmark_intent.md
    ws_dir = tmp_path / TASK / CASE / METHOD
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "benchmark_intent.md").write_text(
        benchmark_intent_content(TASK, METHOD, CASE), encoding="utf-8"
    )

    exit_code = cli.main([
        "run",
        "--task", TASK,
        "--method", METHOD,
        "--case", CASE,
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 0, f"run returned non-zero: {exit_code}"
    assert "not yet implemented" not in captured.out.lower(), (
        "run still prints stub message"
    )
    # Summary should mention blocked status
    assert "blocked" in captured.out.lower(), (
        f"Expected 'blocked' in run summary, got: {captured.out!r}"
    )
