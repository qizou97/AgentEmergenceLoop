"""
sobench/contracts/metric_contract.py — metric set (spec §4.3).

Deterministic in M1: metrics is a subset of {ARI, NMI}, computed by
sobench.metrics. No LLM-judged metrics.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MetricContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metrics: list[str]
    implementation: str
    label_type: str
