# sobench v3 Design Spec
**Date:** 2026-06-20
**Status:** Approved for implementation
**Supersedes:** `docs/superpowers/specs/2026-06-19-sobench-design.md` (v1 evidence loop) and `docs/superpowers/specs/2026-06-20-sobench-v2-design.md` (v2 synthesis layer — staged for deletion)

---

## 1. Project Purpose

sobench is a hybrid benchmark-construction substrate for spatial omics. It is not the v1 evidence log and not a closed LLM pipeline. It provides reproducible, deterministic machinery operated by an external coding agent.

**The single most important rule — the hybrid boundary:**

| Plane | Owner | Contains | LLM calls? |
|---|---|---|---|
| Reasoning | External coding agent (Claude Code / Codex) | Inspect papers, repos, h5ad files; reconstruct data/metric/method assumptions; write `driver.py`, `env.yml`, `data_adapter.py`; diagnose stderr; repair failures | Yes — the agent is the LLM |
| Reproducibility | sobench Python | Contract validation/freezing, scaffolding, env records, smoke validation, metric computation, benchmark execution, aggregation, experience writing | **No** — zero LLM calls in M1 |

Everything that must be reproducible and auditable lives in deterministic sobench Python. Everything that requires open-ended reasoning over papers, repos, and code is delegated to the external agent.

**M1 goal:** The external coding agent, guided by sobench skills, constructs the full spatial-domain-identification benchmark — all 3 methods × 5 MERFISH cases — producing real ARI/NMI values in a fixed result schema plus structured experience records.

**Capability growth:** sobench's fixed tools/skills stay minimal; practical capability grows through append-only, auditable experience records. M1 writes them. M2 adds retrieval and reuse.

**Two uses of ModernTSF (reference, not a feature checklist to copy):**
1. *sobench's own operating surface* — `tool/sobench.py` + agent-facing skills mirrors `tool/tsf.py` + `.claude/skills/` organization.
2. *Generated benchmark projects* — unified runner, frozen contracts, fixed result schema, smoke validation, aggregation, reproducible execution mirror ModernTSF's benchmark implementation patterns.

Additional references that shaped the design: SkillOpt (skills as external operational artifacts improvable from execution feedback), SkillOps (capability growth governed by contracts, validation, and failure records — not memory debt), Deli_AutoResearch (all construction decisions, smoke results, repairs, failures, and results written to files, not conversation memory).

---

## 2. Repository Structure

Three planes with strict interfaces between them.

```
tool/
  sobench.py                     # unified stdlib entry (pure argparse + subprocess; no LLM imports)

agent-instructions/              # agent-facing skills/instructions, initially under .claude/skills/
  construct/SKILL.md
  validate/SKILL.md
  smoke/SKILL.md
  repair/SKILL.md
  execute/SKILL.md
  experience/SKILL.md

sobench/                         # deterministic Python substrate — zero LLM calls in M1
  contracts/
    task_contract.py
    data_contract.py
    metric_contract.py
    bench_record.py
    freeze.py
  scaffold.py
  env_builder.py
  smoke.py
  checker.py
  runner.py
  metrics.py
  aggregator.py
  experience.py
  llm.py                         # retained from v1; unused in M1; reserved for M2 internalization

benchmark_projects/              # git-ignored generated output
  spatial_domain_identification/
    task_contract_draft.json     # written by agent
    data_contract_draft.json     # written by agent
    metric_contract_draft.json   # written by agent
    task_contract.json           # frozen by sobench validate
    data_contract.json           # frozen by sobench validate
    metric_contract.json         # frozen by sobench validate
    freeze_report.json           # written by sobench validate (preserved always)
    run_benchmark.py             # fixed template written by sobench scaffold
    data_adapter.py              # written by agent (interface-validated by sobench)
    methods/
      STAGATE_pyG/
        driver.py                # written by agent (CLI contract validated by sobench)
        env.yml                  # written by agent
        method_card.md           # written by agent — optional in M1
        env_record.json          # written by sobench env
        driver_record.json       # written by sobench smoke (append-only per attempt)
      MENDER/  ...
      SpaGCN/  ...
    results/
      STAGATE_pyG_MERFISH_0.04.json   # BenchRecord per method×case
      ...
      results.csv                     # written by sobench aggregate

experience_store/                # git-tracked, append-only
  methods/STAGATE_pyG.json
  methods/MENDER.json
  methods/SpaGCN.json
  datasets/MERFISH.json
  metrics/ARI.json
  metrics/NMI.json

data/                            # unchanged real task inputs
  spatial_domain_identification_task/
    codes/{STAGATE_pyG,MENDER,SpaGCN}/
    dataset/{MERFISH_0.04..0.24}.h5ad
    papers/{STAGATE,MENDER,SpaGCN}.pdf

tests/
  test_contracts.py
  test_checker.py
  test_metrics.py
  test_aggregator.py
  test_experience.py
  test_integration.py            # requires conda + method repos; skips if absent
```

