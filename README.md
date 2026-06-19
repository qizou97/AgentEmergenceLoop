# AgentEmergenceLoop

An agent that reconstructs one spatial-omics benchmark task from paper/code/data context, preserves auditable evidence, either attempts execution or records a blocker, and writes a scoped experience note.

## Current Target

Build `sobench`: a 14-step pipeline that takes a `benchmark_intent.md` file plus local paper PDFs and method code, and produces a fully auditable workspace with task spec, data manifest, evaluation contract, execution result (or named blocker), and an experience record.

## In Scope Now

- `sobench` package: 15 artifact dataclasses, `Workspace` class, LLM wrapper, CLI (`scaffold / run / check / report`)
- 14 pipeline steps: evidence extraction → task spec → execution → observation → experience record
- Test suite covering every step against a mocked LLM
- One end-to-end smoke test over the `data/spatial_domain_identification_task` workspace

## Out of Scope Now

- Automatic paper/code crawling or downloading
- Multi-agent orchestration or parallelism
- Vector databases, embedding search, or RAG
- Dashboard, visualization, or result comparison across methods
- Generic benchmark runner for arbitrary domains

## Next Concrete Task

Implement `feat-sobench-001`: the 15 artifact dataclasses (`from_dict` / `to_dict` / `validate`) and the `Workspace` class (path resolution, artifact I/O, `blocked` property).

Steps:
1. Run `./init.sh` to confirm baseline is clean.
2. Write `tests/test_models.py` and `tests/test_workspace.py` first.
3. Implement `sobench/models.py` and `sobench/workspace.py`.
4. Verify with `python -m pytest tests/test_models.py tests/test_workspace.py`.

## Repository Layout

```
data/                   # local paper PDFs and method code (input context)
docs/superpowers/       # design spec and implementation plan
feature_list.json       # feature state tracker (source of truth)
progress.md             # session continuity log
init.sh                 # startup and verification path
tests/                  # test suite
```

See `feature_list.json` for the full feature list and completion status.
