# AgentEmergenceLoop

**sobench v3** — a deterministic, hybrid benchmark-construction substrate for spatial omics.

sobench provides reproducible, auditable machinery operated by an external coding
agent. The agent does the open-ended reasoning (read papers/repos/h5ad, write
`driver.py` / `env.yml` / `data_adapter.py`, diagnose failures); sobench Python does
everything that must be reproducible (contract validation/freeze, scaffolding, env
records, smoke validation, metric computation, benchmark execution, aggregation,
experience writing). **sobench makes no LLM calls in M1.**

Binding design spec: `docs/superpowers/specs/2026-06-20-sobench-v3-design.md`.

## The hybrid boundary

| Plane | Owner | LLM calls? |
|---|---|---|
| Reasoning | External coding agent (Claude Code / Codex) | Yes — the agent is the LLM |
| Reproducibility | sobench Python | No — zero LLM calls in M1 |

## CLI — the single agent entry point

Agents invoke only `tool/sobench.py` (pure stdlib; each subcommand forwards to an
internal module):

```bash
python tool/sobench.py scaffold    --project-dir <p> [--task <name>]
python tool/sobench.py validate    --project-dir <p>
python tool/sobench.py env         --project-dir <p> --method <M>
python tool/sobench.py smoke       --project-dir <p> --method <M> --case <C>
python tool/sobench.py run         --project-dir <p>
python tool/sobench.py aggregate   --project-dir <p>
python tool/sobench.py experience  --project-dir <p>
```

Agent-facing instructions for each stage live in `agent-instructions/*/SKILL.md`.

## Three environments (kept strictly separate)

1. **Development** — runs sobench's own Python, substrate tests, and `./init.sh`.
   Has `anndata` / `pydantic` / `numpy` / `scikit-learn` — NOT the heavy method deps.
2. **Agent/runtime** — operates the harness (inspects files, edits code, invokes
   `tool/sobench.py`).
3. **Per-method conda envs** — one isolated env per benchmark method, built from
   that method's `env.yml`. Drivers run through `env_record.json.interpreter_path`,
   never through the development or agent environment.

## Verification

```bash
./init.sh      # python -m pytest (sobench substrate) + compileall sobench tool tests
```

The deterministic substrate tests run with no LLM and no conda (fast, restartable).
The full method×case integration test (`tests/test_integration.py`) builds real
conda envs and runs real drivers — it skips unless conda + method repos are present
and `SOBENCH_RUN_INTEGRATION=1` is set. All tests use the real task under `data/`;
no mocks (see `docs/TESTING_POLICY.md`).

## Repository layout

```
tool/sobench.py            # single agent CLI entry point (stdlib)
agent-instructions/        # agent-facing SKILL.md instructions (construct/validate/...)
sobench/                   # deterministic substrate (contracts, scaffold, env_builder,
                           #   smoke, checker, runner, metrics, aggregator, experience)
sobench/llm.py             # retained from v1; unused in M1; reserved for M2
benchmark_projects/        # git-ignored generated output
experience_store/          # git-tracked, append-only operational knowledge
data/spatial_domain_identification_task/   # real task: MERFISH h5ad + method repos + papers
tests/                     # real-task substrate tests + opt-in integration test
docs/                      # spec + testing policy
feature_list.json          # feature state tracker (source of truth)
progress.md                # session continuity log
```

## Current target

M1: the agent, guided by the sobench skills, constructs the full spatial-domain
benchmark — 3 methods (STAGATE_pyG, MENDER, SpaGCN) × 5 MERFISH cases — producing
real ARI/NMI in a fixed result schema plus structured experience records.
Capability grows through the append-only experience store; retrieval/reuse is M2.
