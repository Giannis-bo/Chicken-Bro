# Equipment Simulator Phase 1 Contracts and Rule Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Use `superpowers:test-driven-development` for every behavior and `superpowers:verification-before-completion` before any completion claim. Do not dispatch subagents unless the user later explicitly requests it.

**Goal:** Establish the approved Selection Intent, Dependency Vector and three-layer signatures, Authority Context, structured Result Envelope, and ordered Rule Matrix as focused Python contracts without activating a Resolver route, changing the frontend, or cutting existing runtime consumers over.

**Architecture:** Add three isolated, importable contract modules. `gear_contracts.py` owns untrusted Intent parsing, exact TypedDict shapes, Dependency Vector validation, Authority Context validation, and signatures. `gear_result_envelope.py` owns problem kinds, deterministic envelopes, and future HTTP semantics. `gear_rule_matrix.py` owns a fixed v1 registry of ten explicit pure evaluator functions that consume only validated Intent and Authority Context. Existing `websim_payload.py`, `gear_legality.py`, routes, frontend state, PostgreSQL selectors, and public read models remain the active runtime behavior until later phases.

**Tech Stack:** Python 3 `TypedDict`, dataclasses, `hashlib`, canonical JSON, `unittest`; existing repo-native Harness v0.5; GitHub PR and candidate deployment.

---

## Phase 1 Boundaries

### Must change

- Create `server/gear_contracts.py`.
- Create `server/gear_result_envelope.py`.
- Create `server/gear_rule_matrix.py`.
- Create focused unit tests for every new branch and error path.
- Record owner, verification, runbook, roadmap, project-state and Strict release evidence.

### Must not change

- Do not add or activate `/api/websim/gear/resolve`.
- Do not import the new contracts into `server/news_backend.py`, `server/websim_payload.py`, `server/postgres_cache_store.py`, or frontend runtime code.
- Do not add PostgreSQL queries, connection arguments, migrations, tables, jobs, Worker units, cache state, or writes.
- Do not implement the Phase 2 canonical Resolver or Evidence Ledger.
- Do not move `gear_legality.py` or existing serializer behavior to the new Rule Matrix yet.
- Do not change `/profile`, `/simulate`, `/gear/stats`, current response shapes, frontend state, or public observed-only semantics.
- Do not implement or enable Phase 6 Catalyst retained-secondary-stat conversion.

### Phase 1 exit

- Contract modules and ordered evaluators are fully characterized and importable.
- Malformed Intent, revision conflict, missing authority, illegal selection, stable signatures, structured problems, and existing facade behavior are proven.
- The candidate deploy proves the modules import and evaluate correctly while all current runtime surfaces remain unchanged.
- The phase is merged, live-smoked and archived before Phase 2 planning begins.

---

## Task 1: Open the Strict Phase 1 contract in a clean worktree

**Files:**

- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/requirement.json`
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/evidence.json`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `tests/project-state.test.js`

- [ ] **Step 1: Create the isolated branch/worktree**

Use branch `codex/equipment-simulator-phase1-contracts-rule-authority` and worktree `.worktrees/equipment-simulator-phase1-contracts-rule-authority` from current `main`. Confirm `main == origin/main` first and preserve `.superpowers/` as untouched untracked residue.

- [ ] **Step 2: Create the Strict packet**

Use:

- slug: `equipment-simulator-phase1-contracts-rule-authority`;
- classification: `Strict`;
- release trigger: `backend_api`;
- status/highest evidence: `implementation_allowed`;
- rollback: `code_rollback`;
- candidate deployment required because new server modules ship to the runtime tree, even though no route consumes them.

The requirement must state the exact must-change and must-not-change boundaries above. The evidence packet must start with branch identity, `commit=uncommitted`, empty runtime evidence, all verification commands as `not_run`, and risks for premature cutover, contract drift, and accidental database coupling.

- [ ] **Step 3: Point current truth at Phase 1**

Set:

```json
{
  "activeMilestone": "equipment_simulator_phase1",
  "activeReleaseArtifact": "artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority"
}
```

Update the active phase contract status to `phase1_contracts_in_progress`; add a newest roadmap paragraph stating that Phase 1 is contract-only and does not activate Resolver/API/frontend behavior. Update the project-state test fixture.

- [ ] **Step 4: Generate and validate the initial manifest**

