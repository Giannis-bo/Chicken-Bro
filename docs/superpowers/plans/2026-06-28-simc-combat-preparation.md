# SimC Combat Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend-owned SimC buff and combat preparation policy with class/spec boundaries and player-visible reporting.

**Architecture:** Add one shared backend module for profile preparation lines and report summaries. Both template SimC and WebSim profile generation call the same helper, and frontend views only display `simcReport.preparation` instead of inferring SimC action names.

**Tech Stack:** Python backend payload builders, WeChat mini-program JavaScript/WXML, Python unittest, Node test runner.

---

### Task 1: Shared Profile Preparation Policy

**Files:**
- Create: `server/simc_preparation.py`
- Modify: `server/simulator_payload.py`
- Modify: `server/websim_payload.py`
- Test: `tests/news_backend_test.py`
- Test: `tests/websim_payload_test.py`

- [x] Write failing tests for `optimal_raid=0`, self-class raid buffs, and no cross-class buffs.
- [x] Run targeted tests and confirm they fail because preparation lines are missing.
- [x] Implement `server/simc_preparation.py` with verified self-class buff mappings and structured summary output.
- [x] Call the helper from template SimC and WebSim profile builders.
- [x] Re-run targeted tests and confirm they pass.

### Task 2: Player-Visible Report Copy

**Files:**
- Modify: `server/news_backend.py`
- Modify: `pages/simulator/simc.js`
- Modify: `pages/simulator/simc.wxml`
- Modify: `pages/simulator/task-detail.js`
- Modify: `pages/simulator/task-detail.wxml`
- Modify: `pages/simulator/tasks.js`
- Test: `tests/news_backend_test.py`
- Test: `tests/simulator-page.test.js`

- [x] Write failing tests that `simcReport.preparation` is present in confirmation, queued summaries, and task detail normalization.
- [x] Run targeted tests and confirm they fail because the report block is missing.
- [x] Add `preparation` to report and summary payloads.
- [x] Display the preparation summary in confirmation, task list, and task detail views.
- [x] Re-run targeted tests and confirm they pass.

### Task 3: Evidence And Documentation

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/simulator-simc-end-to-end.md`

- [x] Update roadmap evidence after tests pass.
- [x] Document the current supported mapping and the rule that unsupported spec preparation remains blocked or partial until SimC binary smoke verifies the exact syntax.
- [x] Run final verification commands.
