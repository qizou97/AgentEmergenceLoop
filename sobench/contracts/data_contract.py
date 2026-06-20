"""
sobench/contracts/data_contract.py — per-case data description (spec §4.2).

Different cases may have different files, columns, or keys. ground_truth_column
and spatial_key are validated against the ACTUAL h5ad at freeze time — never
hardcoded (the spec's "Cell_class" example is illustrative; the real MERFISH
ground-truth column is "ground_truth").
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    h5ad_path: str
    obs_columns: list[str]
    spatial_key: str
    ground_truth_column: str


class DataContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: dict[str, CaseData]
