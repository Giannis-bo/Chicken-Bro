# Chickenbro Evidence Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make time-sensitive Chickenbro questions produce a general, source-bounded Evidence Plan and a user-visible `answered`/`partial`/`researching`/`blocked` outcome instead of treating an unsupported comparison as a failed or terminal chat turn.

**Status:** Candidate verification passed at runtime identity `71882e89`; real WeChat acceptance remains pending. See [candidate evidence](../../artifacts/releases/2026-08-04-chickenbro-evidence-planner/evidence.json).

**Architecture:** Keep `QuestionFrame` as the source-agnostic natural-language parser and add a pure `EvidencePlan` projection that maps declared evidence needs to scenario-specific facets. `news_backend.py` remains the owner of Registry dispatch and answer composition; it attaches the pure plan to bounded context, preserves the existing public envelope with an additive `evidenceOutcome`, and composes deterministic partial answers only from the plan. Trace v4 records only allowlisted facet keys, statuses, comparison scope and outcome.

**Tech Stack:** Python standard library and `unittest`; PostgreSQL-backed immutable Chickenbro Registry; TypeScript, React/Taro, Vitest; existing Harness and candidate backend/WeChat package scripts.

## Global Constraints

- Do not write a fixed answer for any class, spec, patch, provider or player phrase.
- PTR/retail and Mythic+/raid/PvP scopes remain isolated; a same-role Raider.IO high-key signal never proves a cross-spec DPS/Tier/representation/personal-performance conclusion.
- Reuse only current immutable Registry capabilities in this slice; do not add Archon, Wowhead, Icy Veins, URLs, credentials, collectors, syncs, backfills or arbitrary model retrieval.
- `researching` is emitted only when a backend-owned, persisted and cancellable job identity exists; this slice creates no such job and therefore must not emit it for synchronous source reads.
- `partial`, source failure and `blocked` remain literal. HTTP 200, a model response or a service restart never upgrades the player-visible evidence outcome.
- Trace contains no raw message, model output, source body, owner identity, credential or unbounded URL.
- Keep the public chat envelope backward compatible: `evidenceOutcome` is optional/additive and old clients continue to accept messages that omit it.
- Candidate deployment uses `WOW_DEPLOY_START_ASYNC_SYNCS=0`; no timer, source refresh or scheduled collector is started by this task.

---

### Task 1: Build the pure Evidence Plan contract

**Files:**
- Create: `server/chickenbro_evidence_plan.py`
- Create: `tests/chickenbro_evidence_plan_test.py`

**Interfaces:**
- Consumes: a `QuestionFrame`, Registry projection `{selectedCapabilityIds}`, and compact source ToolResults.
- Produces: `build_chickenbro_evidence_plan(question_frame, registry_context, source_evidence) -> dict` with `schemaRevision`, `comparisonScope`, `facets`, `selectedCapabilityIds`, `unmetEvidenceNeeds`, `outcome`, and `continuationPolicy`.
- Facet statuses are exactly `planned`, `supported`, `partial`, `unavailable`; outcomes are exactly `answered`, `partial`, `researching`, `blocked`.

- [ ] **Step 1: Write failing pure-plan tests**

```python
def test_retail_mplus_strength_plan_is_answered_from_same_subject_signal(self):
    plan = build_chickenbro_evidence_plan(
        retail_mplus_elemental_frame(),
        verified_registry(["source:raiderio-strength:v1"]),
        [raiderio_strength_source("source_reference")],
    )
    self.assertEqual("answered", plan["outcome"])
    self.assertEqual("high_key_trend", plan["facets"][0]["key"])
    self.assertEqual("supported", plan["facets"][0]["status"])

def test_cross_spec_dps_plan_is_partial_and_drops_subject_signal(self):
    plan = build_chickenbro_evidence_plan(
        cross_spec_mplus_dps_frame(),
        verified_registry(["source:raiderio-strength:v1"]),
        [raiderio_strength_source("source_reference")],
    )
    self.assertEqual("partial", plan["outcome"])
    self.assertEqual("cross_spec_performance", plan["facets"][0]["key"])
    self.assertEqual("unavailable", plan["facets"][0]["status"])
    self.assertEqual(["comparative_strength_signal"], plan["unmetEvidenceNeeds"])
```

- [ ] **Step 2: Run test to verify RED**

Run: `python3 -m unittest tests.chickenbro_evidence_plan_test -v`
Expected: an import failure for `server.chickenbro_evidence_plan`.

- [ ] **Step 3: Write minimal implementation**

