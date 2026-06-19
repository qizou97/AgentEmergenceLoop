<!--
PROVENANCE: This file is a documented reduced fixture derived from the real benchmark task.

Source task directory : data/spatial_domain_identification_task/
Real paper path       : data/spatial_domain_identification_task/papers/STAGATE.pdf  (confirmed present)
Real repository path  : data/spatial_domain_identification_task/codes/STAGATE       (confirmed present)
Benchmark data        : DLPFC slice 151673 .h5ad — genuinely absent locally

This is NOT a synthetic replacement.  It points at the real paper PDF and the
real method repository under data/.  The content is verbatim from the design
spec (section 6) which itself was derived from the actual spatial-domain
identification benchmark task.  The DLPFC .h5ad data file is intentionally
absent so that the pipeline produces a real blocked cycle with structural_check
passed:true — the auditable-package outcome tested by test_integration.py.

Used by: tests/test_integration.py
Testing policy reference: docs/TESTING_POLICY.md (reduced fixtures must preserve provenance)
-->

## Task
spatial_domain_identification

## Method
STAGATE

## Case
DLPFC_151673

## Paper
path: data/spatial_domain_identification_task/papers/STAGATE.pdf
notes: Section 4.1 describes DLPFC evaluation. ARI mentioned as primary metric.

## Repository
path: data/spatial_domain_identification_task/codes/STAGATE
notes: Entry point unclear. Tutorial notebook exists.

## Data
notes: DLPFC slice 151673 required. File location unknown locally.

## What to reconstruct
Reproduce the spatial domain identification result on DLPFC 151673 as reported
in the paper, using ARI as the primary metric if evidence supports it.

## Human observations
(fill in after run, or add any prior knowledge to guide reconstruction)