`benchmark_projects/` is git-ignored generated output. `experience_store/` is git-tracked. The distinction: projects are produced artifacts; the experience store is accumulated operational knowledge.

`sobench/metrics.py` stays inside the sobench package. `run_benchmark.py` imports it directly, so generated projects are executable within the repo. Standalone packaging is post-M1.

---

## 3. CLI Surface

`tool/sobench.py` is the single agent entry point — pure stdlib, wraps every command as a subprocess call. Agents invoke only `tool/sobench.py`; they never call internal modules directly.

```bash
python tool/sobench.py scaffold    --project-dir <path> [--task <name>]
python tool/sobench.py validate    --project-dir <path>
python tool/sobench.py env         --project-dir <path> --method <M>
python tool/sobench.py smoke       --project-dir <path> --method <M> --case <C>
python tool/sobench.py run         --project-dir <path>
python tool/sobench.py aggregate   --project-dir <path>
python tool/sobench.py experience  --project-dir <path>
```

| Command | Delegates to | What it does |
|---|---|---|
| `scaffold` | `sobench/scaffold.py` | Write project tree skeleton + fixed `run_benchmark.py` template from frozen contracts |
| `validate` | `sobench/contracts/freeze.py` | Validate agent-written draft contracts against real h5ad files; freeze on pass; write `freeze_report.json` always |
| `env` | `sobench/env_builder.py` | Create/cache conda env from `methods/<M>/env.yml`; write `env_record.json` |
| `smoke` | `sobench/smoke.py` | Create deterministic 100-spot smoke h5ad; run driver with method interpreter; append attempt to `driver_record.json`; 7-check validate output |
| `run` | `sobench/runner.py` | Full benchmark run per method×case using method interpreter; write `BenchRecord` JSONs |
| `aggregate` | `sobench/aggregator.py` | Read all `BenchRecord` JSONs → write `results.csv` with fixed column order |
| `experience` | `sobench/experience.py` | Append structured entries to `experience_store/` from completed run artifacts |

---

## 4. Contracts

### 4.1 TaskContract

Describes the benchmark matrix. The `methods` field carries per-method metadata so the runner can resolve repo path, driver path, env file, and env record without a separate MethodContract in M1.

```json
{
  "project_id": "spatial_domain_identification_20260620",
  "task": "spatial_domain_identification",
  "dataset": "MERFISH",
  "cases": ["MERFISH_0.04", "MERFISH_0.09", "MERFISH_0.14", "MERFISH_0.19", "MERFISH_0.24"],
  "methods": [
    {
      "name": "STAGATE_pyG",
      "repo_path": "data/spatial_domain_identification_task/codes/STAGATE_pyG",
      "driver_path": "methods/STAGATE_pyG/driver.py",
      "env_file": "methods/STAGATE_pyG/env.yml",
      "env_record": "methods/STAGATE_pyG/env_record.json"
    }
  ]
}
```

### 4.2 DataContract

Per-case entries. Different cases may have different files, columns, or keys.

```json
{
  "cases": {
    "MERFISH_0.04": {
      "h5ad_path": "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad",
      "obs_columns": ["Cell_class", "batch"],
      "spatial_key": "spatial",
      "ground_truth_column": "Cell_class"
    },
    "MERFISH_0.09": { "..." }
  }
}
```

### 4.3 MetricContract

Deterministic in M1.

```json
{
  "metrics": ["ARI", "NMI"],
  "implementation": "sobench.metrics",
  "label_type": "integer_cluster_labels"
}
```

### 4.4 BenchRecord (Pydantic, `extra="forbid"`)