```python
EVIDENCE_PLAN_SCHEMA_REVISION = "chickenbro-evidence-plan-v1"

def build_chickenbro_evidence_plan(question_frame, registry_context, source_evidence):
    frame = question_frame if isinstance(question_frame, dict) else {}
    scope = str(frame.get("comparisonScope") or "subject").strip().lower()
    facets = _facets_for_frame(frame, scope)
    _mark_supported_facets(facets, source_evidence, scope)
    unmet = _unmet_evidence_needs(frame, facets)
    return {
        "schemaRevision": EVIDENCE_PLAN_SCHEMA_REVISION,
        "comparisonScope": scope,
        "facets": facets,
        "selectedCapabilityIds": _selected_capability_ids(registry_context),
        "unmetEvidenceNeeds": unmet,
        "outcome": _outcome_for(frame, facets, unmet),
        "continuationPolicy": "replan" if scope == "cross_spec" else "reuse_compatible_only",
    }
```

`_facets_for_frame` maps official changes to `official_changes`, subject-scoped M+ comparison to `high_key_trend`, and cross-spec comparison to `cross_spec_performance`. Only a `source_reference` or `verified` result with evidence references can mark a facet `supported`; Registry selection alone cannot.

- [ ] **Step 4: Run test to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_evidence_plan_test -v`
Expected: all cases pass, including PTR-with-official-change=`partial`, unsupported raid comparison=`partial`, and malformed input producing a non-crashing plan.

- [ ] **Step 5: Commit**

```bash
git add server/chickenbro_evidence_plan.py tests/chickenbro_evidence_plan_test.py
git commit -m "feat(chickenbro): add evidence plan contract"
```

### Task 2: Attach the plan to bounded context and expose an additive outcome

**Files:**
- Modify: `server/news_backend.py:7739-7776,7906-8056,8346-8404`
- Modify: `packages/domain/src/entities.ts:929-939`
- Modify: `packages/api-client/src/simulator.ts:152-170`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `packages/api-client/src/simulator.test.ts`

**Interfaces:**
- Consumes: `build_chickenbro_evidence_plan(...)` and the existing `capabilityPlan`.
- Produces: `boundedContext.evidencePlan` and `evidenceOutcome?: "answered" | "partial" | "researching" | "blocked"` on validated assistant payloads.
- Compatibility: `capabilityPlan` remains unchanged; the client accepts payloads that omit `evidenceOutcome`.

- [ ] **Step 1: Write failing integration tests**

```python
def test_ptr_official_change_context_exposes_partial_outcome(self):
    bounded = backend.build_chickenbro_bounded_context(
        "NQ 在 12.1 PTR 强度如何？", {}, source_tool_results=official_ptr_change_packet(),
    )
    self.assertEqual("partial", bounded["evidencePlan"]["outcome"])
    self.assertEqual("部分可验证证据", bounded["basisLabel"])

def test_validated_answer_carries_context_outcome(self):
    payload = backend.validate_chickenbro_model_output(valid_answer_payload(), partial_bounded_context())
    self.assertEqual("partial", payload["evidenceOutcome"])
```

```ts
it('accepts a backward-compatible partial evidence outcome', () => {
  expect(parseChickenbroResponse(withPayload({ evidenceOutcome: 'partial' }))).toBeDefined()
})
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_agent_test -v` and `npm run test:taro -- packages/api-client/src/simulator.test.ts`
Expected: missing `evidencePlan`/ `evidenceOutcome` assertions fail.

- [ ] **Step 3: Write minimal implementation**

```python
evidence_plan = build_chickenbro_evidence_plan(question_frame, registry_context, source_evidence)
bounded_context["evidencePlan"] = evidence_plan
if evidence_plan.get("outcome") == "partial":
    bounded_context["basisLabel"] = "部分可验证证据"
validated["evidenceOutcome"] = bounded_context.get("evidencePlan", {}).get("outcome", "")
```

Add `evidenceOutcome?: 'answered' | 'partial' | 'researching' | 'blocked'` to `AssistantPayload`. The API parser accepts it only when absent or one of those literals.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_question_frame_test tests.chickenbro_agent_test tests.news_backend_test -q && npm run test:taro -- packages/api-client/src/simulator.test.ts`
Expected: targeted backend/client tests pass and old payload fixtures remain valid.

- [ ] **Step 5: Commit**

```bash
git add server/news_backend.py packages/domain/src/entities.ts packages/api-client/src/simulator.ts tests/chickenbro_agent_test.py packages/api-client/src/simulator.test.ts
git commit -m "feat(chickenbro): expose evidence outcomes"
```

### Task 3: Compose plan-derived partial answers and preserve compatible follow-ups

**Files:**
- Modify: `server/news_backend.py:8864-9052`
- Modify: `tests/chickenbro_agent_test.py:808-1054`

**Interfaces:**
- Consumes: `boundedContext.evidencePlan`, `questionFrame`, and current validated answer schema.
- Produces: existing response envelope with `answerSource="deterministic_evidence_plan"`, `evidenceOutcome="partial"`, named missing facet, and one compatible continuation.

