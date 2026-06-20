# sobench v2 Design Spec
**Date:** 2026-06-20
**Status:** Approved for implementation
**Supersedes:** `docs/superpowers/specs/2026-06-19-sobench-design.md` (P0 evidence loop — retained as-is; v2 builds on top)

---

## 1. Project Purpose

sobench is a spatial-omics benchmark construction system. It reads papers, method repos, datasets, and accumulated experience records; infers data contracts, metric contracts, method adapters, and environment specs; generates runnable task-specific benchmark projects; executes them; and records all outcomes as structured experience.

The final product is not an evidence log. It is an executable, task-specific benchmark workflow plus benchmark results. The 14-step evidence loop (sobench v1) is the evidence-acquisition layer — necessary infrastructure, not the deliverable.

**Architectural reference:** ModernTSF (`references/ModernTSF/`). Key lessons applied:
- Minimal fixed tool surface; skills and experience records are operational knowledge, not hard-coded logic.
- Scaffolding generates the skeleton; smoke-valid execution is the acceptance bar.
- A fixed result contract schema (`BenchRecord`) eliminates metric drift across methods.
- Self-describing method cards enable progressive disclosure without reading source.
- Experience reuse is the runtime equivalent of accumulating operational skill knowledge.

**Staged delivery:**
- **Stage 1 (scaffold):** `synthesize` generates a smoke-valid benchmark project — drivers pass the smoke check (run without crashing, produce valid labels on 100 spots).
- **Stage 2 (execute):** `execute-benchmark` runs all methods × cases and produces `results.csv` with ARI/NMI values.
- **Stage 3 (close loop):** `update-experience` feeds outcomes back into scoped experience records and the experience store; future synthesis runs use those records.

---

## 2. Package Structure

sobench is a single package. The v1 14-step loop is preserved exactly. The v2 synthesis layer is a subdirectory inside sobench.

```
sobench/
  # --- v1: evidence acquisition layer (unchanged) ---
  cli.py               ← adds 4 new subcommands; evidence-run replaces run (run kept as alias)
  runner.py            ← unchanged
  workspace.py         ← unchanged
  models.py            ← gains 5 new artifact dataclasses (Section 7)
  llm.py               ← unchanged
  steps/               ← all 14 steps unchanged

  # --- v2: synthesis layer (new subdirectory inside sobench) ---
  synthesis/
    __init__.py
    sweep.py           # orchestrates N×evidence-run → sweep_manifest.json
    synthesize.py      # reads workspaces → generates benchmark project
    env_builder.py     # conda env creation, interpreter path, env_record.json
    driver_gen.py      # LLM generate + smoke-run repair loop → driver_record.json
    data_adapter_gen.py  # generates shared data_adapter.py
    metrics_gen.py     # generates shared metrics.py from evaluation_contracts
    runner_gen.py      # generates run_benchmark.py
    assembler.py       # writes benchmark_projects/<task>_<dataset>/ tree
    experience_store.py  # read/write/retrieve experience_store/ index files

  execute_benchmark.py  # env creation + driver repair + full run → results.csv
  update_experience.py  # feed outcomes back into workspaces + experience_store/

tool/
  sobench.py           # unified agent entry point (mirrors ModernTSF tool/tsf.py)
                       # pure stdlib: argparse + subprocess; no torch, no llm imports

experience_store/      # cross-task operational knowledge index (git-tracked)
  methods/             # one JSON per method name
  datasets/            # one JSON per dataset stem
  metrics/             # one JSON per metric name

benchmark_projects/    # generated output (git-ignored)
  <task>_<dataset>/
    methods/<method>/
      driver.py
      env.yml
      method_card.md   # self-describing card (paper, API summary, config)
    data_adapter.py
    metrics.py
    run_benchmark.py
    results/
      results.csv
      <method>_<case>.json

.claude/skills/        # agent-facing operational instructions (mirrors ModernTSF pattern)
  sobench-evidence-run/SKILL.md
  sobench-sweep/SKILL.md
  sobench-synthesize/SKILL.md
  sobench-execute/SKILL.md
  sobench-update-experience/SKILL.md
  sobench-add-method/SKILL.md
```

