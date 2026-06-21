# Parallel Optimization Lanes Design

## Context

The project has moved from core framework build-out into continuous optimization. The active work should improve three areas in parallel:

- Gear simulation: make the embedded gear simulator easier to trust, inspect, and save from.
- SimC: make the fixed-template SimC flow more explainable and harder to submit incorrectly.
- ZhaJi Captain: start a first evidence-bound player coaching surface without turning it into an unconstrained chat agent.

The shared risk is contract drift. Gear templates feed SimC, and SimC/WCL reports become evidence for ZhaJi Captain. Work must therefore be parallel in isolated branches, but serialized at integration points.

## Recommended Architecture

Use one coordination branch and three isolated worktrees:

- `codex/parallel-optimization-contracts`: shared docs, roadmap, and worktree guardrails only.
- `codex/gear-sim-opt`: gear simulator experience and explainability.
- `codex/simc-opt`: fixed-template SimC confirmation, blocking, report, and task detail polish.
- `codex/zhaji-captain-start`: ZhaJi Captain evidence coach v0.

The integration order is gear first, SimC second, ZhaJi Captain third. Gear outputs are an input to SimC, and SimC/WCL evidence is an input to ZhaJi Captain.

## Lane A: Gear Simulator Optimization

Goal: move the gear simulator from "can select and save gear" to "players can understand each slot's source, trust state, and executable status."

Primary files:

- `pages/builds/detail.*`
- `pages/builds/websim-api.js`
- `pages/common/game-asset.js`
- `server/websim_payload.py`
- `tests/builds-page.test.js`
- `tests/frontend-api-client.test.js`
- `tests/websim_payload_test.py`

Boundaries:

- Do not restore `/api/websim/gear/stats` as a page-level stat snapshot.
- Do not show DPS conclusions in the gear page.
- Continue saving gear templates as complete 16-slot canonical raw strings.
- Display-only and source-reference gear must never be represented as executable SimC gear.

First deliverable:

- Slot sheet and community template import clearly show verified, partial, source-reference, missing-slot, and blocker states.
- Save validation explains exactly why a gear template cannot be saved.

## Lane B: SimC Optimization

Goal: make the fixed-template SimC flow explainable, deterministic, and consistent from confirmation through task detail.

Primary files:

- `pages/simulator/simc.*`
- `pages/simulator/task-detail.*`
- `server/simulator_payload.py`
- `server/news_backend.py` only for routing or persistence glue
- `tests/simulator-page.test.js`
- `tests/news_backend_test.py`
- `tests/websim_payload_test.py`

Boundaries:

- `confirmOnly=true` and final submit must reuse the same payload, with final submit only flipping execution/persistence flags.
- LLM must not decide whether input is executable.
- Display-only gear and UI-only talent fields must not become SimC profile input.
- Blocked states must be deterministic and visible.

First deliverable:

- Confirmation preview and task detail show talent template, gear template, scenario, missing fields, run policy, evidence state, and allowed-number source.

## Lane C: ZhaJi Captain Evidence Coach v0

Goal: start ZhaJi Captain as an evidence-bound player coach that consumes existing project evidence and reports missing inputs honestly.

Primary files:

- New backend module such as `server/coach_payload.py`
- Minimal route glue in `server/news_backend.py`
- New page such as `pages/simulator/coach.*` or an integrated simulator entry, depending on implementation plan review
- New tests such as `tests/coach_payload_test.py`
- `tests/simulator-page.test.js`

Boundaries:

- No fabricated rankings, DPS/HPS, log findings, or player percentile claims.
- If WCL, SimC, role, item level, or comparable sample evidence is missing, return `missingInputs` and general guidance only.
- Keep deep Codex Worker behavior out of v0.
- The model can explain and prioritize, but numeric facts must come from evidence references.

First deliverable:

- A deterministic evidence schema and v0 coaching response with `summary`, `confidence`, `evidenceRefs`, `priorityActions`, `missingInputs`, and `nextSteps`.

## Shared Contracts

All lanes must preserve these contracts:

- Gear templates remain canonical 16-slot raw strings for executable submissions.
- SimC executable gear must include canonical slot keys and item ids at minimum.
- Confirmation and final submit reuse the same profile or build context.
- Evidence UI must distinguish official, SimC, WCL, Raider.IO, source-reference, partial, stale, blocked, and LLM inference.
- Roadmap updates must not present planned work as already implemented.

## Integration Strategy

1. Finish and merge `codex/parallel-optimization-contracts`.
2. Rebase or recreate the three lane worktrees from the coordination commit.
3. Merge `codex/gear-sim-opt` after lane tests pass.
4. Rebase `codex/simc-opt` onto updated `main`, then merge after SimC and WebSim contract tests pass.
5. Rebase `codex/zhaji-captain-start` onto updated `main`, then merge after coaching schema and simulator UI tests pass.

## Approval

This design reflects the user-approved direction from 2026-06-21: start gear simulator optimization, SimC optimization, and ZhaJi Captain startup as parallel but contract-bound work lanes.
