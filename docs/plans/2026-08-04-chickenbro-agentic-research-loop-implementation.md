# Chickenbro Agentic Research Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Codex, rather than a question-specific routing tree, plan and re-plan read-only Chickenbro research through the published ToolBox, then return source-grounded answers that continue naturally across follow-up questions.

**Architecture:** Run one native Codex Agent conversation with a candidate-only profile. Codex receives the player message and compact conversation history, decides its own research goal, may use native live web search, and may call the read-only MCP ToolBox in the same turn. The backend does not create a `ResearchPlan`, select a tool, execute a tool on the model's behalf, force a JSON response, or reject natural prose through a per-claim schema. It only owns MCP read-only/SSRF/rate boundaries, session persistence and timeout. Legacy `QuestionFrame`/`EvidencePlan` paths remain available only when the native feature flag is off.

**Tech Stack:** Python standard library and `unittest`; native Codex live web search; a repository-owned stdio MCP server for bounded public URL reads and service-owned community snapshots; Codex CLI profile layering; TypeScript/Taro compatibility tests; Harness candidate deployment scripts.

## Global Constraints

- Do not encode a class, spec, patch, content type, provider, or sample question as an agentic tool-selection rule or answer template.
- The agent may invoke only active, published, read-only Tool manifests. It cannot access arbitrary URLs, files, Shell, SQL, credentials, registries, syncs, backfills, or production configuration.
- A player-visible number or strong comparative claim must be grounded in actual MCP observations and their actual evidence references. Empty, stale, timed-out, partial, or single-subject observations remain literal, but a valid natural answer is never replaced merely because it cannot be decomposed into model-authored claim rows.
- PTR/retail, raid/Mythic+/PvP, personal and public observations may be combined only when their returned scope fields are compatible. This is a general claim validator, not a keyword router.
- Keep all legacy response envelopes backward compatible. Native-agent citations are derived from MCP observation records; clients continue to consume the existing assistant payload and optional `evidenceOutcome`.
- Keep tool execution synchronous and bounded in this release by the generic ToolBox's own public-web limits, timeouts and rate budget. There is no hidden "two planning turns" or backend-selected source loop; no background `ResearchRun`, no source refresh, and `WOW_DEPLOY_START_ASYNC_SYNCS=0` during candidate deployment.
- Do not add Archon or any new third-party collector in this task. Its host, access method, terms, parser fixture, freshness policy, cache, limit and rollback require their own approved `SourceContract`; existing Raider.IO, Warcraft Logs and official adapters are the first published ToolBox.
- Candidate deployment must use a new service and port identity, render a candidate-only Codex MCP profile, record exact Git/runtime identity, and leave production unchanged until user acceptance.

## Native Agent correction (authoritative for this candidate)

The earlier `ResearchPlan → backend execution → final JSON + claimRefs` task steps are historical implementation context only; they are **not** this candidate's execution path. This candidate proves: Codex chooses concrete research queries and whether to use native web search, `research_public_web`, or `inspect_current_mythic_plus_snapshot`; natural Chinese answers publish without a JSON or per-claim response gate; MCP citations come only from tool observations written during the same job; follow-ups carry compact conversation history and can research again; a Codex/MCP transport failure remains an honest failure rather than silently returning a legacy template.

---

### Task 1: Create the generic ResearchPlan and observation contracts

**Files:**
- Create: `server/chickenbro_research.py`
- Create: `tests/chickenbro_research_test.py`

**Interfaces:**
- Produces `research_plan_schema() -> dict`, `build_research_catalog(release) -> list[dict]`, `research_plan_prompt(message, history, catalog, observations, turn) -> str`, and `validate_research_plan(payload, catalog) -> dict`.
- A valid plan has `{schemaRevision, goal, hypotheses, informationGaps, toolCalls, decision}`; a call has `{toolId, arguments}`. `decision` is `continue` or `answer`; an empty call list is legal only for `answer`.
- Produces `observations_from_tool_results(tool_calls, results) -> list[dict]` containing only tool id, source key, status, evidence refs, declared scope and bounded limitations/facts; never raw message, source body, URL query secrets, implementation ref, or model reasoning.

- [ ] **Step 1: Write failing contract tests**