---

## 3. CLI Surface

```bash
# Unified entry point (mirrors tool/tsf.py)
python tool/sobench.py <command> [args...]

# Evidence acquisition (v1, renamed)
sobench evidence-run  --task T --method M --case C   # was: sobench run
sobench check         --task T --method M --case C   # unchanged
sobench report        --task T --method M --case C   # unchanged
sobench scaffold      ...                            # unchanged

# Synthesis pipeline (v2, new)
sobench sweep          --task T --methods M1,M2,M3 --cases C1,C2 [--force]
sobench synthesize     --task T
sobench execute-benchmark --task T [--method M] [--case C]
sobench update-experience --task T

# Inspection and reporting
sobench status         --task T   # show sweep_manifest, driver statuses, results summary
sobench smoke          --task T --method M  # run driver smoke check standalone
```

`tool/sobench.py` is the single agent entry point — pure stdlib, no imports from sobench package. It wraps every command as a subprocess call so it can be invoked from any environment, including environments that lack the method deps.

---

## 4. Command Behaviour

### `sweep`

Idempotent. For each `(method, case)` pair: if workspace exists with `structural_check.passed == true`, skip (unless `--force`). Runs evidence-runs sequentially (one at a time; GPU contention risk in parallel).

**Prerequisite:** `benchmark_intent.md` must already exist for each `(task, case, method)` combination at `workspaces/<task>/<case>/<method>/benchmark_intent.md`. Use `sobench scaffold` to create them before running sweep. Sweep does not create intent files — it reads them.

After all runs complete:

```json
// workspaces/<task>/sweep_manifest.json
{
  "task": "spatial_domain_identification",
  "methods": ["STAGATE_pyG", "MENDER", "SpaGCN"],
  "cases": ["MERFISH_0.04", "MERFISH_0.09"],
  "entries": [
    {
      "method": "STAGATE_pyG", "case": "MERFISH_0.04",
      "workspace_path": "workspaces/spatial_domain_identification/MERFISH_0.04/STAGATE_pyG",
      "complete": true, "blocked": false, "blocker_reason": null
    },
    {
      "method": "MENDER", "case": "MERFISH_0.04",
      "complete": true, "blocked": true,
      "blocker_reason": "required obs column ct_obs absent"
    }
  ],
  "ready_for_synthesis": true
}
```

`ready_for_synthesis: true` when at least one entry is `complete: true, blocked: false`.

### `synthesize`

Reads `sweep_manifest.json`. For each unblocked entry:

1. **Experience lookup** — queries experience_store for compatible method/dataset/metric entries (Section 8).
2. **Source selection** — reads relevant repo source files (e.g. `Train_STAGATE.py`, `utils.py`); writes `source_selection.json`.
3. **Env generation** — derives `env.yml` from `repo_evidence.dependencies` + experience; writes `env_plan.json`.
4. **Driver generation** — LLM call with fixed contract + source files + evidence + prior operational evidence; writes initial `driver.py` and `driver_plan.json`.
5. **Method card generation** — LLM generates `method_card.md` (paper, venue, API summary, config pointer).
6. **Shared artefacts** — generates `data_adapter.py`, `metrics.py`, `run_benchmark.py` once per task.
7. **Assembly** — `assembler.py` writes the full `benchmark_projects/<task>/` tree.

`synthesize` is **LLM-only** — no subprocess, no conda operations.

Per-method artefacts written to each workspace:
- `env_plan.json` — `{method, env_name, env_spec_hash, conda_spec, packages[], python_version}`
- `env.yml` — rendered conda environment file
- `driver_plan.json` — `{method, case, source_files_used, driver_source, generation_prompt_hash, api_calls_identified}`
- `source_selection.json` — `{files_read[], why_selected}`

Task-level artefacts written to `benchmark_projects/<task>/`:
- `methods/<method>/driver.py`, `env.yml`, `method_card.md`
- `data_adapter.py`, `metrics.py`, `run_benchmark.py`

