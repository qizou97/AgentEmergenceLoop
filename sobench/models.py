"""
sobench/models.py — artifact dataclasses matching spec section 7.

14 JSON artifact dataclasses (one per JSON artifact in spec 7.1–7.14).
NOTE: The plan says "15 artifact dataclasses" but spec section 7 lists exactly
14 JSON artifacts (7.1–7.14). benchmark_intent.md (section 3) is a
human-authored markdown file, not a JSON artifact. We implement 14 dataclasses.

Each dataclass:
  - is a @dataclass for structural equality
  - exposes from_dict(d) -> cls, to_dict() -> dict, validate() -> None
  - carries identity fields task/method/case where the spec shows them
    (paper_evidence and repo_evidence omit case per their spec schemas)
  - Blocker carries no task/method/case per its spec schema
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _require(value: Any, name: str) -> None:
    """Raise ValueError if value is falsy (empty string, None, etc.)."""
    if not value and value != 0 and value is not False:
        raise ValueError(f"Required field '{name}' is missing or empty")


# ---------------------------------------------------------------------------
# 7.1 parsed_intent
# ---------------------------------------------------------------------------

@dataclass
class ParsedIntent:
    task: str
    method: str
    case: str
    paper_path: str
    repo_path: str
    data_notes: str
    reconstruction_goal: str
    human_observations: str

    @classmethod
    def from_dict(cls, d: dict) -> "ParsedIntent":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            paper_path=d["paper_path"],
            repo_path=d["repo_path"],
            data_notes=d["data_notes"],
            reconstruction_goal=d["reconstruction_goal"],
            human_observations=d["human_observations"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "paper_path": self.paper_path,
            "repo_path": self.repo_path,
            "data_notes": self.data_notes,
            "reconstruction_goal": self.reconstruction_goal,
            "human_observations": self.human_observations,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.2 paper_evidence
# spec shows task + method only (no case)
# ---------------------------------------------------------------------------

@dataclass
class PaperEvidence:
    task: str
    method: str
    source: str
    evaluation_contexts: list
    coordinate_evidence: str
    coordinate_open_questions: list
    ambiguities: list
    missing: list

    @classmethod
    def from_dict(cls, d: dict) -> "PaperEvidence":
        return cls(
            task=d["task"],
            method=d["method"],
            source=d["source"],
            evaluation_contexts=d["evaluation_contexts"],
            coordinate_evidence=d["coordinate_evidence"],
            coordinate_open_questions=d["coordinate_open_questions"],
            ambiguities=d["ambiguities"],
            missing=d["missing"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "source": self.source,
            "evaluation_contexts": self.evaluation_contexts,
            "coordinate_evidence": self.coordinate_evidence,
            "coordinate_open_questions": self.coordinate_open_questions,
            "ambiguities": self.ambiguities,
            "missing": self.missing,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")


# ---------------------------------------------------------------------------
# 7.3 repo_evidence
# spec shows task + method only (no case)
# ---------------------------------------------------------------------------

@dataclass
class RepoEvidence:
    task: str
    method: str
    entry_points: list
    dependencies: dict
    hardcoded_paths: list
    metric_implementations: list
    deviations_from_paper: list
    coordinate_evidence: str
    coordinate_open_questions: list
    ambiguities: list
    missing: list

    @classmethod
    def from_dict(cls, d: dict) -> "RepoEvidence":
        return cls(
            task=d["task"],
            method=d["method"],
            entry_points=d["entry_points"],
            dependencies=d["dependencies"],
            hardcoded_paths=d["hardcoded_paths"],
            metric_implementations=d["metric_implementations"],
            deviations_from_paper=d["deviations_from_paper"],
            coordinate_evidence=d["coordinate_evidence"],
            coordinate_open_questions=d["coordinate_open_questions"],
            ambiguities=d["ambiguities"],
            missing=d["missing"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "entry_points": self.entry_points,
            "dependencies": self.dependencies,
            "hardcoded_paths": self.hardcoded_paths,
            "metric_implementations": self.metric_implementations,
            "deviations_from_paper": self.deviations_from_paper,
            "coordinate_evidence": self.coordinate_evidence,
            "coordinate_open_questions": self.coordinate_open_questions,
            "ambiguities": self.ambiguities,
            "missing": self.missing,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")


# ---------------------------------------------------------------------------
# 7.4 data_manifest
# ---------------------------------------------------------------------------

@dataclass
class DataManifest:
    task: str
    method: str
    case: str
    required: list
    coordinate_evidence: str
    coordinate_assumptions: str
    coordinate_open_questions: list
    coordinate_checks: list
    open_questions: list

    @classmethod
    def from_dict(cls, d: dict) -> "DataManifest":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            required=d["required"],
            coordinate_evidence=d["coordinate_evidence"],
            coordinate_assumptions=d["coordinate_assumptions"],
            coordinate_open_questions=d["coordinate_open_questions"],
            coordinate_checks=d["coordinate_checks"],
            open_questions=d["open_questions"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "required": self.required,
            "coordinate_evidence": self.coordinate_evidence,
            "coordinate_assumptions": self.coordinate_assumptions,
            "coordinate_open_questions": self.coordinate_open_questions,
            "coordinate_checks": self.coordinate_checks,
            "open_questions": self.open_questions,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.5 task_spec
# ---------------------------------------------------------------------------

@dataclass
class TaskSpec:
    task: str
    method: str
    case: str
    source_context: str
    input_description: str
    expected_output: str
    primary_metric: dict
    assumptions: list
    unresolved: list

    @classmethod
    def from_dict(cls, d: dict) -> "TaskSpec":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            source_context=d["source_context"],
            input_description=d["input_description"],
            expected_output=d["expected_output"],
            primary_metric=d["primary_metric"],
            assumptions=d["assumptions"],
            unresolved=d["unresolved"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "source_context": self.source_context,
            "input_description": self.input_description,
            "expected_output": self.expected_output,
            "primary_metric": self.primary_metric,
            "assumptions": self.assumptions,
            "unresolved": self.unresolved,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.6 evaluation_contract
# ---------------------------------------------------------------------------

@dataclass
class EvaluationContract:
    task: str
    method: str
    case: str
    metric: dict
    data_requirements_resolved: bool
    data_blockers: list
    open_questions: list

    @classmethod
    def from_dict(cls, d: dict) -> "EvaluationContract":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            metric=d["metric"],
            data_requirements_resolved=d["data_requirements_resolved"],
            data_blockers=d["data_blockers"],
            open_questions=d["open_questions"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "metric": self.metric,
            "data_requirements_resolved": self.data_requirements_resolved,
            "data_blockers": self.data_blockers,
            "open_questions": self.open_questions,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.7 risk_audit
# ---------------------------------------------------------------------------

@dataclass
class RiskAudit:
    task: str
    method: str
    case: str
    risks: list
    overall_confidence: str
    blocker_risk_ids: list

    @classmethod
    def from_dict(cls, d: dict) -> "RiskAudit":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            risks=d["risks"],
            overall_confidence=d["overall_confidence"],
            blocker_risk_ids=d["blocker_risk_ids"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "risks": self.risks,
            "overall_confidence": self.overall_confidence,
            "blocker_risk_ids": self.blocker_risk_ids,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.8 blocker
# spec schema has no task/method/case fields
# ---------------------------------------------------------------------------

@dataclass
class Blocker:
    blocked: bool
    raised_by_step: Optional[str]
    reason: Optional[str]
    detail: Optional[str]
    evidence: Optional[str]
    resolution: Optional[str]
    human_action_required: bool

    @classmethod
    def from_dict(cls, d: dict) -> "Blocker":
        return cls(
            blocked=d["blocked"],
            raised_by_step=d["raised_by_step"],
            reason=d["reason"],
            detail=d["detail"],
            evidence=d["evidence"],
            resolution=d["resolution"],
            human_action_required=d["human_action_required"],
        )

    def to_dict(self) -> dict:
        return {
            "blocked": self.blocked,
            "raised_by_step": self.raised_by_step,
            "reason": self.reason,
            "detail": self.detail,
            "evidence": self.evidence,
            "resolution": self.resolution,
            "human_action_required": self.human_action_required,
        }

    def validate(self) -> None:
        if self.blocked and not self.reason:
            raise ValueError("Blocker with blocked=True must have a reason")


# ---------------------------------------------------------------------------
# 7.9 execution_log
# ---------------------------------------------------------------------------

@dataclass
class ExecutionLog:
    task: str
    method: str
    case: str
    status: str
    command: str
    stdout_excerpt: str
    stderr_excerpt: str
    duration_seconds: Optional[float]
    environment: dict
    output_files: list

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionLog":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            status=d["status"],
            command=d["command"],
            stdout_excerpt=d["stdout_excerpt"],
            stderr_excerpt=d["stderr_excerpt"],
            duration_seconds=d["duration_seconds"],
            environment=d["environment"],
            output_files=d["output_files"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "status": self.status,
            "command": self.command,
            "stdout_excerpt": self.stdout_excerpt,
            "stderr_excerpt": self.stderr_excerpt,
            "duration_seconds": self.duration_seconds,
            "environment": self.environment,
            "output_files": self.output_files,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.10 raw_observations
# ---------------------------------------------------------------------------

@dataclass
class RawObservations:
    task: str
    method: str
    case: str
    outputs_found: list
    output_shape: dict
    metric_raw: dict
    stdout_summary: str
    stderr_summary: str
    anomalies_observed: list

    @classmethod
    def from_dict(cls, d: dict) -> "RawObservations":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            outputs_found=d["outputs_found"],
            output_shape=d["output_shape"],
            metric_raw=d["metric_raw"],
            stdout_summary=d["stdout_summary"],
            stderr_summary=d["stderr_summary"],
            anomalies_observed=d["anomalies_observed"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "outputs_found": self.outputs_found,
            "output_shape": self.output_shape,
            "metric_raw": self.metric_raw,
            "stdout_summary": self.stdout_summary,
            "stderr_summary": self.stderr_summary,
            "anomalies_observed": self.anomalies_observed,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.11 result_validity_audit
# ---------------------------------------------------------------------------

@dataclass
class ResultValidityAudit:
    task: str
    method: str
    case: str
    result_valid: bool
    checks: list
    validity_reasoning: str
    warnings: list

    @classmethod
    def from_dict(cls, d: dict) -> "ResultValidityAudit":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            result_valid=d["result_valid"],
            checks=d["checks"],
            validity_reasoning=d["validity_reasoning"],
            warnings=d["warnings"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "result_valid": self.result_valid,
            "checks": self.checks,
            "validity_reasoning": self.validity_reasoning,
            "warnings": self.warnings,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.12 interpretation
# ---------------------------------------------------------------------------

@dataclass
class Interpretation:
    task: str
    method: str
    case: str
    primary_metric_value: Optional[float]
    can_conclude: list
    cannot_conclude: list
    benchmark_result_claimed: bool
    open_questions: list
    interpretation: str

    @classmethod
    def from_dict(cls, d: dict) -> "Interpretation":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            primary_metric_value=d["primary_metric_value"],
            can_conclude=d["can_conclude"],
            cannot_conclude=d["cannot_conclude"],
            benchmark_result_claimed=d["benchmark_result_claimed"],
            open_questions=d["open_questions"],
            interpretation=d["interpretation"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "primary_metric_value": self.primary_metric_value,
            "can_conclude": self.can_conclude,
            "cannot_conclude": self.cannot_conclude,
            "benchmark_result_claimed": self.benchmark_result_claimed,
            "open_questions": self.open_questions,
            "interpretation": self.interpretation,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")


# ---------------------------------------------------------------------------
# 7.13 experience_record
# ---------------------------------------------------------------------------

@dataclass
class ExperienceRecord:
    id: str
    task: str
    method: str
    case: str
    tags: list
    finding: str
    evidence: list
    confidence: str
    failure_conditions: list
    status: str
    created: str

    @classmethod
    def from_dict(cls, d: dict) -> "ExperienceRecord":
        return cls(
            id=d["id"],
            task=d["task"],
            method=d["method"],
            case=d["case"],
            tags=d["tags"],
            finding=d["finding"],
            evidence=d["evidence"],
            confidence=d["confidence"],
            failure_conditions=d["failure_conditions"],
            status=d["status"],
            created=d["created"],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "tags": self.tags,
            "finding": self.finding,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "failure_conditions": self.failure_conditions,
            "status": self.status,
            "created": self.created,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")
        _require(self.finding, "finding")


# ---------------------------------------------------------------------------
# 7.14 structural_check
# ---------------------------------------------------------------------------

@dataclass
class StructuralCheck:
    task: str
    method: str
    case: str
    passed: bool
    structurally_complete: bool
    completed_with_blocker: bool
    execution_attempted: bool
    benchmark_result_claimed: bool
    checks: list
    missing_unacknowledged: list
    warnings: list

    @classmethod
    def from_dict(cls, d: dict) -> "StructuralCheck":
        return cls(
            task=d["task"],
            method=d["method"],
            case=d["case"],
            passed=d["passed"],
            structurally_complete=d["structurally_complete"],
            completed_with_blocker=d["completed_with_blocker"],
            execution_attempted=d["execution_attempted"],
            benchmark_result_claimed=d["benchmark_result_claimed"],
            checks=d["checks"],
            missing_unacknowledged=d["missing_unacknowledged"],
            warnings=d["warnings"],
        )

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "method": self.method,
            "case": self.case,
            "passed": self.passed,
            "structurally_complete": self.structurally_complete,
            "completed_with_blocker": self.completed_with_blocker,
            "execution_attempted": self.execution_attempted,
            "benchmark_result_claimed": self.benchmark_result_claimed,
            "checks": self.checks,
            "missing_unacknowledged": self.missing_unacknowledged,
            "warnings": self.warnings,
        }

    def validate(self) -> None:
        _require(self.task, "task")
        _require(self.method, "method")
        _require(self.case, "case")
