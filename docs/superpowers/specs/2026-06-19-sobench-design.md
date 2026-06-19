# sobench Design Spec
**Date:** 2026-06-19
**Status:** Approved for implementation

---

## 1. Project Purpose

`sobench` is an evidence-guided agent for reproducible spatial-omics benchmark construction. It does not run benchmarks generically. It reconstructs what benchmark a method paper intended, audits whether that benchmark is valid, attempts execution when possible, diagnoses blockers when not, and records scoped experience that can inform future tasks.

The first version proves the smallest useful single-agent benchmark-construction loop. Multi-agent architecture, vector memory, dashboards, and complex coordinate ontologies are explicitly deferred. Future evolution must come from repeated evidence across tasks, not from speculative architecture.

The experience loop is staged:
- **P0 (this version):** experience records written to disk, human-inspectable
- **P1:** `sobench` searches prior records on demand
- **P2:** relevant scoped experience selectively injected into future runs

---

## 2. Package Name and CLI

Package: `sobench`

```
sobench scaffold --task <task> --method <method> --case <case> [--paper path] [--repo path] [--data path]
sobench run      --task <task> --method <method> --case <case>
sobench check    --task <task> --method <method> --case <case>
sobench report   --task <task> --method <method> --case <case>
```

- `scaffold` creates the workspace directory and writes a `benchmark_intent.md` template. Optional flags `--paper`, `--repo`, `--data` populate convenience lines in the template — they do not bypass it.
- `run` executes all 14 steps in order for the specified workspace.
- `check` runs s14 standalone to verify structural completeness.
- `report` prints a human-readable summary from completed artifacts.

CLI identifies and manages the workspace only. Scientific context comes from `benchmark_intent.md`.

---

## 3. Workspace Layout

```
workspaces/
  <task>/
    <case>/
      <method>/
        benchmark_intent.md          # PRIMARY INPUT — human-editable
        parsed_intent.json           # internal scratchpad, inspectable
        paper_evidence.json
        repo_evidence.json
        data_manifest.json
        task_spec.json
        evaluation_contract.json
        risk_audit.json
        blocker.json                 # always written; blocked: false when clear
        execution_log.json           # always written after s09
        raw_observations.json
        result_validity_audit.json
        interpretation.json
        experience_record.json
        structural_check.json
```

Example path: `workspaces/spatial_domain_identification/DLPFC_151673/STAGATE/`

---

## 4. Package Structure

```
sobench/
  __init__.py
  cli.py          # argparse, four subcommands
  workspace.py    # path resolution, scaffold, read/write artifacts, read_blocker()
  llm.py          # thin wrapper: prompt → text, no business logic
  models.py       # all dataclasses with from_dict / to_dict / validate
  runner.py       # calls steps in order; skip logic for blocked cycles
  steps/
    __init__.py
    s01_ensure_workspace.py
    s02_parse_intent.py
    s03_extract_paper_evidence.py
    s04_inspect_repo_evidence.py
    s05_build_data_manifest.py
    s06_draft_task_spec.py
    s07_draft_evaluation_contract.py
    s08_draft_risk_audit.py
    s09_execute_or_block.py
    s10_record_raw_observations.py
    s11_audit_result_validity.py
    s12_write_interpretation.py
    s13_write_experience_record.py
    s14_structural_check.py

data/                  # existing — untouched by runner
tests/                 # per-step unit tests + integration smoke test
```

Each step module exports one function: `run(workspace: Workspace) -> None`. It reads prior artifacts via `workspace`, calls the LLM if needed, and writes exactly one artifact.

---

## 5. Runner Control Flow

```python
SKIP_WHEN_BLOCKED = {
    "s10_record_raw_observations",
    "s11_audit_result_validity",
    "s12_write_interpretation",
}

for step in STEPS:
    if workspace.blocked and step.name in SKIP_WHEN_BLOCKED:
        continue
    step.run(workspace)
```

`workspace.blocked` is set to `True` when `blocker.json` is written with `blocked: true`. Steps s13 and s14 always run regardless of blocker or validity state.

`blocker.blocked: true` means only: a condition exists that prevents the current cycle from reaching the next required state. It is not used for warnings, partial evidence, or risks that downstream steps can work around.

---

## 6. Primary Human Input

