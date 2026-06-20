"""
sobench/contracts/task_contract.py — the benchmark matrix (spec §4.1).

Carries per-method metadata (repo/driver/env paths) so the runner can resolve
everything without a separate MethodContract in M1.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MethodEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    repo_path: str
    driver_path: str
    env_file: str
    env_record: str


class TaskContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    task: str
    dataset: str
    cases: list[str]
    methods: list[MethodEntry]