### `execute-benchmark`

All subprocess activity is owned here. Sequence per method:

**Step 1 — Environment creation**
```
conda env create -f methods/<method>/env.yml -n sobench-method-<method>
```
Writes `env_record.json` to workspace:
```json
{
  "method": "STAGATE_pyG",
  "env_name": "sobench-method-STAGATE_pyG",
  "interpreter_path": "/path/to/envs/sobench-method-STAGATE_pyG/bin/python",
  "env_spec_hash": "sha256:abc123",
  "status": "created",   // created | cached | env_failed
  "create_log": "..."
}
```
If `env_failed`: method is skipped; recorded in experience store.

**Step 2 — Preflight check**
Reads `repo_evidence.required_obs_columns`. Checks target h5ad for each column before any execution. If absent: `driver_record.final_status = "blocked_missing_input_column"`, `blocked_columns = [...]`. No repair attempts.

**Step 3 — Driver smoke repair loop**
```
for attempt in range(max_attempts=3):
    run: <interpreter> driver.py
           --data <smallest_h5ad>
           --output /tmp/smoke_<method>.json
           --method-dir <repo_path>
           --work-dir <scratch_dir>
           --smoke
    validate output (7 checks below)
    if valid: final_status = "smoke_valid"; break
    else: LLM repair call with (driver.py + stderr + repo source + evaluation_contract)
          → overwrite driver.py; record attempt
```

**Smoke output validation (all 7 must pass):**
1. File exists and JSON parses
2. `cell_ids` and `labels` keys present
3. `len(cell_ids) == len(labels)`
4. `len(labels) > 0`
5. No null values in either list
6. All labels are `str` or all `int` (consistent type)
7. `cell_ids` exactly match the 100-spot subsample's `obs_names`

`--smoke` flag: subsample to 100 spots, reduce epochs/iterations, but **must still produce cluster labels**. It is not a dry-run.

**Driver CLI contract (fixed, injected into every generation prompt):**
```
python driver.py
  --data        path/to/input.h5ad
  --output      path/to/result.json
  --method-dir  path/to/method/repo
  --work-dir    path/to/scratch/
  --smoke       (optional: 100 spots, reduced epochs, still produces labels)
```
Output schema (always written to `--output`):
```json
{"cell_ids": ["spot1", ...], "labels": [0, 1, ...], "status": "success", "metadata": {}}
```

Writes `driver_record.json` to workspace:
```json
{
  "method": "STAGATE_pyG", "case": "MERFISH_0.04",
  "preflight_passed": true,
  "attempts": [
    {"attempt": 1, "driver_source": "...", "stdout": "...", "stderr": "...",
     "validation_failures": ["len mismatch"], "repair_prompt_hash": "abc123"}
  ],
  "final_status": "smoke_valid",   // smoke_valid | crashed | timeout | invalid_output |
                                    // blocked_missing_input_column
  "source_files_used": ["Train_STAGATE.py", "utils.py"]
}
```

**Step 4 — Full benchmark run**
Runs `run_benchmark.py` for all `smoke_valid` methods × all cases. Writes:
- `results/results.csv` — one row per `(method, case)` with ARI, NMI, runtime, status
- `results/<method>_<case>.json` — full `BenchRecord`

Skipped methods (env_failed, crashed, blocked) are recorded in results.csv with explicit status and reason. results.csv always exists after execute-benchmark, even if all methods failed.

### `update-experience`

Pure file I/O + LLM. No subprocess. Reads `BenchRecord` JSONs and `driver_record.json` per workspace. Writes back into each workspace's `experience_record.json` (append-only on `execution_outcomes` list; original `finding` and `evidence` are never mutated). Writes to `experience_store/` index (Section 8).