```python
def test_valid_plan_can_select_two_published_tools_without_question_labels(self):
    catalog = [catalog_tool("source:official:v1"), catalog_tool("source:community:v1")]
    plan = validate_research_plan(
        {
            "schemaRevision": "chickenbro-research-plan-v1",
            "goal": "比较当前可验证的表现",
            "hypotheses": ["来源可能覆盖不同维度"],
            "informationGaps": ["是否有同口径样本"],
            "toolCalls": [
                {"toolId": "source:official:v1", "arguments": {"productPhase": "ptr"}},
                {"toolId": "source:community:v1", "arguments": {"scenarioKey": "mythic_plus"}},
            ],
            "decision": "continue",
        },
        catalog,
    )
    self.assertEqual(["source:official:v1", "source:community:v1"], [call["toolId"] for call in plan["toolCalls"]])

def test_plan_rejects_unpublished_tool_and_unsafe_argument(self):
    with self.assertRaisesRegex(ValueError, "published tool"):
        validate_research_plan(plan_with("https://example.invalid"), [catalog_tool("source:official:v1")])
    with self.assertRaisesRegex(ValueError, "unsafe research argument"):
        validate_research_plan(plan_with("source:official:v1", {"url": "file:///etc/passwd"}), [catalog_tool("source:official:v1")])
```

- [ ] **Step 2: Run the new test to verify RED**

Run: `python3 -m unittest tests.chickenbro_research_test -v`

Expected: FAIL because `server.chickenbro_research` does not yet exist.

- [ ] **Step 3: Implement the smallest pure contract**

```python
RESEARCH_PLAN_SCHEMA_REVISION = "chickenbro-research-plan-v1"
MAX_RESEARCH_TURNS = 2
MAX_TOOL_CALLS_PER_TURN = 8  # process resource ceiling; manifests own per-Tool budgets

def validate_research_plan(payload, catalog):
    published = {item["toolId"]: item for item in catalog}
    calls = _bounded_calls(payload.get("toolCalls"), published)
    decision = _allowed_decision(payload.get("decision"), calls)
    return _normalized_plan(payload, calls, decision)
```

`_bounded_calls` deduplicates no values silently: it rejects unknown/disabled/non-read-only tool ids, calls beyond the process resource ceiling, calls that exceed a manifest-declared per-Tool budget, unsupported keys, values longer than the declared limit, nested payloads, URL/path/credential-like keys and arguments absent from that tool's `inputSchema.required`. `build_research_catalog` strips `implementationRef`, Registry hashes and provenance before a model can see it.

- [ ] **Step 4: Run the contract tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_research_test -v`

Expected: all catalog sanitization, malformed model JSON, unsafe argument, duplicate tool and bounded-observation tests pass.

- [ ] **Step 5: Commit the contract**

```bash
git add server/chickenbro_research.py tests/chickenbro_research_test.py
git commit -m "feat(chickenbro): add agentic research plan contract"
```

### Task 2: Let the runtime execute validated per-tool calls without rule-based discovery

**Files:**
- Modify: `server/chickenbro_registry.py`
- Modify: `server/chickenbro_tool_runtime.py`
- Modify: `tests/chickenbro_registry_test.py`
- Modify: `tests/chickenbro_tool_runtime_test.py`

**Interfaces:**
- Produces `published_chickenbro_tools(release) -> list[dict]`, which validates the immutable release but returns every active read-only manifest in stable `toolId` order; it does not inspect message, class, patch, scenario or question type.
- Produces `execute_chickenbro_tool_calls(manifests, adapter_bindings, calls) -> list[dict]`, where every call has its own sanitized `{intent, context}` projection and maps exactly to one published manifest.
- Retains `discover_chickenbro_capabilities` and `execute_chickenbro_selected_tools` unchanged for fallback compatibility.

- [ ] **Step 1: Write failing runtime tests**

```python
def test_published_catalog_does_not_depend_on_question_frame(self):
    release = signed_release([current_sources_manifest(), community_strength_manifest(...)])
    self.assertEqual(
        ["source:current-wow-sources:v1", "source:raiderio-strength:v1"],
        [tool["toolId"] for tool in published_chickenbro_tools(release)],
    )