```bash
node scripts/project-harness.js --json --write \
  --date 2026-07-10 \
  --slug equipment-simulator-phase1-contracts-rule-authority \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/evidence.json
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/evidence.json \
  --base origin/main
node --test tests/project-state.test.js
```

Expected: packet passes at `implementation_allowed`; no runtime file has changed.

---

## Task 2: Define Selection Intent, Dependency Vector, Authority Context and signatures

**Files:**

- Create: `server/gear_contracts.py`
- Create: `tests/gear_contracts_test.py`

**Interfaces:**

```python
parse_selection_intent(raw_intent) -> tuple[dict | None, list[dict]]
validate_dependency_vector(vector) -> list[dict]
validate_authority_context(intent, authority_context) -> list[dict]
selection_signature(intent, eligibility_context) -> str
resolved_gear_signature(selection_signature_value, dependency_vector) -> str
profile_signature(
    resolved_signature,
    character_context,
    talent_hash,
    serializer_revision,
    simc_runtime_revision,
    stat_policy_revision,
) -> str
```

- [ ] **Step 1: Write the Intent contract red tests**

Add tests:

```python
test_selection_intent_parser_returns_exact_canonical_v1_shape
test_selection_intent_parser_rejects_malformed_or_unknown_slots
test_selection_intent_parser_rejects_client_final_facts
```

The valid fixture must use the approved fields only:

```python
{
    "schemaRevision": "selection-intent-v1",
    "authoredAgainst": {
        "seasonRevision": "season-17-active",
        "gearCatalogRevision": "gear-r17",
    },
    "eligibilityContext": {
        "classKey": "mage",
        "specKey": "arcane",
        "level": 90,
    },
    "slots": {
        "head": {
            "itemId": "250060",
            "variantKey": "variant-head-289",
            "gemOptionIds": ["gem-240898-r2"],
            "enchantOptionId": "",
            "embellishmentOptionId": "",
            "craftedOptionId": "",
            "catalystOptionId": "",
        }
    },
}
```

Forbidden client facts include `itemSetId`, `stats`, `simcOptions`, `legality`, `readiness`, `evidence`, and `claims` at the root or slot level. Expected red: module missing.

- [ ] **Step 2: Implement exact TypedDict shapes and canonical parsing**

Define `EligibilityContext`, `AuthoredAgainst`, `SlotSelection`, `SelectionIntent`, `DependencyVector`, `AuthorityItem`, and `AuthorityContext` TypedDicts plus revision constants:

```python
SELECTION_INTENT_SCHEMA_REVISION = "selection-intent-v1"
DEPENDENCY_VECTOR_CONTRACT_REVISION = "gear-dependency-vector-v1"
AUTHORITY_CONTEXT_CONTRACT_REVISION = "gear-authority-context-v1"
RESOLVER_CONTRACT_REVISION = "gear-resolver-contract-v1"
```

`parse_selection_intent` must:

- reject non-object input, wrong schema revision, missing authored revisions, missing/invalid class/spec/level, unknown/non-object slots, missing item IDs, invalid option-list types, and all forbidden final-fact keys;
- normalize all IDs to bounded strings and level to an integer;
- return only approved keys;
- preserve `gemOptionIds` order because it represents socket order;
- order slot maps by the fixed canonical slot order for deterministic snapshots;
- return `INVALID_INTENT` contract issues without raising for user input.

- [ ] **Step 3: Write Dependency Vector and signature red tests**

Add:

```python
test_dependency_vector_requires_every_approved_revision
test_selection_signature_is_order_stable_and_eligibility_sensitive
test_resolved_signature_uses_resolution_dependencies_not_profile_dependencies
test_profile_signature_changes_for_character_talent_serializer_runtime_or_stat_policy
```

Use exact Dependency Vector fields:

```text
seasonRevision
gearCatalogReleaseId
gearCatalogRevision
gearRuleRevision
resolverContractRevision
serializerRevision
simcRuntimeRevision
statPolicyRevision
selectionSchemaRevision
```

Community-only origin fields remain optional:

```text
communityTemplateReleaseId
communityTemplateRevision
templateOriginSignature
validatedAgainstGearReleaseId
```

- [ ] **Step 4: Implement canonical SHA-256 signatures**

Use UTF-8 canonical JSON with sorted object keys and compact separators; return `sha256:<hex>`.

