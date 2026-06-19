"""
Tests for sobench/models.py — round-trip and validate() for all 14 artifact dataclasses.

All example values are derived from the real benchmark task:
  data/spatial_domain_identification_task/
  task: spatial_domain_identification, method: STAGATE, case: DLPFC_151673

Per docs/TESTING_POLICY.md: no mocks; all inputs derived from the real task.
Temporary output dirs are explicitly allowed; these tests are purely in-memory.
"""

import pytest
from sobench.models import (
    ParsedIntent,
    PaperEvidence,
    RepoEvidence,
    DataManifest,
    TaskSpec,
    EvaluationContract,
    RiskAudit,
    Blocker,
    ExecutionLog,
    RawObservations,
    ResultValidityAudit,
    Interpretation,
    ExperienceRecord,
    StructuralCheck,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TASK = "spatial_domain_identification"
METHOD = "STAGATE"
CASE = "DLPFC_151673"


def roundtrip(obj):
    """Assert from_dict(to_dict(obj)) == obj and return the reconstructed obj."""
    cls = type(obj)
    d = obj.to_dict()
    restored = cls.from_dict(d)
    assert restored == obj, f"Round-trip failed for {cls.__name__}"
    return restored


# ---------------------------------------------------------------------------
# 7.1 ParsedIntent
# ---------------------------------------------------------------------------

def test_parsed_intent_roundtrip():
    obj = ParsedIntent(
        task=TASK,
        method=METHOD,
        case=CASE,
        paper_path="data/spatial_domain_identification_task/papers/STAGATE.pdf",
        repo_path="data/spatial_domain_identification_task/codes/STAGATE",
        data_notes="DLPFC slice 151673 required. File location unknown locally.",
        reconstruction_goal="Reproduce spatial domain identification on DLPFC 151673 using ARI.",
        human_observations="",
    )
    roundtrip(obj)


def test_parsed_intent_validate_missing_task():
    obj = ParsedIntent(
        task="",
        method=METHOD,
        case=CASE,
        paper_path="",
        repo_path="",
        data_notes="",
        reconstruction_goal="",
        human_observations="",
    )
    with pytest.raises(ValueError):
        obj.validate()


def test_parsed_intent_validate_missing_method():
    obj = ParsedIntent(
        task=TASK,
        method="",
        case=CASE,
        paper_path="",
        repo_path="",
        data_notes="",
        reconstruction_goal="",
        human_observations="",
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.2 PaperEvidence
# ---------------------------------------------------------------------------

def test_paper_evidence_roundtrip():
    obj = PaperEvidence(
        task=TASK,
        method=METHOD,
        source="STAGATE.pdf",
        evaluation_contexts=[
            {
                "id": "ctx-001",
                "task": TASK,
                "cases": [CASE, "DLPFC_151507"],
                "metrics": [
                    {"name": "ARI", "confidence": "high", "quote": "we report ARI across all slices"},
                    {"name": "NMI", "confidence": "medium", "quote": "NMI shown in supplement"},
                ],
                "downstream_tasks": [],
                "notes": "primary evaluation; k not stated explicitly",
            }
        ],
        coordinate_evidence="paper references spatial coordinates but does not specify coordinate space or scale",
        coordinate_open_questions=["which coordinate space is used for spatial graph construction?"],
        ambiguities=["k selection procedure not described", "preprocessing steps underspecified"],
        missing=["no train/test split described"],
    )
    roundtrip(obj)


def test_paper_evidence_validate_missing_task():
    obj = PaperEvidence(
        task="",
        method=METHOD,
        source="STAGATE.pdf",
        evaluation_contexts=[],
        coordinate_evidence="",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.3 RepoEvidence
# ---------------------------------------------------------------------------

def test_repo_evidence_roundtrip():
    obj = RepoEvidence(
        task=TASK,
        method=METHOD,
        entry_points=["tutorial.ipynb", "run_STAGATE.py"],
        dependencies={"python": "3.8", "packages": ["scanpy==1.9", "torch==1.11"]},
        hardcoded_paths=["./data/DLPFC/"],
        metric_implementations=[
            {"name": "ARI", "file": "utils.py", "line": 42, "matches_paper": True}
        ],
        deviations_from_paper=["tutorial uses raw counts; paper implies normalized input"],
        coordinate_evidence="spatial coords loaded from obsm['spatial']; no scale factor applied in tutorial",
        coordinate_open_questions=["is obsm['spatial'] in pixel or array space?"],
        ambiguities=["tutorial uses different slice than paper figure 2"],
        missing=["no requirements.txt; only conda env yaml"],
    )
    roundtrip(obj)


def test_repo_evidence_validate_missing_task():
    obj = RepoEvidence(
        task="",
        method=METHOD,
        entry_points=[],
        dependencies={},
        hardcoded_paths=[],
        metric_implementations=[],
        deviations_from_paper=[],
        coordinate_evidence="",
        coordinate_open_questions=[],
        ambiguities=[],
        missing=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.4 DataManifest
# ---------------------------------------------------------------------------

def test_data_manifest_roundtrip():
    obj = DataManifest(
        task=TASK,
        method=METHOD,
        case=CASE,
        required=[
            {
                "role": "expression_matrix_with_coords",
                "format": "AnnData .h5ad",
                "expected_path": "data/DLPFC/151673.h5ad",
                "available": False,
                "notes": "not found locally; spatialLIBD is likely source",
            },
            {
                "role": "ground_truth_labels",
                "format": "obs column in .h5ad",
                "expected_path": None,
                "available": False,
                "notes": "expected inside expression file; column name unclear from repo",
            },
        ],
        coordinate_evidence="repo loads obsm['spatial'] from .h5ad; paper does not specify space",
        coordinate_assumptions="none made yet — awaiting data file inspection",
        coordinate_open_questions=["pixel vs array space?", "scale factor needed?"],
        coordinate_checks=[],
        open_questions=["ground truth column name in .h5ad?"],
    )
    roundtrip(obj)


def test_data_manifest_validate_missing_task():
    obj = DataManifest(
        task="",
        method=METHOD,
        case=CASE,
        required=[],
        coordinate_evidence="",
        coordinate_assumptions="",
        coordinate_open_questions=[],
        coordinate_checks=[],
        open_questions=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.5 TaskSpec
# ---------------------------------------------------------------------------

def test_task_spec_roundtrip():
    obj = TaskSpec(
        task=TASK,
        method=METHOD,
        case=CASE,
        source_context="ctx-001",
        input_description="AnnData with expression matrix and spatial coordinates",
        expected_output="cluster label per spot",
        primary_metric={"name": "ARI", "resolved": True},
        assumptions=[
            "raw counts as input based on repo evidence",
            "ground truth from obs column — name to be confirmed from data",
        ],
        unresolved=["cluster count k not stated in paper"],
    )
    roundtrip(obj)


def test_task_spec_validate_missing_task():
    obj = TaskSpec(
        task="",
        method=METHOD,
        case=CASE,
        source_context="",
        input_description="",
        expected_output="",
        primary_metric={},
        assumptions=[],
        unresolved=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.6 EvaluationContract
# ---------------------------------------------------------------------------

def test_evaluation_contract_roundtrip():
    obj = EvaluationContract(
        task=TASK,
        method=METHOD,
        case=CASE,
        metric={
            "name": "ARI",
            "resolved": True,
            "implementation": "sklearn.metrics.adjusted_rand_score",
            "provenance": "stated in paper ctx-001; confirmed in utils.py:42",
            "known_risks": ["sensitive to k; k is unresolved"],
        },
        data_requirements_resolved=False,
        data_blockers=["expression file not found locally"],
        open_questions=["ground truth column name", "k selection"],
    )
    roundtrip(obj)


def test_evaluation_contract_validate_missing_task():
    obj = EvaluationContract(
        task="",
        method=METHOD,
        case=CASE,
        metric={},
        data_requirements_resolved=False,
        data_blockers=[],
        open_questions=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.7 RiskAudit
# ---------------------------------------------------------------------------

def test_risk_audit_roundtrip():
    obj = RiskAudit(
        task=TASK,
        method=METHOD,
        case=CASE,
        risks=[
            {
                "id": "risk-001",
                "category": "data",
                "description": "required data file not located locally",
                "severity": "high",
                "evidence": "data_manifest.required[0].available=false",
                "mitigation": "download from spatialLIBD; update data_manifest",
            },
            {
                "id": "risk-002",
                "category": "metric",
                "description": "cluster count k not specified in paper",
                "severity": "medium",
                "evidence": "task_spec.unresolved[0]",
                "mitigation": "document assumption; report sensitivity if run completes",
            },
        ],
        overall_confidence="low",
        blocker_risk_ids=["risk-001"],
    )
    roundtrip(obj)


def test_risk_audit_validate_missing_task():
    obj = RiskAudit(
        task="",
        method=METHOD,
        case=CASE,
        risks=[],
        overall_confidence="",
        blocker_risk_ids=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.8 Blocker
# ---------------------------------------------------------------------------

def test_blocker_not_blocked_roundtrip():
    obj = Blocker(
        blocked=False,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    )
    roundtrip(obj)


def test_blocker_blocked_roundtrip():
    obj = Blocker(
        blocked=True,
        raised_by_step="s09_execute_or_block",
        reason="required data file not found",
        detail="data/DLPFC/151673.h5ad does not exist at expected path",
        evidence="data_manifest.required[0].available=false",
        resolution="download DLPFC 151673 from spatialLIBD and update data_manifest.json",
        human_action_required=True,
    )
    roundtrip(obj)


def test_blocker_validate_missing_blocked_field():
    # A blocker dict without the 'blocked' field at all cannot be constructed
    # via from_dict — validate() should surface if the dict has the field as None
    # and blocked is not set.
    # We test that a Blocker with blocked=True but no reason raises.
    obj = Blocker(
        blocked=True,
        raised_by_step=None,
        reason=None,
        detail=None,
        evidence=None,
        resolution=None,
        human_action_required=False,
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.9 ExecutionLog
# ---------------------------------------------------------------------------

def test_execution_log_roundtrip():
    obj = ExecutionLog(
        task=TASK,
        method=METHOD,
        case=CASE,
        status="not_attempted",
        command="python run_STAGATE.py --slice 151673",
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment={"python": "3.10", "platform": "linux"},
        output_files=[],
    )
    roundtrip(obj)


def test_execution_log_validate_missing_task():
    obj = ExecutionLog(
        task="",
        method=METHOD,
        case=CASE,
        status="not_attempted",
        command="",
        stdout_excerpt="",
        stderr_excerpt="",
        duration_seconds=None,
        environment={},
        output_files=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.10 RawObservations
# ---------------------------------------------------------------------------

def test_raw_observations_roundtrip():
    obj = RawObservations(
        task=TASK,
        method=METHOD,
        case=CASE,
        outputs_found=["results/151673_labels.csv"],
        output_shape={"rows": 3639, "columns": 2},
        metric_raw={"name": "ARI", "value": 0.52},
        stdout_summary="Training complete. 7 clusters assigned.",
        stderr_summary="",
        anomalies_observed=[],
    )
    roundtrip(obj)


def test_raw_observations_validate_missing_task():
    obj = RawObservations(
        task="",
        method=METHOD,
        case=CASE,
        outputs_found=[],
        output_shape={},
        metric_raw={},
        stdout_summary="",
        stderr_summary="",
        anomalies_observed=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.11 ResultValidityAudit
# ---------------------------------------------------------------------------

def test_result_validity_audit_roundtrip():
    obj = ResultValidityAudit(
        task=TASK,
        method=METHOD,
        case=CASE,
        result_valid=True,
        checks=[
            {"check": "output row count matches input spot count", "passed": True},
            {"check": "cluster count matches assumed k=7", "passed": True},
            {"check": "no NaN or missing labels", "passed": True},
        ],
        validity_reasoning="outputs structurally consistent with expected task output",
        warnings=["k=7 was assumed, not confirmed from paper"],
    )
    roundtrip(obj)


def test_result_validity_audit_validate_missing_task():
    obj = ResultValidityAudit(
        task="",
        method=METHOD,
        case=CASE,
        result_valid=False,
        checks=[],
        validity_reasoning="",
        warnings=[],
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.12 Interpretation
# ---------------------------------------------------------------------------

def test_interpretation_roundtrip_valid_result():
    obj = Interpretation(
        task=TASK,
        method=METHOD,
        case=CASE,
        primary_metric_value=0.52,
        can_conclude=["ARI=0.52 is within the range reported in paper figure 2"],
        cannot_conclude=["whether normalized input would change result", "sensitivity to k"],
        benchmark_result_claimed=True,
        open_questions=["paper supplement NMI not computed"],
        interpretation="result consistent with paper; raw-counts assumption appears to hold for this case",
    )
    roundtrip(obj)


def test_interpretation_roundtrip_invalid_result():
    obj = Interpretation(
        task=TASK,
        method=METHOD,
        case=CASE,
        primary_metric_value=None,
        can_conclude=[],
        cannot_conclude=["result validity check failed; no benchmark result can be claimed"],
        benchmark_result_claimed=False,
        open_questions=[],
        interpretation="execution ran but outputs did not pass validity audit",
    )
    roundtrip(obj)


def test_interpretation_validate_missing_task():
    obj = Interpretation(
        task="",
        method=METHOD,
        case=CASE,
        primary_metric_value=None,
        can_conclude=[],
        cannot_conclude=[],
        benchmark_result_claimed=False,
        open_questions=[],
        interpretation="",
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.13 ExperienceRecord
# ---------------------------------------------------------------------------

def test_experience_record_roundtrip():
    obj = ExperienceRecord(
        id="exp-001",
        task=TASK,
        method=METHOD,
        case=CASE,
        tags=["ARI", "raw_counts", "DLPFC", "k_assumption"],
        finding="raw counts produce ARI consistent with paper",
        evidence=["repo_evidence.deviations_from_paper[0]", "interpretation.can_conclude[0]"],
        confidence="medium",
        failure_conditions=["may not hold outside DLPFC", "untested with normalized input"],
        status="hypothesis",
        created="2026-06-19",
    )
    roundtrip(obj)


def test_experience_record_validate_missing_task():
    obj = ExperienceRecord(
        id="exp-001",
        task="",
        method=METHOD,
        case=CASE,
        tags=[],
        finding="",
        evidence=[],
        confidence="",
        failure_conditions=[],
        status="hypothesis",
        created="2026-06-19",
    )
    with pytest.raises(ValueError):
        obj.validate()


def test_experience_record_validate_missing_finding():
    obj = ExperienceRecord(
        id="exp-001",
        task=TASK,
        method=METHOD,
        case=CASE,
        tags=[],
        finding="",
        evidence=[],
        confidence="",
        failure_conditions=[],
        status="hypothesis",
        created="2026-06-19",
    )
    with pytest.raises(ValueError):
        obj.validate()


# ---------------------------------------------------------------------------
# 7.14 StructuralCheck
# ---------------------------------------------------------------------------

def test_structural_check_roundtrip():
    obj = StructuralCheck(
        task=TASK,
        method=METHOD,
        case=CASE,
        passed=True,
        structurally_complete=True,
        completed_with_blocker=True,
        execution_attempted=False,
        benchmark_result_claimed=False,
        checks=[
            {"artifact": "benchmark_intent.md", "present": True},
            {"artifact": "paper_evidence.json", "present": True, "valid": True},
        ],
        missing_unacknowledged=[],
        warnings=["execution not attempted — blocked on missing data"],
    )
    roundtrip(obj)


def test_structural_check_validate_missing_task():
    obj = StructuralCheck(
        task="",
        method=METHOD,
        case=CASE,
        passed=False,
        structurally_complete=False,
        completed_with_blocker=False,
        execution_attempted=False,
        benchmark_result_claimed=False,
        checks=[],
        missing_unacknowledged=[],
        warnings=[],
    )
    with pytest.raises(ValueError):
        obj.validate()