The fixed result schema. Written by `sobench/runner.py`. Never written by the agent or `run_benchmark.py` directly.

```python
class SpatialMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ARI: float | None = None
    NMI: float | None = None

class BenchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str           # "<method>__<dataset>__<case>"
    project_id: str
    task: str
    method: str
    dataset: str
    case: str
    metrics: SpatialMetrics
    status: str              # success | failed | skipped | timeout | invalid_output
    skip_reason: str | None = None
    failure_detail: str | None = None
    duration_seconds: float | None = None
    driver_repair_count: int
    env_name: str
    created_at: str          # ISO-8601
```

`results.csv` is derived by flattening all `BenchRecord` objects. Column order is fixed. Missing metric = null in that cell, not a shifted column.

---

## 5. The Freeze Flow

```
Agent writes:
  task_contract_draft.json
  data_contract_draft.json
  metric_contract_draft.json

sobench validate:
  → opens each h5ad listed in data_contract_draft
  → checks ground_truth_column and spatial_key against actual obs.columns and obsm.keys()
  → checks all required fields are present
  → checks every case key in data_contract matches a case in task_contract
  → checks metrics list is a subset of ["ARI", "NMI"]
  → PASS:
      writes task_contract.json, data_contract.json, metric_contract.json (frozen)
      writes freeze_report.json: {passed: true, timestamp, contract_hashes}
      drafts preserved as-is — never erased
  → FAIL:
      writes freeze_report.json: {passed: false, errors: [...]}
      no frozen files written; agent reads errors and revises drafts
```

The runner reads only frozen `*_contract.json`. If frozen files are absent, it exits with a clear error before touching any data.

---

## 6. Driver CLI Contract

Fixed. Injected into every agent context via the `construct` skill. `sobench smoke` and `sobench run` both use the method's `env_record.json.interpreter_path` to invoke the driver — never system Python.

```bash
<interpreter_path> driver.py \
  --data       <path/to/case.h5ad> \
  --output     <path/to/result.json> \
  --method-dir <path/to/method/repo> \
  --work-dir   <path/to/scratch/> \
  [--smoke]    # fast mode: reduced epochs — must still produce real cluster labels
```

Output schema (written to `--output`, always):
```json
{"cell_ids": ["spot1", ...], "labels": [0, 1, ...], "status": "success", "metadata": {}}
```

`--smoke` is not a dry run. It produces real cluster labels. The subsampling is controlled by sobench, not the driver.

---

## 7. Smoke Validation

`sobench smoke` creates the deterministic smoke h5ad (100 spots, fixed random seed, written to a temp path derived from project dir + method + case) before invoking the driver. The driver receives this file as `--data`. Check 7 of the smoke validator then compares output `cell_ids` against this file's `obs_names` exactly.

**Smoke output 7-check validator** (`sobench/checker.py` — new M1 substrate logic):

1. Output file exists and JSON parses
2. `cell_ids` and `labels` keys present
3. `len(cell_ids) == len(labels)`
4. `len(labels) > 0`
5. No null values in either list
6. All labels are uniformly `str` or uniformly `int`
7. `cell_ids` exactly match the deterministic smoke h5ad's `obs_names`

`sobench smoke` appends one attempt record to `driver_record.json` per invocation (atomic write: read → prepend → temp-replace):

```json
{
  "method": "STAGATE_pyG",
  "case": "MERFISH_0.04",
  "attempts": [
    {
      "attempt": 1,
      "timestamp": "2026-06-20T14:00:00Z",
      "command": "<interpreter> driver.py --data ... --smoke",
      "stdout": "...",
      "stderr": "...",
      "validation_failures": ["check 7 failed: cell_ids mismatch"],
      "status": "invalid_output"
    }
  ],
  "final_status": "invalid_output",
  "repair_count": 1
}
```

`final_status` reflects the most recent attempt. `repair_count` = number of attempts after the first. The agent skill enforces the 3-attempt limit; the tool always records.

---

## 8. data_adapter.py Interface

Agent writes `data_adapter.py`. `sobench validate` checks it is importable and exposes the three required signatures before any driver runs.