- [ ] **Step 1: Write failing stream tests**

```python
def test_cross_spec_request_returns_plan_partial_not_retry_or_manual_lookup(self):
    result = stream_result_for("给我当前全职业 DPS 横向排名", prior_elemental_history())
    self.assertEqual("partial", result["answer"]["evidenceOutcome"])
    self.assertEqual("deterministic_evidence_plan", result["answer"]["answerSource"])
    self.assertIn("跨专精", result["answer"]["answer"])
    self.assertIn("同口径", result["answer"]["answer"])
    self.assertNotIn("重试", result["answer"]["answer"])
    self.assertNotIn("自己去", result["answer"]["answer"])

def test_ratio_follow_up_remains_answered_with_compatible_facet(self):
    result = stream_result_for("解读一下15/27是啥意思？", prior_strength_history())
    self.assertEqual("answered", result["answer"]["evidenceOutcome"])
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_agent_test.ChickenbroAgentTest.test_streamed_unmet_comparative_strength_returns_an_evidence_boundary_without_model -v`
Expected: the old answer source and absent outcome assertions fail.

- [ ] **Step 3: Write minimal implementation**

```python
def chickenbro_unmet_comparative_strength_result(bounded_context):
    plan = bounded_context.get("evidencePlan") or {}
    missing = plan.get("unmetEvidenceNeeds") or []
    if plan.get("outcome") != "partial" or "comparative_strength_signal" not in missing:
        return None
    return chickenbro_validated_plan_partial_result(
        bounded_context,
        missing_facet="cross_spec_performance",
        continuation="我可以继续按已覆盖的专精与场景比较；跨专精榜需要同场景、同指标的比较来源。",
    )
```

The helper derives labels from allowlisted facet keys and scope only. It must not interpolate raw source bodies, model text or user identity, and continues to reject unsupported rank/DPS claims.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_question_frame_test tests.chickenbro_agent_test tests.chickenbro_tool_runtime_test tests.news_backend_test -q`
Expected: PTR/retail and raid/M+ isolation remain green; the four-turn smoke returns final `succeeded`, no retry event, and no inherited 15/27 in the cross-spec reply.

- [ ] **Step 5: Commit**

```bash
git add server/news_backend.py tests/chickenbro_agent_test.py
git commit -m "fix(chickenbro): continue partial comparison research"
```

### Task 4: Record outcome safely and render a compact player-facing state

**Files:**
- Modify: `server/chickenbro_observability.py:14-96,281-307,471-540,616-678`
- Modify: `tests/chickenbro_observability_test.py`
- Modify: `packages/design-system/src/components/ChickenbroChatComponents.tsx`
- Modify: `packages/design-system/src/components/ChickenbroChatComponents.module.scss`
- Create: `packages/design-system/src/components/ChickenbroChatComponents.test.ts`

**Interfaces:**
- Consumes: `boundedContext.evidencePlan` and optional `AssistantPayload.evidenceOutcome`.
- Produces: Trace v4 `{comparisonScope, evidenceFacetKeys, evidenceFacetStatuses, evidenceOutcome}` and a compact assistant-card state label.
- Allowed labels: `已完成证据判断`, `部分证据`, `受控检索中`, `当前不可执行`; no internal source/tool identifier is rendered.

- [ ] **Step 1: Write failing trace and component-contract tests**

```python
def test_trace_v4_keeps_only_allowlisted_plan_projection(self):
    trace = build_trace(partial_cross_spec_context())
    self.assertEqual("chickenbro-agent-trace-v4", trace["schemaRevision"])
    self.assertEqual("cross_spec", trace["comparisonScope"])
    self.assertEqual(["cross_spec_performance"], trace["evidenceFacetKeys"])
    self.assertEqual("partial", trace["evidenceOutcome"])
    self.assertNotIn("全职业 DPS 横向排名", json.dumps(trace, ensure_ascii=False))
```

```ts
it('renders a partial marker without source keys', () => {
  const source = read('ChickenbroChatComponents.tsx')
  expect(source).toContain('data-role="chickenbro-evidence-outcome"')
  expect(source).toContain("partial: '部分证据'")
  expect(source).not.toContain('source:raiderio-strength:v1')
})
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_observability_test -v && npm run test:taro -- packages/design-system/src/components/ChickenbroChatComponents.test.ts`
Expected: v3 trace and missing marker assertions fail.

- [ ] **Step 3: Write minimal implementation**

```python
TRACE_SCHEMA_REVISION_V4 = "chickenbro-agent-trace-v4"
TRACE_KEYS_V4 = TRACE_KEYS_V3 | {
    "comparisonScope", "evidenceFacetKeys", "evidenceFacetStatuses", "evidenceOutcome",
}
```

Normalize only allowlisted facet keys/statuses/outcomes; v1-v3 historical traces remain valid. In `ChickenbroTranscript`, map `message.payload?.evidenceOutcome` to the allowed label and render it before answer text inside the existing bubble. Its style must wrap and be content-sized, never impose a transcript height.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_observability_test -q && npm run test:taro -- packages/design-system/src/components/ChickenbroChatComponents.test.ts apps/mini-taro/src/pages/simulator/simulator-home-dock-contract.test.ts`
Expected: trace redaction, state marker and flexible transcript contracts pass.

