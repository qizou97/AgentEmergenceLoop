# Testing Policy

**Status:** Binding. This policy governs all tests in this repository and
**supersedes** any conflicting testing guidance in `README.md`, design specs,
or implementation plans.

## Core Rule: No Mock Tests

All implementation must be tested against the **real benchmark task** currently
stored under `data/`.

Mock tests are not accepted as evidence of correctness.

## Before Writing Tests

1. Inspect the `data/` directory.
2. Identify the current real task used by this repository.
3. Read its paper / repo / data / task artifacts.
4. Derive test expectations from that real task only.

> Current real task: `data/spatial_domain_identification_task/`
> (method repos: MENDER, STAGATE, SpaGCN; papers as PDFs). Re-inspect `data/`
> before each test-writing session — the real task is the source of truth, not
> this note.

## Hard Constraints

- Do **not** use mock tests as evidence of correctness.
- Do **not** use toy examples, fabricated `EvidenceItem` objects, fake metrics,
  fake datasets, random arrays, empty temp repos, or synthetic benchmark tasks.
- Do **not** use `unittest.mock`, pytest `monkeypatch`, fake filesystem
  behavior, mocked CLI output, mocked LLM responses, or mocked execution results
  to claim implementation correctness.
- Tests must exercise the real workflow requirements represented by the task
  under `data/`.
- Every test input must either come directly from `data/` or be a clearly
  documented reduced fixture derived from that real task.
- Any reduced fixture must preserve provenance and be named/documented as
  derived from the real task.
- If the real task is too large or expensive, write a real-task
  smoke/integration test that uses a **minimal real subset**, not a fabricated
  replacement.
- If a feature cannot be tested with the current real task, mark it as
  **unverified** and do not claim it complete.

## Allowed

- Temporary output directories for test artifacts.
- Snapshot / golden files generated from the real task.
- Small derived fixtures copied or minimized from real task files, with
  provenance.
- Skipping **only** when the required real data is absent, with an explicit skip
  reason.
- Unit-level assertions **only** when they are fed by real task-derived inputs.

## Definition of Done

An implementation is **not complete** until:

1. It passes tests using the current real task under `data/`.
2. The tests generate or validate an auditable benchmark package.
3. The package contains real evidence references, real task reconstruction, real
   metric/audit decisions, and real blocker/proceed status.
4. No test success depends on mocked benchmark behavior.
