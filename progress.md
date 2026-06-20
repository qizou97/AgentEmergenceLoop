# Session Progress Log

## Current State

**Last Updated:** 2026-06-20 (v3 deterministic substrate session COMPLETE)
**Active Feature:** none — sobench v3 M1 deterministic substrate (F0–F11) done.
Next: `feat-v3-M1-operate` (the agent operates the substrate to build the full
MERFISH benchmark; integration test exists, gated on conda env builds).

## Project

**sobench v3** — a deterministic, hybrid benchmark-construction substrate for
spatial omics. Spec: `docs/superpowers/specs/2026-06-20-sobench-v3-design.md`
(the binding contract). The v1 14-step LLM pipeline (spec 2026-06-19) and the v2
synthesis layer are **superseded** (spec §15).

**The hybrid boundary** is the core rule:
- Reasoning plane = the external coding agent (reads papers/repos/h5ad, writes
  driver.py/env.yml/data_adapter.py, diagnoses failures). This is where the LLM lives.
- Reproducibility plane = deterministic sobench Python (contracts/freeze,
  scaffold, env records, smoke, metrics, runner, aggregator, experience).
  **Zero LLM calls in M1.**

## v3 Session (2026-06-20)

Built the full M1 deterministic substrate, TDD, one feature at a time, each
leaving `./init.sh` green. Real-task tests only (no mocks) against
`data/spatial_domain_identification_task/` (5 MERFISH h5ad, 3 method repos).

- **F0** (50409d0): removed v1 source + ~220 real-LLM tests (kept llm.py for M2);
  re-scoped the gate to `sobench tool tests`. ./init.sh: 13 min → ~4s, no LLM,
  0 `references/` items collected (was 135).
