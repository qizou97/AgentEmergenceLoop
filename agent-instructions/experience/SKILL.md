---
name: sobench-experience
description: Append structured experience entries from a completed run, then commit the experience store. Use last.
---

# experience

Persist what the run taught us into the git-tracked, append-only experience store.

## Steps

1. Run:
   ```bash
   python tool/sobench.py experience --project-dir benchmark_projects/<task>
   ```
   This appends entries to `experience_store/methods/`, `datasets/`, and
   `metrics/` (newest-first JSON arrays, `schema_version: "1"`, atomic writes).
2. Review the printed summary: entries written per index, and any record flagged
   `partial: true` (with `missing_artifacts` + `reason`).
3. Commit `experience_store/` to git with a message naming the task and the
   methods executed.

M1 only writes experience. Retrieval and reuse of prior entries is M2 — do not
build it now.
