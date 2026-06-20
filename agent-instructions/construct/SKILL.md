---
name: sobench-construct
description: Inspect papers/repos/h5ad and draft the contracts, data_adapter.py, driver.py, and env.yml for a spatial-omics benchmark. Use first, before validate.
---

# construct

You are the **reasoning plane**. sobench Python is deterministic and makes no LLM
calls — everything that requires reading papers, repos, and h5ad files and writing
code is your job. Write artifacts to files, not to conversation memory.

## Steps

1. **Inspect the real inputs.** For each method (under `data/<task>/codes/<M>/`)
   and each case h5ad (under `data/<task>/dataset/`):
   - Read the paper PDF and the key repo source files (entry points, the
     clustering call, any metric code, hardcoded paths, deviations from the paper).
   - Open each h5ad with `anndata.read_h5ad` and record the ACTUAL
     `obs.columns`, `obsm.keys()`, `X.shape`. Never assume column names.

2. **Draft the three contracts** in the project dir:
   - `task_contract_draft.json` — the benchmark matrix + per-method
     `repo_path` / `driver_path` / `env_file` / `env_record` (see spec §4.1).
   - `data_contract_draft.json` — per-case `h5ad_path`, `obs_columns`,
     `spatial_key`, `ground_truth_column`, each **verified against the real
     h5ad** you opened (see spec §4.2).
   - `metric_contract_draft.json` — `{"metrics": ["ARI","NMI"],
     "implementation": "sobench.metrics", "label_type": "integer_cluster_labels"}`.

3. **Write `data_adapter.py`** satisfying the fixed interface (spec §8):
   ```python
   def load_case(case_id: str) -> anndata.AnnData: ...
   def get_ground_truth(adata) -> list: ...   # labels aligned to obs_names order
   def get_spatial(adata) -> numpy.ndarray: ...  # spatial coordinates
   ```

4. **Write `methods/<M>/driver.py`** per method, satisfying the fixed CLI contract
   below. Derive method calls from the repo source you read.

5. **Write `methods/<M>/env.yml`** from the repo's `requirements.txt` / `setup.py`.
   These heavy deps (scanpy, torch, squidpy, tensorflow) belong ONLY in the
   per-method conda env — never in the sobench development environment.

6. When all drafts + adapters + drivers + env files are written, invoke the
   **validate** skill.

## Driver CLI contract (fixed — do not deviate)

```bash
<interpreter_path> driver.py \
  --data       <path/to/case.h5ad> \
  --output     <path/to/result.json> \
  --method-dir <path/to/method/repo> \
  --work-dir   <path/to/scratch/> \
  [--smoke]    # fast mode: reduced epochs — must still produce REAL cluster labels
```

The driver always writes `--output` as:
```json
{"cell_ids": ["spot1", ...], "labels": [0, 1, ...], "status": "success", "metadata": {}}
```
- `cell_ids` must equal the input h5ad's `obs_names` (any order; sobench aligns by join).
- `labels` must be uniformly `int` or uniformly `str`, one per cell, no nulls.
- `--smoke` is NOT a dry run: it produces real labels on the 100-spot file sobench
  hands it. Subsampling is sobench's job, not the driver's.
