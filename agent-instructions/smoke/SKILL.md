---
name: sobench-smoke
description: Smoke-validate a method's driver on a deterministic 100-spot subset. Use after env, before run.
---

# smoke

Confirm each driver produces contract-valid cluster labels on a fast 100-spot
subset before committing to the full run.

## Steps

1. Prerequisite: `methods/<M>/env_record.json` must exist. If absent, invoke the
   **env** skill first.
2. Run on the smallest case (smallest h5ad by file size — for MERFISH that is
   `MERFISH_0.04`):
   ```bash
   python tool/sobench.py smoke --project-dir benchmark_projects/<task> --method <M> --case MERFISH_0.04
   ```
3. Read `methods/<M>/driver_record.json` → `final_status`:
   - `smoke_valid` → proceed to the next method (or to **run** once all are valid).
   - any failure status (`invalid_output`, `driver_error`) → invoke the **repair** skill.

sobench builds the deterministic smoke h5ad (fixed seed) and runs the driver with
`--smoke` via the method interpreter. Each invocation appends one attempt to
`driver_record.json`; `repair_count` counts attempts after the first.