**benchmark_intent.md** — *What does the human want to reconstruct?*

```markdown
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
```

---

## 7. Artifact Schemas

All JSON artifacts share three top-level identity fields where applicable:
`"task"`, `"method"`, `"case"`.

### 7.1 parsed_intent.json
Internal scratchpad. Structured extraction from `benchmark_intent.md`. Used by downstream steps to avoid re-parsing markdown. Not a required artifact for structural check.

Fields: `task`, `method`, `case`, `paper_path`, `repo_path`, `data_notes`, `reconstruction_goal`, `human_observations`.

### 7.2 paper_evidence.json
*What does the paper say?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "source": "STAGATE.pdf",
  "evaluation_contexts": [
    {
      "id": "ctx-001",
      "task": "spatial_domain_identification",
      "cases": ["DLPFC_151673", "DLPFC_151507"],
      "metrics": [
        {"name": "ARI", "confidence": "high", "quote": "we report ARI across all slices"},
        {"name": "NMI", "confidence": "medium", "quote": "NMI shown in supplement"}
      ],
      "downstream_tasks": [],
      "notes": "primary evaluation; k not stated explicitly"
    }
  ],
  "coordinate_evidence": "paper references spatial coordinates but does not specify coordinate space or scale",
  "coordinate_open_questions": ["which coordinate space is used for spatial graph construction?"],
  "ambiguities": ["k selection procedure not described", "preprocessing steps underspecified"],
  "missing": ["no train/test split described"]
}
```

### 7.3 repo_evidence.json
*What does the code appear to do?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "entry_points": ["tutorial.ipynb", "run_STAGATE.py"],
  "dependencies": {"python": "3.8", "packages": ["scanpy==1.9", "torch==1.11"]},
  "hardcoded_paths": ["./data/DLPFC/"],
  "metric_implementations": [
    {"name": "ARI", "file": "utils.py", "line": 42, "matches_paper": true}
  ],
  "deviations_from_paper": ["tutorial uses raw counts; paper implies normalized input"],
  "coordinate_evidence": "spatial coords loaded from obsm['spatial']; no scale factor applied in tutorial",
  "coordinate_open_questions": ["is obsm['spatial'] in pixel or array space?"],
  "ambiguities": ["tutorial uses different slice than paper figure 2"],
  "missing": ["no requirements.txt; only conda env yaml"]
}
```

Note: missing repo path is recorded in `missing`, not a blocker. Risk is surfaced in s08.

### 7.4 data_manifest.json
*What data is required, available, missing, or unknown?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "required": [
    {
      "role": "expression_matrix_with_coords",
      "format": "AnnData .h5ad",
      "expected_path": "data/DLPFC/151673.h5ad",
      "available": false,
      "notes": "not found locally; spatialLIBD is likely source"
    },
    {
      "role": "ground_truth_labels",
      "format": "obs column in .h5ad",
      "expected_path": null,
      "available": false,
      "notes": "expected inside expression file; column name unclear from repo"
    }
  ],
  "coordinate_evidence": "repo loads obsm['spatial'] from .h5ad; paper does not specify space",
  "coordinate_assumptions": "none made yet — awaiting data file inspection",
  "coordinate_open_questions": ["pixel vs array space?", "scale factor needed?"],
  "coordinate_checks": [],
  "open_questions": ["ground truth column name in .h5ad?"]
}
```

Coordinate fields use free-form strings and lists at this stage. No fixed taxonomy is imposed. A richer coordinate tool or skill may emerge after patterns recur across multiple tasks.

### 7.5 task_spec.json
*What benchmark task is being reconstructed?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "source_context": "ctx-001",
  "input_description": "AnnData with expression matrix and spatial coordinates",
  "expected_output": "cluster label per spot",
  "primary_metric": {"name": "ARI", "resolved": true},
  "assumptions": [
    "raw counts as input based on repo evidence",
    "ground truth from obs column — name to be confirmed from data"
  ],
  "unresolved": ["cluster count k not stated in paper"]
}
```