- **F1–F2** (803ddc3): BenchRecord schema + 3 contracts + freeze flow. freeze opens
  the real h5ad and validates the agent's drafts — column names are checked, never
  hardcoded (real gt col is `ground_truth`; spec's `Cell_class` example is stale).
- **F3** (9084c5a): metrics — ARI/NMI by cell_id join, AlignmentError on mismatch.
- **F4** (1783148): checker — 7-check smoke validator (check 7 = order-free multiset).
- **F5** (b889a31): aggregator — BenchRecords → fixed-column results.csv.
- **F6** (b4433a1): experience — append-only 3-index store, atomic, real fingerprint.
- **F7** (be5ada1): scaffold — tree + fixed method-agnostic run_benchmark.py.
- **F8** (e37f5c7): runner — frozen-contract load, driver subprocess, build_record core.
- **F9** (6fb952c): env_builder — conda env from env.yml, idempotent, interpreter_path.
- **F10** (cb8efb1): smoke — deterministic 100-spot h5ad + driver_record append.
- **F11** (0519187): tool/sobench.py CLI (7 subcommands) + 6 agent SKILL.md + integration test.

**Verification:** `./init.sh` → **70 passed, 1 skipped** (integration, opt-in) in ~4s.
Deterministic, LLM-free, conda-free. The integration test (`tests/test_integration.py`)
runs the full §13 matrix when `SOBENCH_RUN_INTEGRATION=1` and the agent has produced
the construction artifacts.

**Environment separation (held throughout):** the dev/agent environment runs
sobench's own code + tests (anndata/pydantic/sklearn — NOT heavy method deps).
Method deps (scanpy/torch/squidpy/tensorflow) live ONLY in per-method conda envs,
invoked via `env_record.json.interpreter_path`.

---

## (Superseded) v1 evidence-loop history

The notes below describe the v1 14-step LLM pipeline, removed in F0 (recoverable in
git history). Retained for continuity only.

### v1 Project

**sobench (v1)** — evidence-guided, reproducible spatial-omics benchmark construction agent.

Design spec committed at `docs/superpowers/specs/2026-06-19-sobench-design.md` (commit `486cc62`).
Implementation plan at `docs/superpowers/plans/2026-06-19-sobench.md`.

The 14-step loop reconstructs what benchmark a method paper intended, audits validity, attempts execution, diagnoses blockers, and records scoped experience.

## Status

### What's Done

- [x] Harness bootstrap: smoke test, .gitignore, `./init.sh` passing (feat-001).
- [x] Design spec for sobench: 14-step loop, 15 artifacts, 4 CLI subcommands, workspace layout, runner control flow, staged experience loop.
- [x] Implementation plan decomposed into 10 one-feature-at-a-time steps with TDD steps, file lists, verification commands.
- [x] `feature_list.json` reset with sobench feature set.
- [x] `progress.md` reset for sobench project.

### What's In Progress

- [ ] None. All 10 features complete; the full 14-step loop is implemented, wired into the
  CLI (scaffold/run/check/report), and verified end-to-end against the real task.

### What's Next (future phases, out of P0 scope)

1. P1: `sobench` searches prior experience records on demand at ambiguities.
2. P2: relevant scoped experience selectively injected into future runs.
3. Enable the s09 feasible execution path in an environment with the method deps
   (torch/scanpy/tensorflow) and real benchmark data present.

## Blockers / Risks

- None currently.
- LLM API key IS present in `.env` and the endpoint (`deepseek-v4-pro` @ api.deepseek.com)
  is verified live. Per `docs/TESTING_POLICY.md` step tests drive the REAL `llm.complete`
  over real `data/` inputs — no mocks. Tests skip with an explicit reason only if the key
  or required real data goes absent.
- LLM is a reasoning model: it returns `reasoning_content` separately and spends token
  budget on reasoning first, so the wrapper must request a generous `max_tokens` or
  `content` can come back empty.

## Decisions Made

- **Design first, implement one feature at a time**: Full design reviewed and approved before any code. Each feature has TDD steps; tests written before implementation.
- **blocker.json always written**: `blocked: false` when clear. Absence would require structural_check to infer state indirectly — always-written is simpler and auditable.
- **Missing repo/data never a blocker at discovery steps**: s04 records missing repo in `missing` field; s05 records unavailable data with `available: false`. Only s09 decides whether to block.
- **s12 skip condition**: skipped only when `workspace.blocked AND execution_log.status == "not_attempted"`. Writes minimal interpretation when execution ran but validity failed.
- **coordinate fields are free-form strings**: no fixed taxonomy at P0. Schema will evolve from repeated task evidence.

## Files Modified in Design Session (2026-06-19)

- `docs/superpowers/specs/2026-06-19-sobench-design.md` — approved design spec (committed `486cc62`)
- `docs/superpowers/plans/2026-06-19-sobench.md` — implementation plan
- `feature_list.json` — reset for sobench project
- `progress.md` — this file

---

## Previous Bootstrap Session (2026-06-16)

- Added smoke test, .gitignore, published repository to origin/main.
- Feat-001 (Project Setup): done.

## Documentation Update (2026-06-18)

- Added Implementation Reuse Rule and Behavioral Coding Guidelines to `AGENTS.md`.

## Direction Update (2026-06-19)

Scope narrowed to one minimal vertical slice. The project is not a generic scientific agent and not an automatic benchmark runner. The single current target is: reconstruct one spatial-omics benchmark task from local paper/code/data context, produce auditable evidence, attempt execution or record a blocker, write a scoped experience note.

Changes made:
- Created `README.md` with project identity, in-scope / out-of-scope, and next concrete task.
- Collapsed `feature_list.json` from 10 placeholder items to 3 concrete work items (feat-sobench-001/002/003) plus the completed feat-001.
- `./init.sh` passed (1 test, 0 compile errors).

**Next action:** implement feat-sobench-001 (models + workspace): write tests first, then `sobench/models.py` and `sobench/workspace.py`, verify with `python -m pytest tests/test_models.py tests/test_workspace.py`.

## feat-sobench-001 DONE (2026-06-19)

- Implemented `sobench/__init__.py`, `sobench/models.py`, `sobench/workspace.py`.
- 14 artifact dataclasses (ParsedIntent, PaperEvidence, RepoEvidence, DataManifest,
  TaskSpec, EvaluationContract, RiskAudit, Blocker, ExecutionLog, RawObservations,
  ResultValidityAudit, Interpretation, ExperienceRecord, StructuralCheck).
- Each dataclass: from_dict/to_dict/validate; round-trip equality holds.
- Workspace: dir=root/task/case/method/, artifact_path, read/write_artifact,
  read_blocker, blocked property.
- TDD: 43 tests written first (RED: import error); then all 43 + 1 smoke = 44 PASSED.
- `./init.sh` clean.
- Concern: plan says "15 dataclasses" but spec section 7 lists 14 JSON artifacts.
  benchmark_intent.md is human-authored markdown, not a JSON artifact. Implemented 14.

## feat-sobench-009 DONE (2026-06-19)

- Implemented `sobench/runner.py`: STEPS list (s01→s14, 14 entries), SKIP_WHEN_BLOCKED set,
  `run(workspace)` returns ordered list of executed step names.
- `workspace.blocked` is re-evaluated each iteration from disk — once s09 writes blocked:true
  the skip checks see it on the very next step.
- Replaced CLI stubs (run/check/report printed "not yet implemented") with real wired functions:
  `_cmd_run` calls `runner.run()` and prints step summary; `_cmd_check` calls s14 standalone and
  returns 0/non-zero based on `sc.passed`; `_cmd_report` reads structural_check.json +
  experience_record.json and prints human-readable summary, exits non-zero gracefully if absent.
- TDD: runner static tests first (RED: ImportError), then runner.py implemented (GREEN: 3 pass),
  then real pipeline test (real blocked-cycle ran in 2:28, PASSED).
- Updated 3 stale CLI stub tests; added 7 new CLI tests (check/report/run) — all real behavior.
- All 4 runner tests + 15 CLI tests pass. `python -m compileall` clean. 96 tests collected.
- Not-blocked path cannot be produced (real .h5ad absent). Covered structurally by STEPS order
  test + the real blocked run showing s01–s09 + s13 + s14 all execute.

## feat-sobench-010 DONE (2026-06-19)

- Created `tests/fixtures/intent_stagate_dlpfc.md`: provenance-headed fixture derived from
  the real `data/spatial_domain_identification_task/` task. Provenance header in the file
  identifies the source dir, real paper path, real repo path, and DLPFC .h5ad absence.
  Standard sections: Task/Method/Case/Paper/Repository/Data/What to reconstruct/Human observations.
- Created `tests/test_integration.py`: end-to-end test driven from the fixture file.
  Skip gates: OPENAI_API_KEY absent OR real paper/repo absent (both present → test MUST run).
  Assertions: workspace.blocked True; blocker.json exists + blocked:true + non-empty reason;
  execution_log.json status=="not_attempted"; structural_check.json passed==True;
  experience_record.json status=="hypothesis" + evidence non-empty; all 6 auditable-package
  artifacts present; data_manifest.required has at least one available:false (real .h5ad absent);
  s10/s11/s12 artifacts DO NOT exist; executed list == EXPECTED_BLOCKED_EXECUTED.
  RESULT: RAN (not skipped), PASSED in 157s.
- Fixed `sobench/llm.py` max_tokens 4096→8192: pre-existing flaky failure in
  test_runner.py::test_real_blocked_pipeline where s08 prompt (with all prior artifacts) caused
  response truncation and JSON extraction failure. Fix resolves it.
- Full ./init.sh: **96 passed, 1 skipped** in 794s (0:13:14). The 1 skipped is the known s09
  feasible-path skip (always expected). No test failures.
- Commit: 2664b3c "test(sobench): add end-to-end integration smoke test"

## Implementation Session (2026-06-19, subagent-driven, real-LLM)

Re-expanded `feature_list.json` from the 3 narrowed items back to the plan's 10 features
(feat-sobench-001 … 010). Rationale: `docs/TESTING_POLICY.md` (binding/overriding) and the
updated plan require real-task, no-mock testing; the 3-item list still described "LLM mocked /
synthetic workspace" for the integration test, which directly conflicts. The 10-feature plan is
the policy-aligned, TDD-structured source of truth. No design change — same 14-step loop, same
15 artifacts, same spec.

Environment confirmed at session start:
- Deps `openai`, `python-dotenv`, `pypdf` installed (pip needs
  `--trusted-host mirrors.aliyun.com --index-url http://mirrors.aliyun.com/pypi/simple/`).
- `./init.sh` baseline clean (1 test passing).
- Real task: `data/spatial_domain_identification_task/` — papers (STAGATE/SpaGCN/MENDER PDFs)
  + 3 method repos. No `.h5ad` anywhere → execution is a genuine blocked cycle.