def test_each_validated_call_receives_its_own_arguments(self):
    results = execute_chickenbro_tool_calls(
        [manifest("source:a:v1"), manifest("source:b:v1")], bindings(),
        [{"toolId": "source:a:v1", "arguments": {"classKey": "paladin"}},
         {"toolId": "source:b:v1", "arguments": {"classKey": "warrior"}}],
    )
    self.assertEqual(["paladin", "warrior"], [row["facts"][0]["classKey"] for row in results])
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test -v`

Expected: FAIL with missing `published_chickenbro_tools` and `execute_chickenbro_tool_calls`.

- [ ] **Step 3: Implement stable published discovery and call execution**

```python
def published_chickenbro_tools(release):
    validated = validate_chickenbro_registry_release(release)
    return [copy.deepcopy(item) for item in sorted(
        validated["manifests"], key=lambda item: item["toolId"]
    ) if item["riskClass"] == "read_only" and item["status"] == "active"]
```

For execution, resolve each call's `toolId` against that list, require the signed `implementationRef` to still match `APPROVED_IMPLEMENTATIONS`, construct only the current `_REQUEST_INTENT_FIELDS`/`_REQUEST_CONTEXT_FIELDS`, retain adapter timeouts/freshness/result validation, and return a failed result for an adapter error rather than aborting unrelated calls.

- [ ] **Step 4: Run the runtime tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test -v`

Expected: existing deterministic discovery tests remain green; the new agentic catalog and per-call execution tests pass.

- [ ] **Step 5: Commit the runtime change**

```bash
git add server/chickenbro_registry.py server/chickenbro_tool_runtime.py tests/chickenbro_registry_test.py tests/chickenbro_tool_runtime_test.py
git commit -m "feat(chickenbro): execute validated agentic tool calls"
```

### Task 3: Orchestrate Codex plan → observations → one optional re-plan

**Files:**
- Modify: `server/news_backend.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/chickenbro_research_test.py`

**Interfaces:**
- Produces `run_chickenbro_research(message, history, context, *, registry_loader, registry_runtime, planner_runner, adapter_bindings) -> dict` with `{status, turns, observations, registryContext, sourceToolResults, limitations}`.
- `status` is `completed`, `partial`, `unavailable`, or `failed`; it is not the player-visible `researching` state because this release creates no persisted cancellable job.
- `build_chickenbro_bounded_context` consumes the returned research packet when `WOW_CHICKENBRO_AGENTIC_RESEARCH_ENABLED=1`, exposes only an allowlisted `agenticResearch` projection internally, and otherwise preserves the current deterministic loader.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_agent_replans_after_a_partial_first_observation(self):
    runner = scripted_runner([
        plan("continue", ["source:current-wow-sources:v1"]),
        plan("answer", ["source:raiderio-strength:v1"]),
    ])
    result = backend.run_chickenbro_research(
        "现在这个版本的表现如何？", [], {},
        registry_loader=lambda: signed_release_with_sources(),
        registry_runtime=ChickenbroRegistryRuntime(60),
        planner_runner=runner, adapter_bindings=fixture_bindings(),
    )
    self.assertEqual("completed", result["status"])
    self.assertEqual(2, len(result["turns"]))
    self.assertEqual(
        ["source:current-wow-sources:v1", "source:raiderio-strength:v1"],
        [row["toolId"] for row in result["observations"]],
    )

def test_agentic_path_never_invokes_legacy_question_discovery(self):
    with mock.patch.object(backend, "classify_chickenbro_request", side_effect=AssertionError("legacy routing")):
        result = backend.run_chickenbro_research(...)
    self.assertEqual("completed", result["status"])
```

- [ ] **Step 2: Run the orchestration tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_research_test tests.chickenbro_agent_test -v`

Expected: FAIL with missing `run_chickenbro_research` and no agentic context projection.

- [ ] **Step 3: Implement the bounded loop and compatibility fallback**

```python
for turn in range(MAX_RESEARCH_TURNS):
    payload = planner_runner(research_plan_prompt(message, history, catalog, observations, turn), schema=research_plan_schema())
    plan = validate_research_plan(parse_research_plan(payload), catalog)
    results = execute_chickenbro_tool_calls(manifests, bindings, plan["toolCalls"])
    observations.extend(observations_from_tool_results(plan["toolCalls"], results))
    if plan["decision"] == "answer" or not plan["toolCalls"]:
        break
```

The loop executes a second plan only after an actual first observation and only if the first plan asks to continue. A model/Registry/plan validation failure returns a literal `unavailable` or `partial` packet and calls the already-tested legacy loader; it never reports an imaginary background task. Register `default_chickenbro_model_runner` as the production planner only when the feature flag is enabled.