### 7.6 evaluation_contract.json
*What metric and data requirements are resolved, ambiguous, or blocked?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "metric": {
    "name": "ARI",
    "resolved": true,
    "implementation": "sklearn.metrics.adjusted_rand_score",
    "provenance": "stated in paper ctx-001; confirmed in utils.py:42",
    "known_risks": ["sensitive to k; k is unresolved"]
  },
  "data_requirements_resolved": false,
  "data_blockers": ["expression file not found locally"],
  "open_questions": ["ground truth column name", "k selection"]
}
```

`metric.resolved: false` is a valid output. The contract records uncertainty, it does not invent resolution.

### 7.7 risk_audit.json
*What benchmark-construction risks are known?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "risks": [
    {
      "id": "risk-001",
      "category": "data",
      "description": "required data file not located locally",
      "severity": "high",
      "evidence": "data_manifest.required[0].available=false",
      "mitigation": "download from spatialLIBD; update data_manifest"
    },
    {
      "id": "risk-002",
      "category": "metric",
      "description": "cluster count k not specified in paper; assumed from domain knowledge",
      "severity": "medium",
      "evidence": "task_spec.unresolved[0]",
      "mitigation": "document assumption; report sensitivity if run completes"
    },
    {
      "id": "risk-003",
      "category": "coordinate",
      "description": "coordinate space of obsm['spatial'] unconfirmed",
      "severity": "low",
      "evidence": "repo_evidence.coordinate_open_questions[0]",
      "mitigation": "inspect data file when available; record in data_manifest"
    }
  ],
  "overall_confidence": "low",
  "blocker_risk_ids": ["risk-001"]
}
```

### 7.8 blocker.json
*Is the loop blocked, by what, and what would resolve it?* Always written.

No blocker:
```json
{
  "blocked": false,
  "raised_by_step": null,
  "reason": null,
  "detail": null,
  "evidence": null,
  "resolution": null,
  "human_action_required": false
}
```

Blocked:
```json
{
  "blocked": true,
  "raised_by_step": "s09_execute_or_block",
  "reason": "required data file not found",
  "detail": "data/DLPFC/151673.h5ad does not exist at expected path",
  "evidence": "data_manifest.required[0].available=false",
  "resolution": "download DLPFC 151673 from spatialLIBD and update data_manifest.json",
  "human_action_required": true
}
```

### 7.9 execution_log.json
*What command was attempted?* Always written after s09.

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "status": "not_attempted | success | partial | failed",
  "command": "python run_STAGATE.py --slice 151673",
  "stdout_excerpt": "...",
  "stderr_excerpt": "...",
  "duration_seconds": null,
  "environment": {"python": "3.10", "platform": "linux"},
  "output_files": []
}
```

### 7.10 raw_observations.json
*What actually happened, without interpretation?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "outputs_found": ["results/151673_labels.csv"],
  "output_shape": {"rows": 3639, "columns": 2},
  "metric_raw": {"name": "ARI", "value": 0.52},
  "stdout_summary": "Training complete. 7 clusters assigned.",
  "stderr_summary": "",
  "anomalies_observed": []
}
```

