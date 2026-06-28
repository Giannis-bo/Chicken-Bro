# SimC Task Execution Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve SimC result quality while preventing each player from running more than two active template simulation tasks.

**Architecture:** The backend remains the source of truth for queue admission. The frontend uses the existing task-list API for early blocking and readable button state, while the backend enforces the same limit for refreshes, multiple devices, and direct API calls.

**Tech Stack:** Python unittest backend tests, Node `node:test` frontend tests, WeChat mini-program page modules, SQLite/PostgreSQL-compatible task storage.

---

### Task 1: Backend queue guard and timeout budget

**Files:**
- Modify: `tests/news_backend_test.py`
- Modify: `server/news_backend.py`
- Modify: `server/simulator_payload.py`

- [x] Add a failing backend test that submits three different `simcraft_template` fingerprints for the same guest while autorun is disabled. The first two should queue, the third should return `status = "blocked"` with `taskLock.reason = "active_simc_task_limit"` and no third row in `simulator_tasks`.
- [x] Add a failing backend test that patches `server.simulator_payload.run_simcraft_process`, runs a queued template task, and asserts the process layer receives `WOW_SIMC_TEMPLATE_TIMEOUT_SECONDS` while the executed profile still contains `iterations=10000`, `desired_targets=5`, and `max_time=300`.
- [x] Add backend helpers for `simcraft_template_active_task_limit`, `active_simcraft_template_task_rows`, and a structured active-limit payload.
- [x] Pass template-specific timeout seconds into `run_simcraft` for template task execution.
- [x] Run `python -m unittest tests.news_backend_test.NewsBackendTest.test_simcraft_template_final_submit_blocks_third_active_task_for_same_player tests.news_backend_test.NewsBackendTest.test_simcraft_template_task_runner_uses_template_timeout_without_changing_profile`.

### Task 2: Frontend submit gate

**Files:**
- Modify: `tests/simulator-page.test.js`
- Modify: `pages/simulator/simc.js`
- Modify: `pages/simulator/simc.wxml`

- [x] Add a failing frontend test that stubs `requestSimulatorTasks` with two active tasks and asserts submit is blocked before `requestSimulatorAnalysis` is called.
- [x] Add a failing frontend test that feeds a backend `active_simc_task_limit` response and asserts the page keeps submit retry blocked with a Chinese explanation.
- [x] Add active task counting and submit refresh logic in `pages/simulator/simc.js`.
- [x] Bind the submit button label to the active-task limit state in `pages/simulator/simc.wxml`.
- [x] Run `node --test tests/simulator-page.test.js`.

### Task 3: Roadmap and verification

**Files:**
- Modify: `docs/roadmap.md`

- [x] Add a concise 2026-06-28 evidence note for SimC template execution budget and active-task gate.
- [x] Run `python -m unittest tests.news_backend_test`.
- [x] Run `node --test tests/simulator-page.test.js`.
- [x] Run `git diff --check`.

### Task 4: Known SimC compatibility blocker

**Files:**
- Modify: `tests/websim_payload_test.py`
- Modify: `tests/news_backend_test.py`
- Modify: `server/websim_payload.py`
- Modify: `server/news_backend.py`
- Modify: `docs/roadmap.md`

- [x] Rebuild cloud SimC from upstream `midnight` commit `16b061b2d928f7ca57ddd4829f0a727aabbe9ed3` and confirm the saved `deathknight/unholy` + `rider_of_the_apocalypse` profile still reproduces the upstream segmentation fault.
- [x] Block the known incompatible combination before gear-stat snapshot SimC launch and before template final submit.
- [x] Return a Chinese product-facing explanation instead of raw `sim_signal_handler` stderr.
- [x] Cover the blocker with backend tests for both `/api/websim/gear/stats` and `mode=simcraft_template` confirmation.