- [ ] **Step 4: Run the orchestrator tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_research_test tests.chickenbro_agent_test tests.chickenbro_question_frame_test -v`

Expected: scripted re-plan, unavailable-model fallback, per-turn tool budget, stale observation and legacy compatibility cases pass.

- [ ] **Step 5: Commit the orchestration**

```bash
git add server/news_backend.py server/chickenbro_research.py tests/chickenbro_agent_test.py tests/chickenbro_research_test.py
git commit -m "feat(chickenbro): orchestrate codex research loop"
```

### Task 4: Make answer validation and Trace depend on observations, not keyword guards

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/chickenbro_observability.py`
- Modify: `server/chickenbro_eval.py`
- Modify: `tests/chickenbro_agent_test.py`
- Modify: `tests/chickenbro_observability_test.py`
- Modify: `tests/chickenbro_eval_test.py`

**Interfaces:**
- Agentic answer schema adds `claimRefs: [{"statement": str, "evidenceRefs": [str]}]`; assistant payload remains unchanged because `claimRefs` is retained only for validation and trace projection.
- Produces Trace v5 `{researchStatus, researchTurnCount, plannedToolIds, observationStatuses, evidenceOutcome}` with no raw prompt, tool arguments, source text, URLs, source bodies or chain-of-thought.
- Leaves v1–v4 trace validation and historical data readable.

- [ ] **Step 1: Write failing generic grounding tests**

```python
def test_agentic_answer_rejects_a_claim_without_returned_observation_ref(self):
    with self.assertRaisesRegex(ValueError, "claim has no returned evidence"):
        backend.validate_chickenbro_model_output(agentic_payload(claim_refs=[]), agentic_context())

def test_agentic_answer_accepts_scope_compatible_returned_claim(self):
    answer = backend.validate_chickenbro_model_output(
        agentic_payload(claim_refs=[{"statement": "样本只覆盖高层大秘境", "evidenceRefs": ["fixture.ref"]}]),
        agentic_context(),
    )
    self.assertEqual("answered", answer["evidenceOutcome"])

def test_trace_v5_projects_only_research_execution_metadata(self):
    trace = build_chickenbro_agent_trace(...)
    self.assertEqual("chickenbro-agent-trace-v5", trace["schemaRevision"])
    self.assertNotIn("玩家原文", json.dumps(trace, ensure_ascii=False))
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `python3 -m unittest tests.chickenbro_agent_test tests.chickenbro_observability_test tests.chickenbro_eval_test -v`

Expected: FAIL because agentic claims and Trace v5 do not yet exist.

- [ ] **Step 3: Implement the generic validator and safe projection**

```python
def validate_agentic_claims(payload, bounded_context):
    observations = bounded_context.get("agenticResearch", {}).get("observations", [])
    returned_refs = {ref for row in observations for ref in row.get("evidenceRefs", [])}
    for claim in payload.get("claimRefs") or []:
        if not set(claim.get("evidenceRefs") or []).intersection(returned_refs):
            raise ValueError("model_output_invalid: claim has no returned evidence")
