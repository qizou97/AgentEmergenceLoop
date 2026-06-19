# CLAUDE.md

Project harness for reliable agent-assisted development in a python codebase.

## Startup Workflow

Before writing code:

1. **Confirm working directory** with `pwd`
2. **Read this file** completely
3. **Read project docs if present** (`docs/ARCHITECTURE.md`, `docs/PRODUCT.md`, README, or equivalent)
4. **Run `./init.sh`** to verify environment is healthy
5. **Read `feature_list.json`** to see current feature state
6. **Review recent commits** with `git log --oneline -5`

If baseline verification is failing, repair that first before adding new scope.

## Working Rules

- **One feature at a time**: Pick exactly one unfinished feature from `feature_list.json`
- **Verification required**: Don't claim done without running verification commands
- **Update artifacts**: Before ending session, update `progress.md` and `feature_list.json`
- **Stay in scope**: Don't modify files unrelated to the current feature
- **Leave clean state**: Next session must be able to run `./init.sh` immediately

## Required Artifacts

- `feature_list.json` — Feature state tracker (source of truth)
- `progress.md` — Session continuity log
- `init.sh` — Standard startup and verification path
- `session-handoff.md` — Optional, for larger sessions

## Definition of Done

A feature is done only when ALL of the following are true:

- [ ] Target behavior is implemented
- [ ] Required verification actually ran (tests / lint / type-check)
- [ ] Evidence recorded in `feature_list.json` or `progress.md`
- [ ] Repository remains restartable from standard startup path

## End of Session

Before ending a session:

1. Update `progress.md` with current state
2. Update `feature_list.json` with new feature status
3. Record any unresolved risks or blockers
4. Commit with descriptive message once work is in safe state
5. Leave repo clean enough for next session to run `./init.sh` immediately

## Verification Commands

```bash
# Full verification (recommended)
./init.sh
```

Required checks:
- `python -m pytest`
- `python -m compileall .`

## Escalation

If you encounter:
- **Architecture decisions**: Consult project architecture docs if present, otherwise ask user
- **Unclear requirements**: Check product/requirements docs if present, otherwise ask user
- **Repeated test failures**: Update progress, flag for human review
- **Scope ambiguity**: Re-read `feature_list.json` for definition of done

---

## Implementation Reuse Rule

Before writing code, check whether a reliable, maintained, and reasonably simple public implementation already exists. Prefer reuse when the integration cost is low. Reuse is **not mandatory** when a dependency is too heavy, poorly maintained, hard to adapt, or would distort the prototype — in that case, implement the minimal version needed and note the decision.

Evaluate: reliability, license, dependency cost, integration complexity, milestone fit, abstraction overhead, and whether a small local implementation would be clearer.

Prefer standard-library first, then small focused dependencies. Avoid large frameworks just because they are popular. Every dependency must directly support the current milestone.

---

## Behavioral Coding Guidelines

### 1. Think Before Coding

State assumptions explicitly. If uncertain, ask. If multiple interpretations exist, present them rather than silently choosing one. Prefer simpler approaches and say so. Stop and name what is confusing rather than proceeding blindly.

### 2. Simplicity First

Write the minimum code that solves the current problem. No speculative features, no single-use abstractions, no unrequested configurability, no error handling for impossible scenarios. If 200 lines could be 50, rewrite it.

### 3. Surgical Changes

Touch only what is necessary. Do not improve adjacent code, comments, or formatting. Match existing style. Mention unrelated dead code but do not delete it. Remove only imports, variables, or functions that your own changes made unused.

Every changed line should trace directly to the current request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals. For multi-step tasks, state a brief plan with a concrete check after each step. Weak success criteria ("make it work") require clarification before proceeding.
