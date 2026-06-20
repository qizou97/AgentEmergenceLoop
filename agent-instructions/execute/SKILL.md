---
name: sobench-execute
description: Run the full method×case benchmark matrix and aggregate results. Use after all runnable drivers are smoke_valid.
---

# execute

Run the frozen benchmark matrix and produce `results.csv`.

## Steps

1. Prerequisite: every method intended to run has reached `smoke_valid` and has an
   `env_record.json`.
2. Run the full matrix:
   ```bash
   python tool/sobench.py run --project-dir benchmark_projects/<task>
   ```
   This writes one `BenchRecord` JSON per method×case under `results/`. A method
   without an env/driver/case yields `status: skipped` with a `skip_reason`; a
   crash yields `failed`; bad output yields `invalid_output`; a hang yields `timeout`.
3. Aggregate:
   ```bash
   python tool/sobench.py aggregate --project-dir benchmark_projects/<task>
   ```
4. Read `results/results.csv`: note the real ARI/NMI per method×case. Every
   non-success row must carry a concrete `status` and a `skip_reason` or
   `failure_detail`. Do not hand-edit BenchRecords or results.csv — they are
   sobench-owned.