- [ ] **Step 5: Commit**

```bash
git add server/chickenbro_observability.py tests/chickenbro_observability_test.py packages/design-system/src/components/ChickenbroChatComponents.tsx packages/design-system/src/components/ChickenbroChatComponents.module.scss packages/design-system/src/components/ChickenbroChatComponents.test.ts
git commit -m "feat(chickenbro): surface evidence plan state"
```

### Task 5: Verify, deploy one candidate, and hand off device acceptance

**Files:**
- Create: `artifacts/releases/2026-08-04-chickenbro-evidence-planner/{requirement.json,manifest.json,evidence.json}`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: a clean implementation head, existing candidate service topology, existing release build variables and the outcome/trace test matrix.
- Produces: one task-scoped release packet, candidate identity, candidate API smoke, release WeChat package identity, rollback path and manual WeChat checklist.

- [ ] **Step 1: Create the release requirement before final verification**

Freeze first-slice-only scope; no third-party source onboarding; no migration/Registry pointer change; literal `partial`; real-device answer-card visibility; no collector backflow; and manual acceptance pending after candidate deployment.

- [ ] **Step 2: Run local verification and local CR**

Run:

```bash
python3 -m unittest tests.chickenbro_evidence_plan_test tests.chickenbro_question_frame_test tests.chickenbro_agent_test tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test tests.chickenbro_observability_test tests.news_backend_test -q
npm run typecheck
npm run lint
npm run test:taro
npm run audit:ui-architecture
git diff --check origin/main...HEAD
```

Expected: all suites pass. Review the final diff: no new provider host, source adapter, Registry pointer, source data write or source body in Trace.

- [ ] **Step 3: Build the release-configured WeChat package**

Run:

```bash
WOW_ASSET_RUNTIME_ROOT=https://api.chickenbro.cloud/wow-assets/releases/2026-07-19-taro-full-integration \
WOW_RUNTIME_MEDIA_ROOT=https://api.chickenbro.cloud/wow-media/releases/2026-07-20-wow-icons-v1 \
WOW_BACKEND_API_BASE_URL=https://api.chickenbro.cloud \
WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes \
npm run build:weapp && npm run verify:ui-package:release
```

Expected: an identity-bound package with no domain/asset blocker. This does not prove DevTools or real-device acceptance.

- [ ] **Step 4: Deploy the exact head as one candidate**

Copy only changed repository-owned files to a new `/opt/wow-mini-program-candidates/chickenbro-evidence-planner-<shortsha>` target, derive a dedicated candidate unit on an unused loopback port, set `WOW_DEPLOY_START_ASYNC_SYNCS=0`, create a timestamped remote backup before replacement, record SHA-256 for every changed runtime file, and restart only the candidate service.

- [ ] **Step 5: Run candidate smoke and record literal state**

POST four stream turns: PTR strength, retail M+ strength, 15/27 explanation, then cross-spec DPS. Assert final `succeeded`; PTR and cross-spec are `partial`; retail M+ and compatible ratio are `answered`; no retry, prior 15/27 or source-key leak. Inspect timers before/after; source refresh/backfill/sync state is unchanged.

- [ ] **Step 6: Commit release evidence and hand off device validation**

```bash
git add artifacts/releases/2026-08-04-chickenbro-evidence-planner docs/plans/README.md docs/roadmap.md
git commit -m "docs(chickenbro): record evidence planner candidate"
```

Hand the candidate WeChat package to the user with four checks: no retry on follow-ups, visible `部分证据` where appropriate, no raw source key/opaque ratio as the main conclusion, and no clipped transcript card. Do not merge, push, clean up or describe the task as accepted until the user explicitly confirms real-device verification.

## Plan self-review

- Spec coverage: Tasks 1-3 implement the first-slice Evidence Plan, outcome semantics and cross-turn recovery; Task 4 covers Trace and player state; Task 5 covers release, candidate deployment and user acceptance.
- Placeholder scan: no unresolved source, provider, metric or verification decision remains. Third-party source expansion is explicitly deferred to a separate SourceContract slice.
- Type consistency: `evidenceOutcome` uses the same four literals in pure plan, context, server payload, domain type, API parser, trace projection and transcript label.
