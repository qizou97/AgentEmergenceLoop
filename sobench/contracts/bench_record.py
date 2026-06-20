"""
sobench/contracts/bench_record.py — the fixed result schema (spec §4.4).

A BenchRecord is the single source of truth for one method×case outcome. It is
written only by sobench.runner — never by the agent or run_benchmark.py — so the
schema is closed (`extra="forbid"`): an unexpected field is a bug, not a silent
pass-through. results.csv is a flattening of these records.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SpatialMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ARI: float | None = None
    NMI: float | None = None


class BenchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str  # "<method>__<dataset>__<case>"
    project_id: str
    task: str
    method: str
    dataset: str
    case: str
    metrics: SpatialMetrics
    status: str  # success | failed | skipped | timeout | invalid_output
    skip_reason: str | None = None
    failure_detail: str | None = None
    duration_seconds: float | None = None
    driver_repair_count: int
    env_name: str
    created_at: str  # ISO-8601