**Status graduation:**
| Condition | `experience_record.status` |
|---|---|
| Execution succeeded, metric within ±0.1 of paper-reported value | `benchmark_executed` |
| Execution succeeded, metric diverges from paper claim | `benchmark_executed` (divergence noted in outcome) |
| Driver smoke_valid but full run failed/timed out | `execution_failed` |
| `blocked_missing_input_column` | `data_contract_blocked` |
| Env creation failed | `env_failed` |
| Driver repair exhausted | `adapter_failed` |
| Not yet executed | `scaffold_generated` or `driver_smoke_valid` |

---

## 5. Driver Generation Prompt Structure

Initial generation (inside `synthesize`):

```
[FIXED DRIVER CONTRACT]
<CLI interface, output schema>

[TASK CONTEXT]
task: spatial_domain_identification
method: STAGATE_pyG
case: MERFISH_0.04
evaluation_contract: {resolved metric: ARI, implementation: sklearn.metrics.adjusted_rand_score}
data_manifest: {h5ad path, obs columns, spatial key}

[METHOD SOURCE FILES]
--- Train_STAGATE.py ---
<full source>
--- utils.py ---
<full source>

[PRIOR OPERATIONAL EVIDENCE — entry_id: method-STAGATE_pyG-20260620-001,
 task: spatial_domain_identification, status: driver_smoke_valid, confidence: medium]
This is prior operational evidence, not ground truth. Adapt it; do not copy blindly.
<validated_driver_template>
[END PRIOR OPERATIONAL EVIDENCE]

[INSTRUCTION]
Generate a single driver.py that satisfies the contract above.
```

Repair prompt adds: current `driver.py` source + full `stderr` + `stdout` + validation failures. Source files re-included.

---

## 6. Result Contract

Fixed `BenchRecord` schema (Pydantic, no extra fields). Equivalent to ModernTSF's `RunRecord`.

```python
class SpatialMetricSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ARI: float | None = None
    NMI: float | None = None

class BenchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str           # "<method>__<dataset>__<case>"
    task: str
    method: str
    dataset: str
    case: str
    metrics: SpatialMetricSet
    status: str              # success | failed | skipped | timeout
    skip_reason: str | None = None
    duration_seconds: float | None = None
    driver_repair_count: int
    env_name: str
    created_at: str          # ISO-8601
```

`results.csv` is derived by flattening all `BenchRecord` objects. Column order is fixed. Missing metric = null, not a shifted column.

---

## 7. New Artifact Dataclasses (models.py)

Five new dataclasses following the existing from_dict/to_dict/validate pattern:

| Class | Artifact file | Written by |
|---|---|---|
| `SweepManifest` | `workspaces/<task>/sweep_manifest.json` | `sweep` |
| `EnvPlan` | workspace `env_plan.json` | `synthesize` |
| `EnvRecord` | workspace `env_record.json` | `execute-benchmark` |
| `DriverPlan` | workspace `driver_plan.json` | `synthesize` |
| `DriverRecord` | workspace `driver_record.json` | `execute-benchmark` |

`BenchRecord` lives in `sobench/synthesis/bench_record.py` (Pydantic with `model_config = ConfigDict(extra="forbid")`, not a plain dataclass) to enforce the fixed result contract at write time.

`source_selection.json` is written by `synthesize` as a plain JSON file (no round-trip dataclass needed); it records which repo source files were read and why, for auditability.

---

## 8. Experience Store

Cross-task operational knowledge. Written by `update-experience`; read by `synthesize`.

```
experience_store/
  methods/<method_name>.json    # e.g. STAGATE_pyG.json
  datasets/<dataset_stem>.json  # e.g. MERFISH.json
  metrics/<metric_name>.json    # e.g. ARI.json
```

Each file is a JSON array of entries (newest-first by `created_at`). Entries are append-only; the original entry is never mutated. A superseding failure entry carries a `supersedes` pointer.

**Base entry schema (all three dimensions):**
```json
{
  "entry_id": "method-STAGATE_pyG-20260620-001",
  "task": "spatial_domain_identification",
  "dataset": "MERFISH_0.04",
  "method": "STAGATE_pyG",
  "source_workspace": "workspaces/spatial_domain_identification/MERFISH_0.04/STAGATE_pyG",
  "created_at": "2026-06-20",
  "evidence_refs": ["evaluation_contract.json", "driver_record.json"],
  "status": "driver_smoke_valid",
  "confidence": "medium",
  "failure_conditions": []
}
```

