# Chickenbro Smart Question Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make time-sensitive natural-language questions discover and use bounded, evidence-appropriate Chickenbro capabilities instead of silently falling through to generic chat.

**Architecture:** Add a pure QuestionFrame/parser and deterministic capability planner before the existing Registry dispatch. Introduce one repository-owned official current-source adapter with an immutable Registry v2 release; carry only de-identified planning outcomes into Trace v3. The backend remains the sole authority for source access, execution and evidence validation.

**Tech Stack:** Python standard library, existing PostgreSQL immutable Registry, existing Blizzard news/forum collector, `unittest`, existing Cloud candidate service and Harness release packet.

## Global Constraints

- No fixed answer for a query, class, spec, patch or source article.
- Network reads only use the already approved Blizzard News and Blizzard Forums source definitions; one bounded request performs no DB write or sync start.
- The runtime has a 10-second current-source total budget and no new dependency.
- `partial`, `failed`, stale or unmatched source facts never authorise ranking, DPS, percentile, BiS or strong personal conclusions.
- The model cannot choose an implementation reference, owner, URL, credential or Tool ID.
- Existing Raider.IO, Warcraft Logs, owner isolation, public chat schema and scheduled jobs remain unchanged.
- Candidate deployment uses `WOW_DEPLOY_START_ASYNC_SYNCS=0`; Schema changes require an explicit PostgreSQL backup, transaction, active Release proof and rollback pointer.

### Task 1: Add QuestionFrame and semantic routing contract

**Files:**
- Create: `server/chickenbro_question_frame.py`
- Modify: `server/chickenbro_agent.py`
- Create: `tests/chickenbro_question_frame_test.py`
- Modify: `tests/chickenbro_agent_test.py`

**Interfaces:**
- Produces `build_chickenbro_question_frame(message, history) -> dict` with `schemaRevision`, `questionType`, `subject`, `scope`, `evidenceNeeds`, and `unresolvedFields`.
- `classify_chickenbro_request` remains a compatibility projection of the frame.

- [ ] **Step 1: Write failing semantic tests.** Cover NQ/奶骑 and canonical holy-paladin resolution, PTR/retail and patch extraction, current-strength versus community-build versus WCL classification, ambiguous subject, and follow-up inheritance from user-only session history.
- [ ] **Step 2: Run `python3 -m unittest tests.chickenbro_question_frame_test tests.chickenbro_agent_test -v` and confirm RED** because the QuestionFrame module and projection do not exist.
- [ ] **Step 3: Implement the pure parser.** Reuse canonical class/spec data, keep player slang in an entity-alias catalog, declare strength/change evidence needs by question type, and never embed answer text or external source access.
- [ ] **Step 4: Re-run the focused tests and confirm GREEN.**
- [ ] **Step 5: Commit QuestionFrame routing.**

### Task 2: Add official current-source evidence adapter

**Files:**
- Create: `server/chickenbro_current_sources.py`
- Create: `tests/chickenbro_current_sources_test.py`
- Modify: `server/news_backend.py`

**Interfaces:**
- Produces `build_current_wow_sources_tool_result(frame, *, article_loader, collector, now) -> ToolResult`.
- Consumes only eligible source records and `source:current-wow-sources:v1` sanitized inputs.

- [ ] **Step 1: Write failing adapter tests.** Assert a matching official PTR holy-paladin change produces compact source facts/references; phase-only evidence is `partial`; unmatched source never creates a strength verdict; a collector timeout produces `failed`; disabled third-party source data is ignored; the collector receives at most approved sources, one article each and the fixed budget.
- [ ] **Step 2: Run `python3 -m unittest tests.chickenbro_current_sources_test -v` and confirm RED.**
- [ ] **Step 3: Implement bounded source selection.** Use current public facts only when they carry matching scope and freshness; otherwise call the existing official collector in memory. Return source/checked times, source status, evidence refs, facts, limitations and no unapproved numbers.
- [ ] **Step 4: Re-run the adapter suite and confirm GREEN.**
- [ ] **Step 5: Commit the current-source adapter.**