```python
def load_case(case_id: str) -> anndata.AnnData: ...
def get_ground_truth(adata: anndata.AnnData) -> list: ...   # ground-truth labels aligned to obs_names order
def get_spatial(adata: anndata.AnnData) -> numpy.ndarray: ...  # spatial coordinates
```

`run_benchmark.py` calls these. Drivers may also import `data_adapter` internally.

---

## 9. run_benchmark.py — Fixed Thin Entrypoint

Written by `sobench scaffold` from a fixed template. Never modified by the agent. Contains no method-specific logic. All orchestration logic lives in `sobench.runner`.

Responsibility: load frozen contracts; call `sobench.runner.run(project_dir)`. That is all.

`sobench.runner` owns: contract loading, interpreter selection from `env_record.json`, driver subprocess execution, output validation via `checker.py`, metric computation via `metrics.py` (alignment by `cell_ids` join, not list order — mismatch → `BenchRecord` with `status: "invalid_output"` and `failure_detail`), and `BenchRecord` writing.

---

## 10. Metric Computation

`sobench/metrics.py` exposes:

```python
def compute(
    pred: dict[str, int | str],   # {cell_id: label}
    true: dict[str, int | str],   # {cell_id: label}
    metrics: list[str],           # from MetricContract
) -> dict[str, float | None]:
    ...
```

The runner aligns driver output `cell_ids`/`labels` with ground truth by constructing these dicts from obs names. Any missing, duplicate, or extra `cell_ids` in the driver output → `BenchRecord` with `status: "invalid_output"`, `failure_detail` describing the mismatch, `metrics.ARI = None`, `metrics.NMI = None`.

---

## 11. Experience Store

Git-tracked, append-only, human-readable. Three indexes.

```
experience_store/
  methods/<method_name>.json
  datasets/<dataset_stem>.json
  metrics/<metric_name>.json
```

Each file is a JSON array, newest-first. All writes are atomic: read existing array → prepend new entry → write to temp file → replace original. Every entry carries `"schema_version": "1"`.

### Method entry

```json
{
  "schema_version": "1",
  "entry_id": "method-STAGATE_pyG-20260620-001",
  "created_at": "2026-06-20T14:30:00Z",
  "task": "spatial_domain_identification",
  "method": "STAGATE_pyG",
  "dataset": "MERFISH",
  "case": "MERFISH_0.04",
  "source_project": "benchmark_projects/spatial_domain_identification",
  "env_status": "env_created",
  "driver_status": "smoke_valid",
  "benchmark_status": "benchmark_executed",
  "driver_repair_count": 1,
  "env_yml_ref": "benchmark_projects/.../methods/STAGATE_pyG/env.yml",
  "env_yml_hash": "sha256:abc123",
  "driver_snapshot_ref": "benchmark_projects/.../methods/STAGATE_pyG/driver.py",
  "driver_snapshot_hash": "sha256:def456",
  "repair_patterns": [
    {
      "stderr_fragment": "Cal_Spatial_Net not called",
      "fix_description": "call Cal_Spatial_Net(adata, rad_cutoff=150) before train_STAGATE"
    }
  ],
  "env_record_ref": "benchmark_projects/.../methods/STAGATE_pyG/env_record.json",
  "driver_record_ref": "benchmark_projects/.../methods/STAGATE_pyG/driver_record.json",
  "bench_record_ref": "benchmark_projects/.../results/STAGATE_pyG_MERFISH_0.04.json",
  "partial": false,
  "missing_artifacts": [],
  "reason": null
}
```

`env_status`, `driver_status`, `benchmark_status` are independent. A method can be `env_created` + `smoke_valid` + `execution_failed` simultaneously. `partial: true` is set when any expected artifact is absent; `missing_artifacts` lists them; `reason` explains.

### Dataset entry

```json
{
  "schema_version": "1",
  "entry_id": "dataset-MERFISH-20260620-001",
  "created_at": "2026-06-20T14:30:00Z",
  "task": "spatial_domain_identification",
  "dataset_stem": "MERFISH",
  "case": "MERFISH_0.04",
  "source_project": "benchmark_projects/spatial_domain_identification",
  "h5ad_path": "data/spatial_domain_identification_task/dataset/MERFISH_0.04.h5ad",
  "h5ad_size_bytes": 12345678,
  "h5ad_mtime": "2026-06-17T04:18:00Z",
  "h5ad_shape": [5765, 254],
  "h5ad_fingerprint": {
    "obs_columns": ["Cell_class", "batch"],
    "obsm_keys": ["spatial"],
    "has_raw": false
  },
  "ground_truth_column": "Cell_class",
  "spatial_key": "spatial",
  "data_adapter_ref": "benchmark_projects/.../data_adapter.py",
  "data_adapter_hash": "sha256:ghi789",
  "contract_ref": "benchmark_projects/.../data_contract.json",
  "freeze_report_ref": "benchmark_projects/.../freeze_report.json",
  "partial": false,
  "missing_artifacts": [],
  "reason": null
}
```