**Method entry extra fields:**
```json
{
  "env_spec_hash": "sha256:abc123",
  "validated_env_yml": "...",
  "validated_driver_template": "...",
  "repair_patterns": [
    {"stderr_pattern": "Spatial_Net not found",
     "fix": "call Cal_Spatial_Net before train_STAGATE"}
  ],
  "required_obs_columns": []
}
```

**Dataset entry extra fields:**
```json
{
  "spatial_key": "spatial",
  "ground_truth_column": "Cell_class",
  "h5ad_fingerprint": {
    "obs_columns": ["Cell_class", "batch"],
    "obsm_keys": ["spatial"],
    "x_shape": [2000, 1122],
    "has_raw": false
  },
  "h5ad_structure_notes": "X is raw counts; no highly_variable pre-set"
}
```

**Metric entry extra fields:**
```json
{
  "implementation": "sklearn.metrics.adjusted_rand_score(true_labels, pred_labels)",
  "ground_truth_source": "obs['Cell_class']",
  "input_type": "integer_cluster_labels",
  "known_risks": ["sensitive to cluster count k"]
}
```

**Compatibility rules (newest compatible, not newest):**

| Index | Compatible when |
|---|---|
| Method | `entry.method == target` AND `entry.env_spec_hash == hash(target_env_yml)` AND status not `adapter_failed` or `env_failed` |
| Dataset | `entry.dataset_stem == target_stem` AND `obsm_keys` intersect (spatial key present), `obs_columns` overlap ≥ 80%, `x_shape[1]` within 20% |
| Metric | `entry.metric == target` AND `entry.input_type` matches label type from `evaluation_contract` |

Fallback to LLM inference when no compatible entry exists. Select highest-confidence + highest-status (by workflow order: `benchmark_executed` > `driver_smoke_valid` > `scaffold_generated`); ties broken by `created_at` descending.

**Workflow status order (ascending):**
`scaffold_generated` < `driver_smoke_valid` < `benchmark_executed`

**Failure statuses (excluded from positive reuse):**
`adapter_failed`, `env_failed`, `data_contract_blocked`, `execution_failed`

**Superseding failure entry:**
```json
{
  "entry_id": "method-STAGATE_pyG-20260621-002",
  "supersedes": "method-STAGATE_pyG-20260620-001",
  "task": "cell_type_deconvolution",
  "status": "adapter_failed",
  "failure_conditions": [
    "driver template used adata.obsm['spatial'] — absent in Visium_brain h5ad"
  ]
}
```

Retrieval skips entries whose `entry_id` appears in a compatible entry's `supersedes` field.

---

## 9. Method Cards

`synthesize` generates `method_card.md` for each method alongside `driver.py`. Mirrors ModernTSF's model README card pattern.

```markdown
---
method: "STAGATE_pyG"
task: "spatial_domain_identification"
paper_title: "Deciphering spatial domains from spatially resolved transcriptomics with an adaptive graph attention auto-encoder"
venue: "Nature Communications 2022"
arxiv: "https://arxiv.org/abs/2202...."
repo: "data/spatial_domain_identification_task/codes/STAGATE_pyG"
driver: "methods/STAGATE_pyG/driver.py"
env: "methods/STAGATE_pyG/env.yml"
primary_metric: "ARI"
---
# STAGATE_pyG

...one-paragraph summary from paper_evidence...

## API

...key function signatures extracted from repo_evidence...

## In sobench
Driver: `methods/STAGATE_pyG/driver.py`
Env: `methods/STAGATE_pyG/env.yml`
Primary metric: ARI (sklearn.metrics.adjusted_rand_score)
```

The card is self-describing: a future agent can answer "what is STAGATE_pyG, how do I run it, what metric does it use" without reading source files. This is the progressive-disclosure pattern from ModernTSF's `understand-model` skill.