`selection_signature` signs canonical Intent plus the explicit eligibility context and selection schema revision.

`resolved_gear_signature` signs the selection signature plus only:

```text
seasonRevision
gearCatalogReleaseId
gearCatalogRevision
gearRuleRevision
resolverContractRevision
selectionSchemaRevision
```

It must not change for serializer/SimC/stat policy changes.

`profile_signature` signs the resolved signature, canonical character context, talent hash, serializer revision, SimC runtime revision and stat policy revision.

- [ ] **Step 5: Write and implement Authority Context validation**

Add red tests:

```python
test_authority_context_missing_required_maps_is_unavailable
test_authority_context_revision_conflict_is_not_silently_reinterpreted
test_authority_context_contract_has_no_connection_or_database_access
```

The exact context shape is:

```python
{
    "contractRevision": "gear-authority-context-v1",
    "manifest": {
        "seasonRevision": "season-17-active",
        "gearCatalogReleaseId": "gear-release-17",
        "gearCatalogRevision": "gear-r17",
    },
    "dependencyVector": {...},
    "itemsById": {},
    "variantsByKey": {},
    "optionsById": {},
    "ruleParameters": {},
    "capabilities": {},
    "evidenceRecordsById": {},
    "missingFields": [],
}
```

Missing maps or non-empty `missingFields` produce `AUTHORITY_UNAVAILABLE`. Authored/current season or gear revision mismatch produces `REVISION_CONFLICT`. The module must not import `sqlite3`, PostgreSQL/store modules, or accept `conn` in any public signature.

- [ ] **Step 6: Run the focused contract suite**

```bash
python3 -m unittest tests.gear_contracts_test
```

Expected: all contract branches green.

---

## Task 3: Define structured problems and Result Envelope semantics

**Files:**

- Create: `server/gear_result_envelope.py`
- Create: `tests/gear_result_envelope_test.py`

**Interfaces:**

```python
gear_problem(kind, code, title, *, detail="", path="", retryable=False, meta=None) -> dict
result_envelope(status, request_id, release_context, *, data=None, problems=None) -> dict
http_status_for_envelope(envelope) -> int
```

- [ ] **Step 1: Add the envelope red tests**

```python
test_result_envelope_has_exact_contract_shape
test_problem_kind_allowlist_rejects_unknown_kind
test_http_semantics_preserve_blocked_pending_conflict_and_unavailable
test_problem_order_and_meta_are_deterministic
```

Allowed problem kinds are exactly:

```text
INVALID_INTENT
ILLEGAL_SELECTION
REVISION_CONFLICT
AUTHORITY_UNAVAILABLE
SIMC_UNAVAILABLE
INTERNAL_ERROR
```

- [ ] **Step 2: Implement the module**

Envelope shape:

```python
{
    "contractRevision": "gear-result-envelope-v1",
    "requestId": "...",
    "status": "resolved|blocked|pending|unavailable",
    "releaseContext": {},
    "data": {},
    "problems": [],
}
```

HTTP mapping for future route use:

- `resolved` or domain `blocked`/`ILLEGAL_SELECTION` -> 200;
- `pending` -> 202;
- `INVALID_INTENT` -> 400;
- `REVISION_CONFLICT` -> 409;
- `AUTHORITY_UNAVAILABLE` or `SIMC_UNAVAILABLE` -> 503;
- `INTERNAL_ERROR` -> 500.

No route imports this module in Phase 1.

- [ ] **Step 3: Run green**

```bash
python3 -m unittest tests.gear_result_envelope_test
```

---

## Task 4: Build the fixed ordered Rule Matrix

**Files:**

- Create: `server/gear_rule_matrix.py`
- Create: `tests/gear_rule_matrix_test.py`

**Interfaces:**

```python
RULE_MATRIX_REVISION = "gear-rule-matrix-v1"
ordered_rule_matrix() -> tuple[RuleDefinition, ...]
evaluate_rule_matrix(selection_intent, authority_context) -> dict
```

- [ ] **Step 1: Add registry red tests**

```python
test_rule_matrix_registers_ten_rules_in_approved_order
test_every_rule_has_revision_scope_parameters_sources_code_and_explicit_evaluator
test_rule_matrix_revision_is_deterministic
```

Registry order and IDs:

| Order | Rule ID | Deterministic blocker prefix |
| --- | --- | --- |
| 10 | `season_release_identity` | `GEAR_RELEASE_` |
| 20 | `slot_inventory_type` | `GEAR_SLOT_` |
| 30 | `class_spec_armor_weapon` | `GEAR_ELIGIBILITY_` |
| 40 | `weapon_hand_configuration` | `GEAR_HAND_` |
| 50 | `unique_equipped` | `GEAR_UNIQUE_` |
| 60 | `socket_and_gem` | `GEAR_GEM_` |
| 70 | `enchant_and_runeforge` | `GEAR_ENCHANT_` |
| 80 | `embellishment_and_crafted` | `GEAR_CRAFT_` |
| 90 | `catalyst_tier_overlay` | `GEAR_CATALYST_` |
| 100 | `cross_slot_set_aggregate` | `GEAR_AGGREGATE_` |

Use a frozen `RuleDefinition` dataclass containing `rule_id`, `rule_revision`, `order`, `scope`, `parameters`, `authority_source_refs`, `blocker_code`, and a named evaluator callable. Do not build a DSL.

- [ ] **Step 2: Add authority and illegal-selection red tests**

```python
test_rule_matrix_missing_authority_fails_before_selection_rules
test_rule_matrix_blocks_item_in_wrong_slot_with_stable_code
test_rule_matrix_blocks_class_spec_armor_or_weapon_mismatch
test_rule_matrix_blocks_two_hand_offhand_and_unique_limit_conflicts
test_rule_matrix_blocks_unknown_gem_enchant_embellishment_or_crafted_options
test_rule_matrix_keeps_catalyst_blocked_without_verified_capability
test_rule_matrix_returns_all_ordered_results_without_resolving_attributes
```

Authority fixture item/option facts must be server-shaped, not client options. Each evaluation result is:

```python
{
    "ruleId": "...",
    "ruleRevision": "gear-rule-matrix-v1",
    "status": "verified|blocked",
    "problems": [],
}
```

- [ ] **Step 3: Implement ten explicit pure evaluators**

Evaluators may read only parsed Intent and supplied Authority Context. They must not import stores, database modules, `websim_payload.py`, or call current facade helpers.

Implement these Phase 1 checks:

1. authored/current release identity and item/variant presence;
2. authoritative allowed slots/inventory types;
3. authoritative allowed class/spec, armor and weapon types;
4. two-hand/off-hand and dual-wield parameters;
5. item/unique-group counts and limits;
6. socket capacity, allowed gem option IDs and unique gem limits;
7. allowed enchant IDs plus runeforge-only parameters;
8. allowed embellishment/crafted option IDs and whole-character embellishment limit;
9. any Catalyst selection requires `capabilities.catalyst.enabled=true`, matching revision and allowed option;
10. supplied authoritative cross-slot/set blocker facts and set aggregation inputs.

Do not generate resolved instances, attributes, itemSetId, Evidence Claims, SimC lines, or readiness; those are Phase 2.

- [ ] **Step 4: Run green and prove zero DB coupling**

```bash
python3 -m unittest tests.gear_rule_matrix_test
rg -n "sqlite3|psycopg|postgres|db_connection|conn" \
  server/gear_contracts.py server/gear_result_envelope.py server/gear_rule_matrix.py
```

Expected: tests pass; the search returns no database coupling or connection parameters.

---

## Task 5: Characterize the unchanged facade and register ownership

**Files:**

- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Modify: `docs/plans/README.md`

- [ ] **Step 1: Register future contract ownership without runtime cutover**

Add the new modules and tests to the existing gear public read-model and SimC pipeline characterization as contract foundations. Keep current fact owners and runtime surfaces unchanged; explicitly state that Phase 1 modules are not active consumers yet. Do not add a seventeenth critical domain.

Add new changed-path coverage for:

```text
server/gear_contracts.py
server/gear_result_envelope.py
server/gear_rule_matrix.py
tests/gear_contracts_test.py
tests/gear_result_envelope_test.py
tests/gear_rule_matrix_test.py
```

- [ ] **Step 2: Characterize the current facade**

Run existing facade and Phase 0 regressions without changing production files:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_gear_serializer_matches_compact_golden_payload \
  tests.websim_payload_test.WebSimPayloadTest.test_pg_only_structured_enhancement_rejects_client_catalog_forgery \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_simulate_runs_encoded_profile_through_fake_simc \
  tests.news_backend_test.NewsBackendTest.test_catalyst_overlay_allowlist_does_not_prove_cutover_capability