```

Use this validator only for an active agentic packet and omit `claimRefs` before persisting/sending the assistant payload. The generic path bypasses `chickenbro_authoritative_strength_evidence_result` and the old comparative keyword guards; legacy fallback keeps them. Trace v5 validates fixed enums/counts/tool ids and is produced only from the allowlisted projection.

- [ ] **Step 4: Run the validator, trace and offline eval tests to verify GREEN**

Run: `python3 -m unittest tests.chickenbro_agent_test tests.chickenbro_observability_test tests.chickenbro_eval_test -v`

Expected: agentic responses cite actual observations, over-scoped claims are rejected, legacy trace fixtures remain valid, and no raw content enters v5.

- [ ] **Step 5: Commit grounding and observability**

```bash
git add server/news_backend.py server/chickenbro_observability.py server/chickenbro_eval.py tests/chickenbro_agent_test.py tests/chickenbro_observability_test.py tests/chickenbro_eval_test.py
git commit -m "feat(chickenbro): ground agentic answers in observations"
```

### Task 5: Update the control plane and run the focused release matrix

**Files:**
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Create: `artifacts/releases/2026-08-04-chickenbro-agentic-research-loop/requirement.json`
- Create: `artifacts/releases/2026-08-04-chickenbro-agentic-research-loop/manifest.json`
- Create: `artifacts/releases/2026-08-04-chickenbro-agentic-research-loop/evidence.json`

**Interfaces:**
- Records the exact implementation SHA, test commands/results, candidate service/port, source/tool observations, feature-flag value, rollback command and user acceptance matrix.
- Updates `docs/plans/README.md` so this is the current authorized plan; it must not claim production promotion or user acceptance.

- [ ] **Step 1: Run the focused backend and client matrix**

Run: `python3 -m unittest tests.chickenbro_research_test tests.chickenbro_registry_test tests.chickenbro_tool_runtime_test tests.chickenbro_question_frame_test tests.chickenbro_evidence_plan_test tests.chickenbro_agent_test tests.chickenbro_observability_test tests.chickenbro_eval_test -v && npm run test:taro -- packages/api-client/src/simulator.test.ts packages/design-system/src/components/ChickenbroChatComponents.test.ts apps/mini-taro/src/pages/simulator/simulator-home-dock-contract.test.ts && node scripts/audit-ui-architecture.js`

Expected: all selected tests and the UI architecture audit pass; no broad build or unrelated data-sync action is used as substitute evidence.

- [ ] **Step 2: Build and inspect the candidate package**

Run: `npm run build:weapp && npm run verify:weapp`

Expected: the generated package binds to the current implementation Git SHA and the existing transcript contract remains flexible; this is not real-device acceptance.

- [ ] **Step 3: Create the release packet and update plan status**

Record the literal outputs from Steps 2–3, including any unavailable provider state. Set `manualAcceptance` to `not_run_user_required`; do not claim it is passed.

- [ ] **Step 4: Commit release artifacts and documentation**

```bash
git add docs/plans/README.md docs/roadmap.md artifacts/releases/2026-08-04-chickenbro-agentic-research-loop
git commit -m "docs(chickenbro): record agentic research candidate"
```

### Task 6: Deploy one isolated candidate and hand off factual acceptance

**Files:**
- Modify: no repository source unless a verification failure requires a scoped correction

**Interfaces:**
- Deploys the exact clean candidate SHA to a new `/opt/wow-mini-program-candidates/...` path with a distinct systemd service and local port.
- Candidate runs `WOW_CHICKENBRO_AGENTIC_RESEARCH_ENABLED=1`, does not launch async syncs, and uses the existing configured model/Codex credentials without writing or changing them.
- Rollback is stopping/disabling only the new candidate unit; existing candidate and production remain untouched.

- [ ] **Step 1: Inspect the remote model, Registry and current source readiness**

Run: the repository-owned candidate deploy preflight and read-only remote checks for `WOW_CHICKENBRO_CODEX_ENABLED`, provider configuration presence, active Registry version, current source result status and bound port.

Expected: record literal readiness. If no configured planner exists, stop before enabling the candidate because a silent legacy fallback would not prove the approved agentic path.

- [ ] **Step 2: Deploy the exact candidate identity**

Run: `WOW_DEPLOY_START_ASYNC_SYNCS=0` with the repository-owned deploy script and an explicit candidate service/port/name derived from the commit SHA.

Expected: remote code identity equals local clean HEAD; only the new candidate service restarts.

- [ ] **Step 3: Run direct API smoke cases against that port**

Use a fresh guest/session and assert all of the following from stored HTTP bodies, not stdout alone:

```text
1. A current-strength question yields a terminal response and a v5 trace with research turns/tool ids.
2. A natural-language follow-up produces a new terminal response; it is not rejected by retry/idempotency state.
3. A source failure returns literal partial/unavailable state without "没有抓取能力".
4. An unsupported comparison retains actual missing evidence rather than inventing a rank.
5. A repeated clientMessageId returns its prior message only; a new id reaches a new agent run.
```

- [ ] **Step 4: Build a candidate WeChat package and refresh DevTools**

Run: `npm run refresh:weapp` from the candidate worktree after its frontend/backend identity checks.

Expected: the command reports whether DevTools opened. It never substitutes for a real-device chat acceptance.

- [ ] **Step 5: Update the release evidence and hand off**

Store candidate identity, API/trace smoke output, source status, rollback command and package identity. Mark only server/candidate verification complete. Ask the user to validate: a normal current-source question, an immediate follow-up, a scope-changing question, and transcript scrolling. Do not merge, promote or remove any candidate until that explicit acceptance.