---

## 10. Agent Skills

Six skills in `.claude/skills/` — operational instructions that wrap `tool/sobench.py` commands. Skills contain no logic; they describe when to invoke which command, what to check, and how to interpret results. This mirrors the ModernTSF pattern exactly.

| Skill | Wraps | When to use |
|---|---|---|
| `sobench-evidence-run` | `evidence-run` | Adding a new method/case to an existing task |
| `sobench-sweep` | `sweep` | Running evidence-run across all methods/cases for a task |
| `sobench-synthesize` | `synthesize` | Generating a benchmark project from accumulated evidence |
| `sobench-execute` | `execute-benchmark` + `smoke` | Executing the benchmark and repairing drivers |
| `sobench-update-experience` | `update-experience` | Closing the loop after execution |
| `sobench-add-method` | scaffold + evidence-run + synthesize | Adding a new spatial-omics method to an existing task |

---

## 11. Experience Reuse as Capability Growth

At P0 (sobench v1), experience records exist but are not reused. At v2 (this spec), experience is actively reused in `synthesize` via the three-dimensional index. As more tasks are processed:

- Method entries accumulate repair patterns → fewer repair attempts for known methods on new tasks.
- Dataset entries accumulate h5ad fingerprints → data_adapter.py generation skips LLM inference for known datasets.
- Metric entries accumulate validated implementations → metrics.py is generated from store rather than inferred.

This is the minimal capability growth path: the system does not require a retrieval database or vector embeddings. The experience_store is a flat JSON index, human-readable, git-tracked. Future phases may add vector search over the `finding` field when the number of entries grows large enough to require it.

---

## 12. Testing Strategy

**Tier 1 — pure Python, always run (no LLM, no subprocess):**
- `tests/synthesis/test_sweep_manifest.py` — SweepManifest from/to/validate; idempotency logic; `ready_for_synthesis` flag
- `tests/synthesis/test_experience_store.py` — entry_id generation; compatibility rules; supersedes resolution; retrieval ordering; all three index dimensions
- `tests/synthesis/test_driver_validation.py` — 7-check smoke output validator with valid/invalid JSON fixtures
- `tests/synthesis/test_bench_record.py` — BenchRecord Pydantic validation; `extra="forbid"` enforcement; results.csv derivation

**Tier 2 — real LLM, skip if no key:**
- `tests/synthesis/test_driver_gen.py` — generate driver for STAGATE_pyG from real repo_evidence + real source files; assert valid Python, correct CLI flags, correct output schema reference
- `tests/synthesis/test_synthesize.py` — full synthesize over real spatial_domain_identification workspaces; assert benchmark_projects/ tree contains all expected files; assert method_card.md has required frontmatter fields

**Tier 3 — real execution, skip if method env absent:**
- `tests/test_execute_benchmark_real.py` — execute-benchmark on MERFISH_0.04 × STAGATE_pyG; assert results.csv exists with at least one non-null ARI row; assert driver_record.final_status == "smoke_valid"

**Fixtures:** `tests/fixtures/intent_<method>_merfish.md` for each of the three methods, following the provenance-header convention established by `intent_stagate_dlpfc.md`.

---

## 13. Design Constraints and Non-Goals

**In scope for v2:**
- `sweep`, `synthesize`, `execute-benchmark`, `update-experience` commands
- Three-dimensional experience store with compatibility-based retrieval
- Driver generate→smoke-run→repair loop with 7-check validation
- Fixed `BenchRecord` result contract (no column drift)
- Method cards (self-describing, progressive-disclosure)
- Six agent skills as operational instructions
- `tool/sobench.py` unified entry point

**Explicitly out of scope for v2:**
- Vector/embedding-based experience retrieval (flat JSON index suffices for ≤50 entries)
- Parallel sweep execution (sequential; `--jobs N` deferred)
- Web-based result dashboard or leaderboard
- Automatic paper/code crawling or downloading
- Support for non-spatial-omics tasks
- Plugin registry for new metric or data types (add by editing experience_store + skills)