`h5ad_fingerprint` is written by `sobench experience` by opening the actual h5ad — not copied from draft contract.

### Metric entry

Written only for successfully computed metrics. If a run failed or was skipped, metric entry is either absent or written with `status: "not_computed"` and a `bench_record_ref`.

```json
{
  "schema_version": "1",
  "entry_id": "metric-ARI-20260620-001",
  "created_at": "2026-06-20T14:30:00Z",
  "task": "spatial_domain_identification",
  "metric": "ARI",
  "method": "STAGATE_pyG",
  "case": "MERFISH_0.04",
  "implementation": "sobench.metrics.compute_ari",
  "ground_truth_column": "Cell_class",
  "label_type": "integer_cluster_labels",
  "alignment": "by_cell_ids",
  "status": "benchmark_executed",
  "value": 0.712,
  "bench_record_ref": "benchmark_projects/.../results/STAGATE_pyG_MERFISH_0.04.json",
  "partial": false,
  "missing_artifacts": [],
  "reason": null
}
```

---

## 12. Skills

Six SKILL.md files in `agent-instructions/` (initially `.claude/skills/`). Each describes when to invoke which command, what to check, and how to interpret outputs. No logic, no hardcoded benchmark decisions. Start minimal; improved from execution feedback (SkillOpt principle).

**`construct/SKILL.md`** — inspect papers/repos/h5ad; draft contracts; write `driver.py`, `env.yml`, `data_adapter.py`:
- Open each paper PDF; read key source files in each method repo; open each h5ad with `anndata.read_h5ad` and inspect actual `obs.columns`, `obsm.keys()`, `X.shape`
- Draft `task_contract_draft.json` (benchmark matrix; per-method repo/driver/env metadata)
- Draft `data_contract_draft.json` (per-case h5ad paths; ground truth column and spatial key verified against actual h5ad)
- Draft `metric_contract_draft.json` (ARI and NMI; `implementation: sobench.metrics`)
- Write `data_adapter.py` satisfying the fixed interface
- Write `methods/<M>/driver.py` per method satisfying the fixed CLI contract (contract text embedded in skill)
- Write `methods/<M>/env.yml` derived from repo requirements/setup files
- Call `sobench validate` when all drafts and adapters are written

**`validate/SKILL.md`** — contract validation loop:
- Call `python tool/sobench.py validate --project-dir benchmark_projects/<task>`
- Read `freeze_report.json`: if `passed: true`, frozen contracts written — proceed to smoke
- If `passed: false`: read `errors` list; fix the specific draft fields; re-call validate
- Do not proceed to smoke until `freeze_report.json` shows `passed: true`

**`smoke/SKILL.md`** — per-method smoke check:
- Prerequisite: `env_record.json` must exist; if absent, run `sobench env` first
- Call `python tool/sobench.py smoke --project-dir ... --method <M> --case <smallest_case>` (smallest case by file size)
- Read `driver_record.json`: check `final_status`
- If `smoke_valid`: proceed to next method
- If any failure status: invoke repair skill

**`repair/SKILL.md`** — driver repair:
- Read `driver_record.json`: `attempts[-1].stderr` and `attempts[-1].validation_failures`
- Read relevant method repo source files; understand the specific API failure
- Make a targeted edit to `driver.py` to fix the identified failure — not a full rewrite
- Re-call `sobench smoke`; read updated `driver_record.json`
- If `repair_count >= 3` and still failing: write `methods/<M>/blocked.md` explaining the failure; move to next method
- Never relax the output contract; fix the driver to meet it