### 7.11 result_validity_audit.json
*Are the outputs valid enough to interpret?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "result_valid": true,
  "checks": [
    {"check": "output row count matches input spot count", "passed": true},
    {"check": "cluster count matches assumed k=7", "passed": true},
    {"check": "no NaN or missing labels", "passed": true}
  ],
  "validity_reasoning": "outputs structurally consistent with expected task output",
  "warnings": ["k=7 was assumed, not confirmed from paper"]
}
```

### 7.12 interpretation.json
*What can and cannot be concluded?*

Normal (valid result):
```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "primary_metric_value": 0.52,
  "can_conclude": ["ARI=0.52 is within the range reported in paper figure 2"],
  "cannot_conclude": ["whether normalized input would change result", "sensitivity to k"],
  "benchmark_result_claimed": true,
  "open_questions": ["paper supplement NMI not computed"],
  "interpretation": "result consistent with paper; raw-counts assumption appears to hold for this case"
}
```

Invalid result (execution ran but validity failed):
```json
{
  "primary_metric_value": null,
  "can_conclude": [],
  "cannot_conclude": ["result validity check failed; no benchmark result can be claimed"],
  "benchmark_result_claimed": false,
  "interpretation": "execution ran but outputs did not pass validity audit"
}
```

### 7.13 experience_record.json
*What scoped, evidence-backed hypothesis should be carried forward?*

Always written. Structured for future retrieval (P1/P2) even though no retrieval is implemented at P0.

```json
{
  "id": "exp-001",
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "tags": ["ARI", "raw_counts", "DLPFC", "k_assumption"],
  "finding": "raw counts produce ARI consistent with paper; normalization assumption is ambiguous but low-risk for this case",
  "evidence": ["repo_evidence.deviations_from_paper[0]", "interpretation.can_conclude[0]"],
  "confidence": "medium",
  "failure_conditions": [
    "may not hold outside DLPFC",
    "untested with normalized input",
    "k sensitivity unknown"
  ],
  "status": "hypothesis",
  "created": "2026-06-19"
}
```

For blocked cycles the experience record captures what was attempted and what was learned about the blocker:
```json
{
  "id": "exp-001",
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "tags": ["data_missing", "spatialLIBD", "DLPFC"],
  "finding": "DLPFC 151673 .h5ad not present locally; spatialLIBD is the expected source",
  "evidence": ["data_manifest.required[0]", "blocker.detail"],
  "confidence": "high",
  "failure_conditions": [],
  "status": "hypothesis",
  "created": "2026-06-19"
}
```

### 7.14 structural_check.json
*Is the cycle structurally complete, regardless of whether benchmark execution succeeded?*

```json
{
  "task": "spatial_domain_identification",
  "method": "STAGATE",
  "case": "DLPFC_151673",
  "passed": true,
  "structurally_complete": true,
  "completed_with_blocker": true,
  "execution_attempted": false,
  "benchmark_result_claimed": false,
  "checks": [
    {"artifact": "benchmark_intent.md",       "present": true},
    {"artifact": "paper_evidence.json",        "present": true, "valid": true},
    {"artifact": "repo_evidence.json",         "present": true, "valid": true},
    {"artifact": "data_manifest.json",         "present": true, "valid": true},
    {"artifact": "task_spec.json",             "present": true, "valid": true},
    {"artifact": "evaluation_contract.json",   "present": true, "valid": true},
    {"artifact": "risk_audit.json",            "present": true, "valid": true},
    {"artifact": "blocker.json",               "present": true, "valid": true},
    {"artifact": "execution_log.json",         "present": true, "valid": true},
    {"artifact": "raw_observations.json",      "present": false, "expected_given_blocker": false},
    {"artifact": "result_validity_audit.json", "present": false, "expected_given_blocker": false},
    {"artifact": "interpretation.json",        "present": false, "expected_given_blocker": false},
    {"artifact": "experience_record.json",     "present": true, "valid": true},
    {"artifact": "structural_check.json",      "present": true}
  ],
  "missing_unacknowledged": [],
  "warnings": ["execution not attempted — blocked on missing data"]
}
```

`passed: false` only when `missing_unacknowledged` is non-empty — i.e., a required artifact is absent without a blocker explaining it.

---

## 8. Step-by-Step Behavior

### s01_ensure_workspace
- Reads: CLI args
- Does: verifies workspace directory and `benchmark_intent.md` exist
- Writes: nothing
- Error (not blocker) if workspace missing

### s02_parse_intent
- Reads: `benchmark_intent.md`
- Calls: LLM — extract task, method, case, paper path, repo path, data notes, reconstruction goal, human observations
- Writes: `parsed_intent.json`
- Blocker: if method and task cannot be parsed

### s03_extract_paper_evidence
- Reads: `parsed_intent.json` → paper path; extracts PDF text
- Calls: LLM — all evaluation contexts, metrics with confidence and quotes, coordinate evidence, ambiguities, missing information
- Writes: `paper_evidence.json`
- Blocker: if paper path absent and unparseable from intent

### s04_inspect_repo_evidence
- Reads: `parsed_intent.json` → repo path; walks repo files
- Calls: LLM — entry points, dependencies, metric implementations, deviations, coordinate evidence, ambiguities
- Writes: `repo_evidence.json` (with `missing` populated if repo path absent)
- Never sets `blocked: true` — missing repo is a risk, not a cycle blocker

### s05_build_data_manifest
- Reads: `paper_evidence.json`, `repo_evidence.json`, `parsed_intent.json`
- Calls: LLM — enumerate required data roles, infer expected paths
- Does: checks each expected path with `Path.exists()` directly
- Writes: `data_manifest.json`
- Never sets `blocked: true` — missing data is recorded here, blocking decision made at s09

### s06_draft_task_spec
- Reads: `paper_evidence.json`, `repo_evidence.json`, `data_manifest.json`, `parsed_intent.json`
- Calls: LLM — select one evaluation context, reconstruct concrete task, list assumptions and unresolved questions
- Writes: `task_spec.json`
- Blocker: if no evaluation context can be selected with sufficient confidence

### s07_draft_evaluation_contract
- Reads: `task_spec.json`, `paper_evidence.json`, `repo_evidence.json`, `data_manifest.json`
- Calls: LLM — resolve data and metric requirements, flag ambiguous or blocked items
- Writes: `evaluation_contract.json`
- `metric.resolved: false` is valid output

### s08_draft_risk_audit
- Reads: all prior artifacts
- Calls: LLM — enumerate risks across data, metric, coordinate, code, reproducibility
- Writes: `risk_audit.json`
- Always writes, even if risk list is empty

### s09_execute_or_block
- Reads: `task_spec.json`, `evaluation_contract.json`, `risk_audit.json`, `data_manifest.json`
- Does: checks feasibility — required data present, entry point known, no unresolved high-severity blocker risk
- If feasible: runs declared command via `subprocess`, captures stdout/stderr
- If not feasible: sets `blocker.blocked: true`
- Writes: `blocker.json` (always), `execution_log.json` (always, `status: "not_attempted"` if blocked)

### s10_record_raw_observations
- Skipped if `workspace.blocked`
- Reads: `execution_log.json`, output files listed therein
- Calls: LLM only if output file or metric column is ambiguous
- Writes: `raw_observations.json`

### s11_audit_result_validity
- Skipped if `workspace.blocked`
- Reads: `raw_observations.json`, `task_spec.json`, `evaluation_contract.json`
- Calls: LLM — structural validity checks, plausibility assessment
- Writes: `result_validity_audit.json`

### s12_write_interpretation
- Skipped if `workspace.blocked` (pre-execution blocker; execution was never attempted)
- Runs if execution was attempted, even if `result_valid: false`
- Reads: `result_validity_audit.json`, `raw_observations.json`, `task_spec.json`, `paper_evidence.json`
- Calls: LLM — what can and cannot be concluded; compare to paper claims
- Writes: `interpretation.json`
  - If `result_valid: false`: minimal interpretation, `benchmark_result_claimed: false`
  - LLM prompt explicitly prohibits promoting unresolved metrics or unapproved conclusions

### s13_write_experience_record
- Always runs
- Reads: all available artifacts
- Calls: LLM — scoped, evidence-backed hypothesis with tags, confidence, failure conditions
- Writes: `experience_record.json`
- For blocked cycles: captures what was attempted and what was learned about the blocker
- `status` is always `"hypothesis"` at P0

### s14_structural_check
- Always runs
- Reads: all artifacts; reads `blocker.json` to determine which post-execution artifacts are excused
- Does: pure Python — presence and basic schema validity checks; computes all summary fields
- Writes: `structural_check.json`
- No LLM call

---

## 9. Experience Loop (Staged)

| Phase | Behavior |
|-------|----------|
| P0 (this version) | Records written to disk; human-inspectable |
| P1 | `sobench` searches prior experience records on demand when hitting ambiguities |
| P2 | Relevant scoped experience selectively injected into future runs |

Experience records are structured for future retrieval from P0 onward: `task`, `method`, `case`, `tags`, `finding`, `evidence`, `confidence`, `status`, `failure_conditions`.

---

## 10. Design Constraints and Non-Goals

**In scope for P0:**
- Deterministic 14-step CLI-driven outer loop
- File-based artifacts with consistent schema
- Structural completeness check independent of execution success
- Evidence-backed LLM sub-steps with uncertainty surfaced, not suppressed
- Blocked cycles are first-class: structurally complete when blocker is explicit

**Explicitly out of scope for P0:**
- Database or vector memory
- Experience record retrieval or injection
- Multi-agent architecture
- Dashboard or leaderboard
- Fixed coordinate ontology
- Plugin registry or configurable pipeline
- Any evolution of tools, skills, or memories not backed by repeated task evidence