### Task 3: Generalize Registry discovery and bind the new adapter

**Files:**
- Modify: `server/chickenbro_registry.py`
- Modify: `server/chickenbro_tool_runtime.py`
- Modify: `server/news_backend.py`
- Create: `server/migrations/postgres/0026_chickenbro_smart_question_chain.sql`
- Modify: `tests/chickenbro_registry_test.py`
- Modify: `tests/chickenbro_tool_runtime_test.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/postgres_schema_test.py`

**Interfaces:**
- Extends request intent with `questionType`, `patchVersion`, `evidenceNeeds` and a bounded QuestionFrame projection.
- The active `chickenbro-tools-2` Release contains the two unchanged v1 source Tools plus `source:current-wow-sources:v1`.

- [ ] **Step 1: Write failing discovery and execution tests.** A resolved current PTR strength frame must select only the official current-source capability; normal community and WCL paths retain their exact v1 selections; unknown adapter/ref fails closed; sanitized adapter input excludes message history, owner and raw source addresses.
- [ ] **Step 2: Run Registry/runtime/agent/schema focused tests and confirm RED.**
- [ ] **Step 3: Extend the closed manifest schema and repository adapter map.** Allow the finite `current_research` request kind and `questionType` context; add only the explicit source adapter binding. Create immutable migration 0026 with content/release hashes and atomic pointer update.
- [ ] **Step 4: Re-run focused Registry/runtime/agent/schema tests and confirm GREEN.**
- [ ] **Step 5: Commit Registry v2.**

### Task 4: Compose evidence-aware answers and trace planning outcomes

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/chickenbro_observability.py`
- Modify: `server/chickenbro_eval.py`
- Modify: `tests/chickenbro_observability_test.py`
- Modify: `tests/chickenbro_eval_test.py`
- Modify: `tests/news_backend_test.py`
- Modify: `tests/fixtures/chickenbro_trace_eval_cases.json`

**Interfaces:**
- Bounded context exposes safe `questionFrame` and `capabilityPlan`.
- Trace v3 exposes only de-identified semantic scope and unmet evidence kinds.

- [ ] **Step 1: Write failing end-to-end tests.** The NQ PTR strength message must produce a frame, select the new Tool, send its source reference to the model, and permit no unsupported number. A tool failure must carry `current_source_unavailable`, preserve no assistant template and record `tool_failed`/`evidence_missing`; a normal build must preserve prior behavior.
- [ ] **Step 2: Run the targeted backend/trace/eval tests and confirm RED.**
- [ ] **Step 3: Add the planning projection and prompt rules.** Cite query-time source evidence, distinguish confirmed change from comparative-strength gap, and revise answer-layer labels/next question without writing response templates. Add Trace v3 validation, projection and deterministic Eval cases.
- [ ] **Step 4: Re-run targeted backend/trace/eval tests and confirm GREEN.**
- [ ] **Step 5: Commit orchestration and observability.**

### Task 5: Contract documentation, candidate verification and handoff

**Files:**
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Create: `artifacts/releases/2026-08-03-chickenbro-smart-question-chain/{requirement.json,manifest.json,evidence.json}`

- [ ] **Step 1: Record exact scope, user acceptance, migration, source boundary, rollback pointer and candidate commands in the task packet.**
- [ ] **Step 2: Run development suites:** QuestionFrame, current-source, Registry/runtime, Trace/Eval and affected backend tests; then `git diff --check`.
- [ ] **Step 3: Run final local Harness full profile on the clean candidate head.**
- [ ] **Step 4: Perform local CR against roadmap, design, owner maps and source boundary; fix valid findings and rerun affected verification.**
- [ ] **Step 5: Deploy the immutable candidate.** Back up production PostgreSQL target and environment, apply migration 0026 transactionally, start candidate service on 8788 with async sync disabled, verify code/release identity, `/health`, `/api/data/health`, a generic chat smoke, the PTR current-source smoke, WCL/Raider.IO regression paths, timer state and rollback pointer.
- [ ] **Step 6: Submit the real WeChat chat flow for user acceptance.** Do not claim user acceptance from API success or an automated response.