```

Expected: unchanged facade behavior passes.

- [ ] **Step 3: Document the dormant boundary**

Verification matrix and runbook must state:

- the modules are contract-only and unconsumed in Phase 1;
- Selection Intent final facts are rejected;
- signatures declare their dependency subsets;
- Result Envelope HTTP mapping is dormant until Phase 3;
- Rule Matrix is pure and ordered but does not yet produce a Resolved Snapshot;
- current facade, frontend, PostgreSQL selectors and public read model remain active.

Register this detailed plan in `docs/plans/README.md`.

---

## Task 6: Complete local verification, PR, candidate deploy and archive

**Files:**

- Modify: `artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/evidence.json`
- Create/refresh: `artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority/manifest.json`
- Modify after merge: `docs/project-state.json`, `docs/roadmap.md`, `docs/plans/README.md`

- [ ] **Step 1: Run complete local verification**

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority \
  --base origin/main
python3 -m py_compile \
  server/gear_contracts.py \
  server/gear_result_envelope.py \
  server/gear_rule_matrix.py \
  tests/gear_contracts_test.py \
  tests/gear_result_envelope_test.py \
  tests/gear_rule_matrix_test.py
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

- [ ] **Step 2: Perform local CR**

Confirm:

- all new modules are pure and no public function accepts a connection;
- signature dependency subsets match the approved design;
- client final facts never enter canonical Intent;
- Rule Matrix uses explicit functions in fixed order and is not a DSL;
- no new route, runtime import, frontend file, database/store, migration, job, Worker, sync/write/backfill/cleanup or Phase 6 activation exists;
- current Phase 0 and public observed-only contracts remain green.

- [ ] **Step 3: Promote local evidence and commit**

Update evidence with TDD red/green results, focused/full counts, zero-DB search, facade characterization and local CR. Regenerate/check the manifest. Commit:

```bash
git commit -m "feat: define gear resolution contracts"
```

Push and open a ready PR.

- [ ] **Step 4: Candidate-deploy the exact PR head**

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 \
WOW_DEPLOY_START_ASYNC_SYNCS=0 \
./server/deploy_lighthouse.sh
```

Candidate smoke must record:

- branch, PR head, hashes for all three new modules, active service, and `WOW_DATABASE_RUNTIME=postgres_only`;
- remote import of the three modules;
- a live pure probe producing stable selection/resolved/profile signatures;
- a live envelope probe for 200 blocked, 409 conflict and 503 authority unavailable;
- a live Rule Matrix fixture proving wrong-slot `ILLEGAL_SELECTION` and Catalyst fail-closed codes;
- `POST /api/websim/gear/resolve` remains absent/404;
- existing `/health`, `/api/data/health`, Phase 0A forged enhancement, Phase 0B Catalyst, Phase 0C legacy stats/flavor/concurrency, public initial/slot, and 40-spec observed-only sweep remain unchanged;
- relevant services/timers are inactive or truthful, async sync was not started, recent error/SQLite-fallback scan is zero;
- rollback is redeploy of the previous main commit; no database restore.

- [ ] **Step 5: Merge, post-merge smoke and archive**

Merge only after candidate and GitHub Harness pass. Fast-forward main, prove `HEAD == origin/main`, repeat the live module probes and current runtime smokes, set the release evidence to `archived`, and update current truth to `equipment_simulator_phase2` / Phase 2 planning. Then create the Phase 2 detailed plan with `superpowers:writing-plans`; do not mark the Goal complete.

---

## Phase 1 Self-Review Checklist

- [ ] Every approved Phase 1 deliverable maps to a module and focused test.
- [ ] Selection Intent is the only input model and rejects final client facts.
- [ ] Dependency Vector and three signatures expose exact dependency boundaries.
- [ ] Authority Context is a pure contract with no database access.
- [ ] All ten Rule Matrix entries use explicit ordered evaluators, not a DSL.
- [ ] Result Envelope and problem kinds are defined without activating a route.
- [ ] Missing authority, revision conflict, malformed Intent and illegal selection are characterized.
- [ ] Existing facade and Phase 0 behavior remain unchanged.
- [ ] Candidate deployment proves import/runtime-tree compatibility without runtime cutover.
- [ ] Phase 6 Catalyst remains disabled/TODO.
