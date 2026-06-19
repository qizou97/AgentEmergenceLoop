# Session Progress Log

## Current State

**Last Updated:** 2026-06-19 (implementation session — subagent-driven, real-LLM)
**Active Feature:** feat-sobench-001 (package skeleton: models + workspace)

## Project

**sobench** — evidence-guided, reproducible spatial-omics benchmark construction agent.

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

- [ ] feat-sobench-001 (package skeleton: models + workspace) — implementation starting.
  - Executing the full 10-task plan via subagent-driven development.

### What's Next

1. feat-sobench-001 → 010 in order, one implementer subagent + task review per feature.
2. Each feature: write real-task tests first, then implement, then verify with `./init.sh`.
3. Final whole-branch review, then finish.

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
