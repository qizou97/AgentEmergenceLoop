---
name: sobench-validate
description: Validate and freeze the draft contracts against the real h5ad files. Use after construct, before env/smoke.
---

# validate

Freeze the agent-written drafts only after sobench confirms they match the real
data. The runner reads ONLY frozen `*_contract.json`.

## Steps

1. Run:
   ```bash
   python tool/sobench.py validate --project-dir benchmark_projects/<task>
   ```
2. Read `freeze_report.json`:
   - `passed: true` → `task_contract.json`, `data_contract.json`,
     `metric_contract.json` are frozen (with `contract_hashes`). Proceed to **env**.
   - `passed: false` → read the `errors` list. Each error names the offending
     field (e.g. `ground_truth_column 'Cell_class' not in obs.columns [...]`).
     Fix that specific draft field and re-run validate.
3. Do not proceed past validate until `freeze_report.json` shows `passed: true`.
   The exit code mirrors this (0 = passed, 1 = failed).

Common failures: a `ground_truth_column` or `spatial_key` that does not exist in
the real h5ad; a metric outside `{ARI, NMI}`; a data-contract case not declared in
the task contract. The fix is always to the draft, never to the substrate.