**`execute/SKILL.md`** — full benchmark run:
- Prerequisite: all methods that reached `smoke_valid` have `env_record.json`
- Call `python tool/sobench.py run --project-dir ...`
- Call `python tool/sobench.py aggregate --project-dir ...`
- Read `results.csv`: note real ARI/NMI per method×case; every non-success row must have `status` and `skip_reason`

**`experience/SKILL.md`** — experience writing:
- Call `python tool/sobench.py experience --project-dir ...`
- Review the printed summary: entries written, statuses, partial records flagged
- Commit `experience_store/` to git with message describing task and methods executed

---

## 13. Verification Model

All tests operate against `data/spatial_domain_identification_task/` only. No mocks, per `docs/TESTING_POLICY.md`.

### Deterministic substrate tests (no LLM, no conda required)

| File | What it exercises | Real inputs used |
|---|---|---|
| `test_contracts.py` | `freeze.py` validates and rejects drafts; opens real h5ad; checks `ground_truth_column` and `spatial_key` exist in actual `obs`/`obsm` | All 5 MERFISH h5ad files |
| `test_checker.py` | 7-check validator accepts valid output; rejects each failure mode; check 7 uses real `obs_names` from deterministic smoke h5ad | `obs_names` from `MERFISH_0.04.h5ad` |
| `test_metrics.py` | ARI/NMI computed correctly by `cell_ids` join; mismatched/duplicate/missing ids → explicit `ValidationError`, not silent `None` | `obs` from `MERFISH_0.04.h5ad` |
| `test_aggregator.py` | `BenchRecord` list → `results.csv`; fixed column order; null metrics appear as null cells | Minimal `BenchRecord` fixtures with real task/method/case identifiers |
| `test_experience.py` | Atomic write (temp-replace); `schema_version` present; separate `env_status`/`driver_status`/`benchmark_status`; `partial: true` with `missing_artifacts` when artifact absent | Artifacts derived from real task identifiers |

### Integration test (requires conda + method repos)

`tests/test_integration.py`: full loop from agent-written artifacts to `results.csv`.

**Skip condition:** conda unavailable OR method repos absent from `data/` — must skip with explicit reason. When both are present, the test must run (not skip).

**Assertions:**
- `results.csv` exists and has exactly 3 × 5 = 15 rows (3 methods × 5 MERFISH cases)
- Every row has a concrete `status` field; every non-success row has a non-empty `skip_reason` or `failure_detail`
- At least one `status == "success"` row per method with real (non-null) ARI and NMI floats
- All `BenchRecord` JSONs present for every row in `results.csv`
- `experience_store/methods/`, `experience_store/datasets/`, `experience_store/metrics/` each have at least one entry
- `freeze_report.json` shows `passed: true`
- `driver_record.json` present for every smoke_valid method

---

## 14. Definition of Done

M1 is complete only when **all** of the following hold:

1. The deterministic Python substrate (contracts, scaffold, env_builder, smoke, checker, runner, metrics, aggregator, experience) passes all tests in Section 13 against the real `data/spatial_domain_identification_task/` task.
2. The external coding agent, guided by sobench skills, can construct the full benchmark: inspect real papers/repos/h5ad files, draft and freeze contracts, write working drivers and env files, smoke-validate all runnable drivers, run the full 3 × 5 method×case matrix as far as possible, write `BenchRecord` JSONs and `results.csv`, and append structured experience entries.
3. `results.csv` contains 15 rows; at least one successful ARI/NMI result per method; every failed/skipped row has a concrete status and reason.
4. `experience_store/` has valid, schema_version-tagged entries for methods, datasets, and metrics.
5. `freeze_report.json` shows `passed: true` with contract hashes.
6. Repository is restartable from `./init.sh`.

---

## 15. v1 Salvage Notes

The v1 fixed-step pipeline (`steps/`, `cli.py`, `workspace.py`, `runner.py`, `models.py`) is **not** the identity of sobench v3. It is removed from the external architecture.

Useful pieces to port, not copy verbatim:
- `llm.py` — retained as-is for M2 internalization; unused in M1
- Dataclass/JSON-artifact patterns from `models.py` — inform the new contract dataclasses
- Feasibility/blocker reasoning from `s09_execute_or_block.py` — informs `BenchRecord.status` vocabulary
- Experience record schema from `s13_write_experience_record.py` — informs experience store entry design

Everything else is superseded.
