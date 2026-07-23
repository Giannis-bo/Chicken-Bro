# Observed Build Registry Shared-Player Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one immutable 80-slot Raider.IO player set serve both talent and gear simulation, with one importable talent template per class/spec/Hero and two distinct importable gear templates per class/spec.

**Architecture:** The existing dormant snapshot, projection, TemplateSet, and PostgreSQL pointer core remains the authority. A bounded Raider.IO adapter creates immutable snapshots, a compiler maps each snapshot through current talent and gear authorities, and one active TemplateSet deterministically feeds the existing talent, gear, and exact-import contracts. Candidate and retail use separate pointer scopes, so WeChat DevTools can verify the candidate through an SSH tunnel without changing the production reader.

**Tech Stack:** Python 3 standard library, PostgreSQL/psycopg, existing Raider.IO collector, existing talent authority and canonical gear Resolver, Taro/React/TypeScript, Vitest, Node repository verification scripts, systemd, WeChat DevTools CLI.

## Global Constraints

- The only player fact set contains exactly 80 class/spec/Hero/scenario slots: 40 specs times two Hero slots.
- Talent and gear for one slot must share one `snapshotId` and one `sourceIdentity`; a slot is never half-updated.
- The two Hero slots in one class/spec must use distinct Raider.IO `sourceIdentity` values.
- The initial public cutover requires 80 verified, importable slots; `pending_collection` blocks activation.
- After initial cutover, a blocked new winner retains the same-slot last-known-good talent and gear together; other slots may update.
- No baseline, default, cross-Hero, cross-spec, anonymous, WCL, or optimizer record may fill an observed-player slot.
- Existing `/api/websim/talents`, `/api/websim/gear`, `/api/websim/gear/community-import`, and talent import-code contracts remain the frontend integration surface.
- Read APIs and health remain read-only and perform no network calls, projection compilation, pointer writes, or SimulationCraft execution.
- Daily observed refresh performs serializer/profile readiness only; it does not run full combat SimulationCraft.
- Candidate code uses pointer scope `candidate`; production uses pointer scope `retail`.
- The first controlled cloud collection through the existing Raider.IO collector is explicitly approved in the 2026-07-23 design confirmation.
- Do not modify or discard unrelated changes in `/Users/boyuan/Documents/wow_mini_program`; implementation remains isolated until Harness integration.

---

## File Structure

### Core contracts

- Modify `server/observed_build_projection.py`: bind `sourceIdentity` into projection identity and integrity validation.
- Modify `server/observed_build_template_set.py`: carry source identity into entries, reject duplicate same-spec players, and block incomplete activation.
- Modify `server/observed_build_store.py`: add validated read methods for pointer, active records, exact projection, and latest verified staging records.
- Modify `server/migrations/postgres/0018_observed_build_registry.sql`: persist indexed source identity on projection and TemplateSet slot rows before migration reaches production.

### Source and compilation

- Create `server/observed_build_ingest.py`: convert Raider.IO community candidates plus exact profiles into deterministic per-slot snapshot candidates and choose distinct same-spec winners.
- Create `server/observed_build_compiler.py`: adapt snapshots to current talent authority, gear authority, canonical Resolver, and serializer readiness without running combat SimC.
- Create `server/observed_build_sync.py`: orchestrate source refresh, snapshot/check sealing, projection compilation, TemplateSet sealing, promotion policy, sync state, and CLI modes.

### Public read path

- Create `server/observed_build_read_model.py`: project active records into the existing talent and gear public template shapes.
- Modify `server/postgres_cache_store.py`: delegate active observed reads and exact gear imports to `ObservedBuildStore`, falling back to the legacy reader only while the configured scope has no active pointer.
- Modify `server/news_backend.py`: expose bounded observed-registry health inside the existing data-health payload.

### Scheduled operation and client contract

- Modify `server/wow-community-template-sync.service`: run the new observed-build sync after candidate verification; keep the old Python entrypoint available for code rollback.
- Modify `packages/domain/src/entities.ts`: carry TemplateSet and snapshot provenance through the client type.
- Modify `packages/api-client/src/websim.ts`: normalize the new provenance fields.
- Modify existing gear/talent model tests; the mounted pages keep their current import interaction.
- Create `scripts/audit-observed-build-cutover.py`: exhaustively audit 80 talent reads/import codes, 40 gear reads with two distinct players, and 80 exact gear imports.

### Tests and Harness evidence

- Create `tests/observed_build_ingest_test.py`.
- Create `tests/observed_build_compiler_test.py`.
- Create `tests/observed_build_read_model_test.py`.
- Create `tests/observed_build_sync_test.py`.
- Modify the existing observed-build core/store/projection/TemplateSet tests.
- Create the single task packet `artifacts/releases/2026-07-23-observed-build-registry-cutover/`.

---

### Task 0: Land the dormant core foundation cleanly

**Files:**
- Modify: `packages/design-system/src/components/TalentSimulatorComponents.module.scss:345-352`
- Modify: `artifacts/releases/2026-07-23-observed-build-registry-core/evidence.json`
- Modify: `artifacts/releases/2026-07-23-observed-build-registry-core/manifest.json`
- Modify: `docs/project-state.json`

**Interfaces:**
- Consumes: draft PR `#98`, branch `codex/observed-build-registry-core`, dormant migration/core evidence.
- Produces: merged dormant registry foundation on `origin/main`, with no active TemplateSet pointer and no public reader change.

- [x] **Step 1: Reproduce the only current full-profile blocker**

Run:

```bash
node scripts/audit-ui-architecture.js
```

Expected: FAIL only at `component_native_buttons_cannot_disable_shared_width_clamping`, naming `TalentSimulatorComponents.module.scss`.

- [x] **Step 2: Remove the unbounded component width exemption**

Replace the only component `max-width: none` escape with the image's explicit three-panel geometry:

```scss
.graphArtworkImage {
  width: 300%;
  max-width: 300%;
}
```

This preserves the talent artwork's three-panel crop without allowing the broad `none` exemption. The shared `.nativeControl { max-width: 100%; }` button owner remains authoritative.

- [x] **Step 3: Verify the targeted audit and dormant core**

Run:

```bash
node scripts/audit-ui-architecture.js
python3 -m unittest \
  tests.observed_build_characterization_test \
  tests.observed_build_registry_test \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test \
  tests.observed_build_store_test \
  tests.observed_build_core_path_test \
  tests.postgres_schema_test
```

Expected: both commands PASS; core tests report no network, legacy release, or active-reader dependency.

- [x] **Step 4: Commit the baseline audit correction**

```bash
git add packages/design-system/src/components/TalentSimulatorComponents.module.scss
git commit -m "fix(ui): retain native button width clamp"
```

- [x] **Step 5: Refresh exact-head Harness evidence**

Run the full profile against the one existing packet:

```bash
node scripts/verify-project.js \
  --profile full \
  --release artifacts/releases/2026-07-23-observed-build-registry-core \
  --base origin/main
```

Expected: PASS. Record the exact verification commit/tree in `evidence.json`; keep the previously proven candidate runtime identity only if the runtime tree hash is unchanged, otherwise rerun the disposable PostgreSQL candidate smoke and bind the new exact runtime identity.

- [x] **Step 6: Commit evidence and merge PR #98**

```bash
git add \
  artifacts/releases/2026-07-23-observed-build-registry-core/evidence.json \
  artifacts/releases/2026-07-23-observed-build-registry-core/manifest.json \
  docs/project-state.json
git commit -m "chore(harness): close observed registry core evidence"
git push origin codex/observed-build-registry-core
gh pr ready 98
gh pr checks 98 --watch
gh pr merge 98 --merge
```

Expected: all required checks PASS and PR #98 merges without force push. Production tables and the `retail` pointer remain untouched.

- [x] **Step 7: Rebase execution state onto the merged foundation**

After PR #98 is merged:

```bash
git fetch origin
git switch -c codex/observed-build-registry-cutover origin/main
git merge-base --is-ancestor origin/main HEAD
git status --short --branch
```

Expected: the same isolated worktree is now on `codex/observed-build-registry-cutover`, based exactly on the merged `origin/main`, with a clean working tree before Task 1. Do not reuse or rewrite the merged core branch.

---

### Task 1: Bind source identity and enforce activation gates

**Files:**
- Modify: `server/observed_build_projection.py`
- Modify: `server/observed_build_template_set.py`
- Modify: `server/observed_build_store.py`
- Modify: `server/migrations/postgres/0018_observed_build_registry.sql`
- Test: `tests/observed_build_projection_test.py`
- Test: `tests/observed_build_template_set_test.py`
- Test: `tests/observed_build_store_test.py`
- Test: `tests/postgres_schema_test.py`

**Interfaces:**
- Consumes: `build_observed_snapshot(...) -> dict`, `build_projection(...) -> dict`, `build_template_set(...) -> dict`.
- Produces: projection and entry field `sourceIdentity: str`; `promotion_decision(...)` blocks pending initial or later candidates; schema columns `source_identity`.

- [x] **Step 1: Write failing source-identity and activation tests**

Add assertions equivalent to:

```python
def test_projection_binds_snapshot_source_identity(self):
    projection = self.verified_projection()
    self.assertEqual(
        projection["sourceIdentity"],
        self.snapshot()["source"]["sourceIdentity"],
    )

def test_initial_activation_rejects_pending_slot(self):
    candidates = self.verified_candidates(player_prefix="first")
    candidates.pop(slot_key(self.slot_a()))
    candidate = build_template_set(
        expected_slots=self.slots(),
        candidates_by_slot=candidates,
        active_set=None,
        dependency_vector=self.dependencies(),
        source_run_id="run-first",
    )
    decision = promotion_decision(active_set=None, candidate_set=candidate)
    self.assertEqual(decision["action"], "blocked")
    self.assertEqual(decision["reason"], "initial_coverage_incomplete")

def test_same_spec_hero_slots_require_distinct_players(self):
    slots = self.slots()
    same_spec = [
        slot for slot in slots
        if slot["classKey"] == slots[0]["classKey"]
        and slot["specKey"] == slots[0]["specKey"]
    ]
    candidates = self.verified_candidates(player_prefix="unique")
    first = self.projection(same_spec[0], "duplicate-player")
    second = self.projection(same_spec[1], "duplicate-player")
    candidates[slot_key(same_spec[0])] = first
    candidates[slot_key(same_spec[1])] = second
    with self.assertRaisesRegex(ValueError, "distinct sourceIdentity"):
        build_template_set(
            expected_slots=slots,
            candidates_by_slot=candidates,
            active_set=None,
            dependency_vector=self.dependencies(),
            source_run_id="run-duplicate",
        )
```

- [x] **Step 2: Run the tests and confirm the contract is absent**

```bash
python3 -m unittest \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test \
  tests.observed_build_store_test \
  tests.postgres_schema_test
```

Expected: FAIL because projections/entries do not expose `sourceIdentity`, duplicate same-spec identities are accepted, and incomplete first activation returns `controlled_cutover`.

- [x] **Step 3: Bind source identity into immutable projection content**

Add `sourceIdentity` to `_identity_payload`, `build_projection`, and `validate_projection`:

```python
source_identity = _text(
    (snapshot.get("source") or {}).get("sourceIdentity")
)
if not source_identity.startswith("raiderio:"):
    raise ValueError("snapshot sourceIdentity must be a Raider.IO identity")

projection = {
    "schemaRevision": OBSERVED_BUILD_PROJECTION_SCHEMA_REVISION,
    "projectionId": "",
    "snapshotId": snapshot["snapshotId"],
    "sourceIdentity": source_identity,
    "slot": _canonical(snapshot["slot"]),
    "slotKey": slot_key(snapshot["slot"]),
    "dependencyHash": _sha256(normalized_dependencies),
    "dependencyVector": normalized_dependencies,
    "talentProjection": normalized_talent,
    "gearProjection": normalized_gear,
    "profileReadiness": normalized_readiness,
    "status": "verified" if ready else "blocked",
    "importable": ready,
    "problems": normalized_problems,
}
```

- [x] **Step 4: Carry and validate identity in TemplateSet entries**

Verified and LKG entries carry `sourceIdentity`; pending entries carry an empty string. Add a spec-pair check:

```python
def _distinct_spec_player_issues(entries):
    identities_by_spec = {}
    issues = []
    for index, entry in enumerate(entries):
        if entry.get("status") not in {"verified", "stale_lkg"}:
            continue
        slot = entry.get("slot") if isinstance(entry.get("slot"), dict) else {}
        spec_id = f"{_text(slot.get('classKey'))}:{_text(slot.get('specKey'))}"
        source_identity = _text(entry.get("sourceIdentity"))
        prior = identities_by_spec.setdefault(spec_id, set())
        if source_identity in prior:
            issues.append(_issue(
                "TEMPLATE_SET_SPEC_PLAYER_DUPLICATE",
                f"templateSet.entries[{index}].sourceIdentity",
                f"{spec_id} Hero slots require distinct sourceIdentity values.",
            ))
        prior.add(source_identity)
    return issues
```

`validate_template_set` appends these issues. `build_template_set` raises on them.

- [x] **Step 5: Block incomplete activation**

Implement the exact promotion rule:

```python
counts = candidate_set.get("counts") or {}
if int(counts.get("pending_collection") or 0) > 0:
    return {
        "action": "blocked",
        "reason": (
            "initial_coverage_incomplete"
            if active_set is None
            else "active_candidate_incomplete"
        ),
        "problems": [{
            "code": "template_set_pending_collection",
            "stage": "promotion",
            "count": int(counts.get("pending_collection") or 0),
        }],
    }
```

An initial set must also have `verified == 80` and `stale_lkg == 0`; an existing active set may promote `verified + stale_lkg == 80`.

- [x] **Step 6: Persist source identity**

Add `source_identity text NOT NULL` to `cache.observed_build_projections` and nullable `source_identity text` to `cache.observed_build_template_set_slots`, with a check requiring it for `verified/stale_lkg` and forbidding it for pending rows. Update `seal_projection`, `seal_template_set`, fake SQL responders, and schema assertions to use these columns.

- [x] **Step 7: Run tests and commit**

```bash
python3 -m unittest \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test \
  tests.observed_build_store_test \
  tests.postgres_schema_test
git add \
  server/observed_build_projection.py \
  server/observed_build_template_set.py \
  server/observed_build_store.py \
  server/migrations/postgres/0018_observed_build_registry.sql \
  tests/observed_build_projection_test.py \
  tests/observed_build_template_set_test.py \
  tests/observed_build_store_test.py \
  tests/postgres_schema_test.py
git commit -m "feat(builds): enforce shared observed player slots"
```

Expected: PASS; commit contains no reader, collector, or SimC runtime change.

---

### Task 2: Convert Raider.IO payloads into 80 deterministic snapshot candidates

**Files:**
- Create: `server/observed_build_ingest.py`
- Create: `tests/observed_build_ingest_test.py`

**Interfaces:**
- Consumes: Raider.IO payload keys `communityTemplates`, `profiles`, `checkedAt`, `seasonSlug`; existing `expected_hero_tree_triplets()`.
- Produces: `snapshot_candidates_from_raiderio(payload) -> {"candidatesBySlot": dict[str, list[dict]], "problemsBySlot": dict[str, list[dict]]}` and `select_distinct_snapshot_winners(candidates_by_slot) -> dict[str, dict]`.

- [x] **Step 1: Write failing fixture tests**

Use two Mage/Frost Hero candidates plus one exact profile each:

```python
def test_builds_snapshot_candidates_from_exact_template_and_profile(self):
    result = snapshot_candidates_from_raiderio(self.payload())
    slot = "mage:frost:frostfire:mythic_plus"
    snapshot = result["candidatesBySlot"][slot][0]
    self.assertEqual(snapshot["source"]["sourceIdentity"], "raiderio:cn|realm-a|player-a")
    self.assertEqual(snapshot["talentObservation"]["rawImportCode"], "C4DA")
    self.assertEqual(snapshot["gearObservation"]["gearItems"][0]["itemId"], "230001")

def test_selects_distinct_players_for_two_hero_slots(self):
    candidates = self.candidates_where_top_player_appears_in_both_heroes()
    winners = select_distinct_snapshot_winners(candidates)
    identities = {
        snapshot["source"]["sourceIdentity"]
        for snapshot in winners.values()
    }
    self.assertEqual(len(winners), 2)
    self.assertEqual(len(identities), 2)

def test_missing_exact_gear_profile_is_a_problem_not_a_snapshot(self):
    payload = self.payload()
    payload["profiles"] = []
    result = snapshot_candidates_from_raiderio(payload)
    self.assertEqual(result["candidatesBySlot"], {})
    self.assertEqual(
        result["problemsBySlot"]["mage:frost:frostfire:mythic_plus"][0]["code"],
        "exact_profile_gear_missing",
    )
```

- [x] **Step 2: Run the new test and verify it fails**

```bash
python3 -m unittest tests.observed_build_ingest_test
```

Expected: FAIL with `ModuleNotFoundError: server.observed_build_ingest`.

- [x] **Step 3: Implement bounded extraction**

Create exact public functions:

```python
def snapshot_candidates_from_raiderio(payload: dict[str, Any]) -> dict[str, Any]:
    """Build real snapshot candidates; never invent or cross-fill a slot."""

def select_distinct_snapshot_winners(
    candidates_by_slot: Mapping[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Choose the highest deterministic distinct-identity pair per spec."""
```

Extraction rules:

- accept only templates whose `sourceKey` is absent or `raiderio`;
- require canonical class/spec/Hero and `scenarioKey == "mythic_plus"`;
- require nested `payload.raiderio.sourceIdentity`, profile URL, player, realm, region, raw/structured talent observation, and a matching profile with usable `gear`;
- build snapshots only with `build_observed_snapshot`;
- sort candidates by descending Raider.IO score, ascending positive rank, descending key level, then `sourceIdentity` and `snapshotId`;
- for each spec, enumerate the two Hero candidate lists and choose the highest combined pair whose identities differ;
- emit `distinct_spec_player_missing` when no valid pair exists;
- never reuse another Hero/spec profile.

- [x] **Step 4: Verify deterministic and fail-closed behavior**

```bash
python3 -m unittest tests.observed_build_ingest_test
```

Expected: PASS for stable input ordering, duplicate identity avoidance, and missing-profile problems.

- [x] **Step 5: Commit**

```bash
git add server/observed_build_ingest.py tests/observed_build_ingest_test.py
git commit -m "feat(builds): ingest observed Raider.IO snapshots"
```

---

### Task 3: Compile one snapshot through current talent and gear authorities

**Files:**
- Create: `server/observed_build_compiler.py`
- Create: `tests/observed_build_compiler_test.py`

**Interfaces:**
- Consumes: immutable snapshot, dependency vector, injected `talent_compiler(snapshot)` and `gear_compiler(snapshot)` adapters.
- Produces: `compile_observed_build(snapshot, dependency_vector, talent_compiler, gear_compiler) -> dict` returning one verified or blocked `build_projection`.
- Produces: `compile_with_postgres(store, snapshot, dependency_vector, simc_runtime_revision) -> dict`.

- [x] **Step 1: Write failing combined-slot tests**

```python
def test_both_authorities_must_pass_for_one_importable_projection(self):
    projection = compile_observed_build(
        self.snapshot(),
        self.dependencies(),
        talent_compiler=lambda snapshot: {
            "status": "verified",
            "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
            "websimExportCode": "websim:encoded",
        },
        gear_compiler=lambda snapshot: {
            "status": "verified",
            "selectionIntent": {"schemaRevision": "selection-intent-v1", "slots": {}},
            "resolvedGearSignature": "sha256:" + "2" * 64,
        },
    )
    self.assertTrue(projection["importable"])

def test_gear_failure_blocks_talent_switch_in_the_same_projection(self):
    projection = compile_observed_build(
        self.snapshot(),
        self.dependencies(),
        talent_compiler=lambda snapshot: {"status": "verified"},
        gear_compiler=lambda snapshot: {
            "status": "blocked",
            "problems": [{"code": "gear_item_unmapped", "stage": "gear"}],
        },
    )
    self.assertEqual(projection["status"], "blocked")
    self.assertEqual(projection["problems"][0]["code"], "gear_item_unmapped")
```

- [x] **Step 2: Run the new tests and verify they fail**

```bash
python3 -m unittest tests.observed_build_compiler_test
```

Expected: FAIL because the compiler module does not exist.

- [x] **Step 3: Implement the pure combined compiler**

```python
def compile_observed_build(
    snapshot,
    dependency_vector,
    talent_compiler,
    gear_compiler,
):
    talent = talent_compiler(snapshot)
    gear = gear_compiler(snapshot)
    problems = [
        problem
        for section in (talent, gear)
        for problem in section.get("problems", [])
        if isinstance(problem, dict)
    ]
    ready = talent.get("status") == "verified" and gear.get("status") == "verified"
    return build_projection(
        snapshot=snapshot,
        dependency_vector=dependency_vector,
        talent_projection=talent,
        gear_projection=gear,
        profile_readiness={
            "status": "ready" if ready else "blocked",
            "simcReady": ready,
        },
        problems=problems,
    )
```

If an adapter raises, convert the exception to one bounded structured problem with stage `talent_projection` or `gear_projection`; do not leak source payload or credentials.

- [x] **Step 4: Implement the PostgreSQL authority adapters**

Talent adapter:

- reconstruct a Raider.IO community candidate from `snapshot.talentObservation` and source metadata;
- call existing `validate_community_talent_template(store, candidate)`;
- require `status == "verified"`, a non-empty `talentState.selectedNodes`, and `websimExportCode` beginning with `websim:`;
- return only canonical talent state, export/import code, Hero, signature, and freshness/provenance.

Gear adapter:

- pass the snapshot’s exact observed items through the existing PG observed-item backfill entry with `enable_simc_stats=False`;
- construct a template bound to the same source identity;
- call `selection_intent_from_template` with the current Gear Release snapshot;
- parse with `parse_selection_intent`, load the current resolver authority through `store.get_gear_authority_context`, and call `gear_resolver.resolve`;
- require a verified resolved snapshot, complete canonical gear coverage, and a non-empty resolved signature;
- return canonical `selectionIntent`, `gearItems`, `enhancementBySlot`, `resolvedGearSignature`, and resolver dependency evidence.

The adapter must not call the SimulationCraft binary.

- [x] **Step 5: Verify compilation and commit**

```bash
python3 -m unittest \
  tests.observed_build_compiler_test \
  tests.observed_build_projection_test \
  tests.gear_resolver_test \
  tests.gear_runtime_test
git add server/observed_build_compiler.py tests/observed_build_compiler_test.py
git commit -m "feat(builds): compile shared talent and gear projections"
```

Expected: PASS; one failed projection blocks the entire player slot.

---

### Task 4: Add validated active and staging reads to the Registry store

**Files:**
- Modify: `server/observed_build_store.py`
- Modify: `tests/observed_build_store_test.py`

**Interfaces:**
- Produces: `load_pointer(scope) -> dict`.
- Produces: `load_active_records(scope, class_key="", spec_key="", hero_key="") -> dict`.
- Produces: `load_active_projection(scope, projection_id, class_key, spec_key) -> dict`.
- Produces: `load_latest_verified_projections(dependency_hash, checked_since) -> dict[str, dict]`.
- Produces: `health_summary(scope) -> dict`.

- [x] **Step 1: Write failing repeatable-read tests**

```python
def test_active_records_join_pointer_set_slot_snapshot_and_projection(self):
    result = self.store_with_active_rows().load_active_records(
        "candidate",
        class_key="mage",
        spec_key="frost",
    )
    self.assertEqual(result["pointer"]["scope"], "candidate")
    self.assertEqual(len(result["records"]), 2)
    self.assertEqual(
        result["records"][0]["snapshot"]["source"]["sourceIdentity"],
        result["records"][0]["projection"]["sourceIdentity"],
    )

def test_exact_projection_must_belong_to_active_scope_and_spec(self):
    with self.assertRaisesRegex(ObservedBuildIntegrityError, "not active"):
        self.store_with_active_rows().load_active_projection(
            "candidate",
            "build-projection:sha256:" + "f" * 64,
            "mage",
            "frost",
        )
```

- [x] **Step 2: Run the store tests and verify failure**

```bash
python3 -m unittest tests.observed_build_store_test
```

Expected: FAIL because the read methods are absent.

- [x] **Step 3: Implement one repeatable-read active query**

The query must:

- begin `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY`;
- bind one pointer scope;
- join pointer → active TemplateSet → slot rows → exact snapshot → exact projection;
- optionally filter class/spec/Hero;
- order by class/spec/Hero;
- re-run `validate_observed_snapshot`, `validate_projection`, and `validate_template_set`;
- reject mismatched slot, snapshot, projection, source identity, dependency vector, or row hash.

Return:

```python
{
    "pointer": {
        "scope": scope,
        "generation": generation,
        "activeTemplateSetId": template_set_id,
        "rollbackTemplateSetId": rollback_id,
        "updatedAt": updated_at,
    },
    "templateSet": template_set,
    "records": [
        {
            "entry": entry,
            "snapshot": snapshot,
            "projection": projection,
        },
    ],
}
```

- [x] **Step 4: Implement bounded staging and health reads**

`load_latest_verified_projections` selects at most one verified/importable projection per expected slot for an exact dependency hash, ordered by latest successful source check then projection creation time. `health_summary` returns only counts, pointer identity, generation, stale/pending counts, and at most 12 structured problems; it returns no raw gear or talent payload.

- [x] **Step 5: Verify read-only SQL and commit**

```bash
python3 -m unittest tests.observed_build_store_test
git add server/observed_build_store.py tests/observed_build_store_test.py
git commit -m "feat(builds): read active observed template sets"
```

Expected: PASS and fake SQL history contains no update, insert, network, or SimC call for read methods.

---

### Task 5: Derive existing public template contracts from one active TemplateSet

**Files:**
- Create: `server/observed_build_read_model.py`
- Create: `tests/observed_build_read_model_test.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `tests/postgres_cache_store_test.py`
- Modify: `tests/gear_runtime_test.py`

**Interfaces:**
- Produces: `talent_templates_from_active_records(records, hero_key="") -> list[dict]`.
- Produces: `gear_templates_from_active_records(records) -> list[dict]`.
- Produces: exact active gear import context keyed by `projectionId`.

- [ ] **Step 1: Write failing public-shape tests**

```python
def test_one_active_record_projects_to_matching_talent_and_gear_identity(self):
    record = self.active_record()
    talent = talent_templates_from_active_records([record])[0]
    gear = gear_templates_from_active_records([record])[0]
    for field in ("templateSetId", "snapshotId", "sourceIdentity", "playerName", "heroKey"):
        self.assertEqual(talent[field], gear[field])
    self.assertTrue(talent["canApplyVisual"])
    self.assertTrue(gear["canApplyGear"])

def test_one_spec_projects_exactly_two_distinct_gear_templates(self):
    templates = gear_templates_from_active_records(self.two_hero_records())
    self.assertEqual(len(templates), 2)
    self.assertEqual(len({item["sourceIdentity"] for item in templates}), 2)
    self.assertEqual(len({item["heroKey"] for item in templates}), 2)
```

- [ ] **Step 2: Run tests and verify the module is missing**

```bash
python3 -m unittest tests.observed_build_read_model_test
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement talent and gear read models**

Both read models use `projectionId` as stable `id` and include:

```python
common = {
    "id": projection["projectionId"],
    "templateSetId": active["templateSetId"],
    "pointerGeneration": active["generation"],
    "snapshotId": snapshot["snapshotId"],
    "sourceIdentity": snapshot["source"]["sourceIdentity"],
    "classKey": slot["classKey"],
    "specKey": slot["specKey"],
    "heroKey": slot["heroKey"],
    "scenarioKey": slot["scenarioKey"],
    "sourceKey": "raiderio_observed_profile",
    "sourceName": "Raider.IO 真实玩家",
    "sourceUrl": snapshot["source"]["profileUrl"],
    "playerName": snapshot["source"]["character"],
    "serverName": snapshot["source"]["realm"],
    "region": snapshot["source"]["region"],
    "mplusScore": snapshot["rankingEvidence"].get("score", 0),
    "mplusRank": snapshot["rankingEvidence"].get("rank", 0),
    "status": "verified",
    "slotStatus": entry["status"],
    "freshnessStatus": "stale" if entry["status"] == "stale_lkg" else "fresh",
    "isStale": entry["status"] == "stale_lkg",
}
```

Talent adds canonical `talentState`, `rawImportCode`, `websimExportCode`, and `canApplyVisual=True`. Gear adds canonical `gearItems`, `selectionIntent`, `enhancementBySlot`, `canApplyGear=True`, and Hero labels.

- [ ] **Step 4: Delegate PostgresCacheStore reads**

Add one internal helper that loads `WOW_OBSERVED_BUILD_SCOPE`, defaulting to `retail`. If that scope has an active pointer:

- `_community_talent_templates` returns observed talent templates;
- `_gear_community_templates` and active-manifest gear payload replace only `communityTemplates` with observed gear templates;
- legacy baseline templates remain internal and do not enter `communityTemplates`;
- `get_websim_talent_import` reads the exact active observed projection;
- `get_community_template_import_context` detects an active observed `projectionId`, obtains its canonical `selectionIntent`, and resolves it against the same current Gear Manifest authority used by legacy exact import.

If no pointer exists, preserve the current legacy reader unchanged. If a pointer exists but its data fails integrity, fail closed with empty community templates; never silently fall back to legacy public winners.

- [ ] **Step 5: Verify exact import and commit**

```bash
python3 -m unittest \
  tests.observed_build_read_model_test \
  tests.postgres_cache_store_test \
  tests.gear_runtime_test
git add \
  server/observed_build_read_model.py \
  server/postgres_cache_store.py \
  tests/observed_build_read_model_test.py \
  tests/postgres_cache_store_test.py \
  tests/gear_runtime_test.py
git commit -m "feat(builds): serve active observed player templates"
```

Expected: PASS; exact imports reject IDs outside the active candidate scope.

---

### Task 6: Orchestrate collection, compilation, LKG, and pointer policy

**Files:**
- Create: `server/observed_build_sync.py`
- Create: `tests/observed_build_sync_test.py`
- Modify: `server/wow-community-template-sync.service`
- Modify: `server/news_backend.py`
- Modify: `tests/news_backend_api_test.py`

**Interfaces:**
- Produces: `run_observed_build_sync(store, *, scope, refresh_source, allow_promotion, source_fetcher, compiler, checked_at) -> dict`.
- CLI: `python3 -m server.observed_build_sync --scope candidate|retail [--refresh-source] [--promote] [--audit] --json`.
- Sync state key: `observed_build_registry_sync`.

- [ ] **Step 1: Write failing orchestration tests**

```python
def test_partial_initial_run_seals_candidate_but_does_not_move_pointer(self):
    result = run_observed_build_sync(
        self.store(),
        scope="candidate",
        refresh_source=False,
        allow_promotion=True,
        source_fetcher=lambda: self.payload_with_79_slots(),
        compiler=self.compiler,
        checked_at="2026-07-23T12:00:00Z",
    )
    self.assertEqual(result["coverage"]["verified"], 79)
    self.assertEqual(result["promotion"]["action"], "blocked")
    self.assertEqual(result["pointerAfter"], {})

def test_existing_active_set_carries_one_lkg_and_updates_other_slots(self):
    result = run_observed_build_sync(
        self.store_with_active_80(),
        scope="candidate",
        refresh_source=False,
        allow_promotion=True,
        source_fetcher=lambda: self.payload_with_one_blocked_new_winner(),
        compiler=self.compiler,
        checked_at="2026-07-23T13:00:00Z",
    )
    self.assertEqual(result["coverage"]["stale_lkg"], 1)
    self.assertEqual(result["coverage"]["pending_collection"], 0)
    self.assertEqual(result["promotion"]["action"], "auto_promote")
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m unittest tests.observed_build_sync_test
```

Expected: FAIL because the orchestration module does not exist.

- [ ] **Step 3: Implement the bounded stage sequence**

The runner executes exactly:

1. source refresh through injected `source_fetcher`;
2. snapshot candidate extraction and distinct winner election;
3. snapshot/check sealing;
4. observed-item authority backfill for the exact newly selected profiles;
5. projection compilation and sealing;
6. merge current-run candidates with fresh previously verified staging projections for still-missing first-cutover slots;
7. TemplateSet build and seal;
8. `promotion_decision`;
9. CAS only when `allow_promotion` and action is `controlled_cutover` or `auto_promote`;
10. bounded sync-state write.

The runner never catches a source or compile failure and reports success. It returns:

```python
{
    "schemaRevision": "observed-build-registry-sync-v1",
    "scope": scope,
    "sourceRunId": source_run_id,
    "sourceStatus": source_status,
    "coverage": {
        "total": 80,
        "verified": verified,
        "stale_lkg": stale_lkg,
        "pending_collection": pending_collection,
        "gearCompleteSpecs": gear_complete_specs,
    },
    "candidateTemplateSetId": candidate_id,
    "promotion": promotion,
    "pointerBefore": pointer_before,
    "pointerAfter": pointer_after,
    "problems": problems[:12],
}
```

- [ ] **Step 4: Add safe CLI modes**

CLI rules:

- `--audit` is read-only and cannot combine with `--refresh-source` or `--promote`;
- `--scope candidate --promote` may create/update only candidate pointer;
- `--scope retail --promote` requires `WOW_OBSERVED_BUILD_RETAIL_CUTOVER=1`;
- scheduled execution without `--promote` auto-promotes only when the scope already has an active pointer and the change is `observed_only`;
- initial activation is always explicit.

- [ ] **Step 5: Switch the scheduled service with rollback retained**

Set:

```ini
Environment=WOW_OBSERVED_BUILD_SCOPE=retail
ExecStart=/usr/bin/flock -w 7200 /run/lock/wow-mini-program-sync.lock /usr/bin/python3 -m server.observed_build_sync --scope retail --refresh-source --json
```

Keep `server/community_template_sync.py` in the repository and record that restoring the previous unit file plus `systemctl daemon-reload` is the code rollback.

- [ ] **Step 6: Expose bounded health**

`build_postgres_only_data_health_payload` adds `observedBuildRegistry` from `ObservedBuildStore.health_summary("retail")`. Before retail activation its status is `pre_cutover`; after activation it reports exact generation, 80 total, verified/stale/pending counts, 40 gear-complete specs, and at most 12 problem codes.

- [ ] **Step 7: Verify and commit**

```bash
python3 -m unittest \
  tests.observed_build_sync_test \
  tests.news_backend_api_test \
  tests.data_health_followup_test
git add \
  server/observed_build_sync.py \
  server/wow-community-template-sync.service \
  server/news_backend.py \
  tests/observed_build_sync_test.py \
  tests/news_backend_api_test.py
git commit -m "feat(builds): orchestrate observed player template sets"
```

Expected: PASS; read-only audit performs zero writes and initial retail activation requires the explicit environment gate.

---

### Task 7: Preserve the existing WeChat import experience with explicit provenance

**Files:**
- Modify: `packages/domain/src/entities.ts`
- Modify: `packages/api-client/src/websim.ts`
- Modify: `packages/api-client/src/websim.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts`
- Modify: `apps/mini-taro/src/pages/builds/talent-simulator-model.test.ts`
- Create: `scripts/audit-observed-build-cutover.py`

**Interfaces:**
- Consumes: existing `CommunityTemplateReference`.
- Produces optional fields `templateSetId`, `snapshotId`, `sourceIdentity`, `pointerGeneration`, `slotStatus`.
- Produces exhaustive HTTP audit with nonzero exit status on any missing/mismatched/import-blocked slot.

- [ ] **Step 1: Write failing API normalization tests**

```typescript
expect(normalizeCommunityTemplateReference({
  id: 'build-projection:sha256:abc',
  templateSetId: 'template-set:sha256:def',
  snapshotId: 'observed-build:sha256:ghi',
  sourceIdentity: 'raiderio:cn|realm|player',
  pointerGeneration: 3,
  slotStatus: 'stale_lkg',
})).toMatchObject({
  templateSetId: 'template-set:sha256:def',
  snapshotId: 'observed-build:sha256:ghi',
  sourceIdentity: 'raiderio:cn|realm|player',
  pointerGeneration: 3,
  slotStatus: 'stale_lkg',
})
```

Add a gear model fixture containing two Hero templates and assert both remain import options with distinct player labels. Add a talent model fixture for each Hero and assert the selected Hero receives exactly its own projection ID.

- [ ] **Step 2: Run the client tests and verify failure**

```bash
npx vitest run \
  packages/api-client/src/websim.test.ts \
  apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts \
  apps/mini-taro/src/pages/builds/talent-simulator-model.test.ts
```

Expected: FAIL because the new provenance fields are not typed/normalized.

- [ ] **Step 3: Extend type and normalizer without changing mounted interaction**

Add:

```typescript
templateSetId?: string
snapshotId?: string
sourceIdentity?: string
pointerGeneration?: number
slotStatus?: 'verified' | 'stale_lkg' | 'pending_collection' | string
```

Normalize the four strings with the existing `cleanString` path and accept `pointerGeneration` only when it is a finite non-negative number. Do not add client-side winner election, LKG, pairing, or fallback.

- [ ] **Step 4: Implement exhaustive cutover audit**

The script obtains the 80 expected triplets from the repository contract and, for a required `--base-url`:

- GETs each talent payload and requires exactly one verified/importable matching-Hero template;
- records `templateSetId/snapshotId/sourceIdentity`;
- GETs each of 40 gear payloads and requires exactly two importable templates, two Hero keys, and two distinct source identities;
- checks gear/talent identity equality for every Hero slot;
- POSTs `/api/websim/gear/community-import` for all 80 projection IDs and requires HTTP 200 plus verified/resolved import data;
- POSTs the existing talent import-code endpoint for all 80 export codes and requires accepted validation;
- outputs counts and at most 12 failures, with no raw profile payload.

- [ ] **Step 5: Verify frontend contracts and commit**

```bash
npx vitest run \
  packages/api-client/src/websim.test.ts \
  apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts \
  apps/mini-taro/src/pages/builds/talent-simulator-model.test.ts
node scripts/audit-ui-architecture.js
git add \
  packages/domain/src/entities.ts \
  packages/api-client/src/websim.ts \
  packages/api-client/src/websim.test.ts \
  apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts \
  apps/mini-taro/src/pages/builds/talent-simulator-model.test.ts \
  scripts/audit-observed-build-cutover.py
git commit -m "feat(builds): expose observed template provenance"
```

Expected: PASS; mounted pages continue using the existing import buttons and server-selected templates.

---

### Task 8: Harness verification, candidate collection, and WeChat DevTools handoff

**Files:**
- Create: `artifacts/releases/2026-07-23-observed-build-registry-cutover/requirement.json`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-cutover/evidence.json`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-cutover/manifest.json`
- Create: `artifacts/releases/2026-07-23-observed-build-registry-cutover/candidate-smoke.json`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/community-template-import-full-chain-runbook.md`

**Interfaces:**
- Consumes: final PR head, known cloud host, approved Raider.IO collection, candidate pointer scope, candidate backend port `18787`.
- Produces: candidate-verified release packet and a WeChat DevTools build pointed through local SSH tunnel to candidate backend.

- [ ] **Step 1: Create the task-scoped Harness packet**

Freeze manual acceptance items:

```json
[
  "gear-two-real-templates-visible",
  "gear-both-templates-importable",
  "talent-one-real-template-per-hero-visible",
  "talent-template-importable",
  "shared-player-provenance-visible"
]
```

Set all items to `pending` until the user tests in DevTools. Record migration, source collection, 80/80 matrix, 40/40×2 matrix, exact import, candidate isolation, rollback, timer, health, and DevTools refresh as required evidence.

- [ ] **Step 2: Run local targeted and full verification**

```bash
python3 -m unittest \
  tests.observed_build_characterization_test \
  tests.observed_build_registry_test \
  tests.observed_build_projection_test \
  tests.observed_build_template_set_test \
  tests.observed_build_store_test \
  tests.observed_build_ingest_test \
  tests.observed_build_compiler_test \
  tests.observed_build_read_model_test \
  tests.observed_build_sync_test \
  tests.observed_build_core_path_test \
  tests.postgres_schema_test \
  tests.postgres_cache_store_test \
  tests.gear_runtime_test \
  tests.news_backend_api_test
npx vitest run \
  packages/api-client/src/websim.test.ts \
  apps/mini-taro/src/pages/builds/gear-template-import-model.test.ts \
  apps/mini-taro/src/pages/builds/talent-simulator-model.test.ts
node scripts/verify-project.js \
  --profile full \
  --release artifacts/releases/2026-07-23-observed-build-registry-cutover \
  --base origin/main
```

Expected: PASS. Any unchanged base failure is corrected or recorded according to Harness; no correctness gate is weakened.

- [ ] **Step 3: Prepare isolated candidate runtime**

On the known host:

- create `/opt/wow-mini-program-candidate/observed-build-registry-<short-sha>`;
- back up the production PostgreSQL database before applying additive migration `0018`;
- copy the exact PR head;
- apply `0018` once;
- start a candidate backend bound to `127.0.0.1:18787` with `WOW_OBSERVED_BUILD_SCOPE=candidate`;
- keep production `wow-backend.service`, `retail` pointer, and public Nginx route unchanged;
- record exact commit/tree, migration state, service PID/unit, backup path/hash, and rollback command.

- [ ] **Step 4: Run controlled collection until the honest matrix closes**

Run one approved refresh:

```bash
sudo -u ubuntu env \
  WOW_DATABASE_RUNTIME=postgres_only \
  WOW_OBSERVED_BUILD_SCOPE=candidate \
  python3 -m server.observed_build_sync \
  --scope candidate \
  --refresh-source \
  --json
```

If slots remain pending, rerun only the reported missing class/spec targets with the existing bounded ranking pages/run-detail budgets. Each successful slot is sealed and reused; failures remain explicit. Stop rather than activate if the source cannot provide two distinct valid players for a spec.

When coverage reaches 80 verified, activate only candidate:

```bash
sudo -u ubuntu env \
  WOW_DATABASE_RUNTIME=postgres_only \
  WOW_OBSERVED_BUILD_SCOPE=candidate \
  python3 -m server.observed_build_sync \
  --scope candidate \
  --promote \
  --json
```

Expected: candidate pointer generation becomes positive; retail pointer remains absent or unchanged.

- [ ] **Step 5: Run exhaustive candidate API/import audit**

Open a local tunnel:

```bash
ssh -N -L 18787:127.0.0.1:18787 wow-lighthouse
```

In another terminal:

```bash
python3 scripts/audit-observed-build-cutover.py \
  --base-url http://127.0.0.1:18787 \
  --json
```

Expected:

```json
{
  "talentSlots": 80,
  "talentImportable": 80,
  "gearSpecs": 40,
  "gearTemplates": 80,
  "gearImportable": 80,
  "sharedIdentityMatches": 80,
  "distinctSpecPairs": 40,
  "failures": []
}
```

- [ ] **Step 6: Prove rollback and restore candidate**

Use the candidate pointer generation to call `rollback_pointer("candidate", generation, actor)`, verify the previous set serves correctly, then CAS the verified candidate set active again. Production retail remains unchanged.

- [ ] **Step 7: Build and open the candidate in WeChat DevTools**

With the SSH tunnel still active:

```bash
WOW_BACKEND_API_BASE_URL=http://127.0.0.1:18787 npm run refresh:weapp
```

Expected: `apps/mini-taro/dist/weapp` rebuilds successfully and the official DevTools CLI opens `apps/mini-taro`. If CLI discovery or the DevTools service port is unavailable, report the exact manual import path and `WECHAT_DEVTOOLS_CLI` override; do not claim DevTools opened.

- [ ] **Step 8: Pause for explicit user acceptance**

Ask the user to verify the five frozen items. Do not merge or switch the production retail pointer until the user explicitly says the DevTools checks passed or authorizes closure.

- [ ] **Step 9: Execute Harness User Acceptance Closure**

After explicit acceptance:

1. run final local CR;
2. commit final evidence;
3. push the task branch and wait for CI;
4. merge without history rewrite;
5. verify local/main and `origin/main` SHA parity;
6. deploy exact merged main with async sync disabled;
7. apply the already-proven additive migration;
8. start the new scheduled unit;
9. explicitly promote the same verified set to `retail` with `WOW_OBSERVED_BUILD_RETAIL_CUTOVER=1`;
10. rerun the exhaustive audit against production base URL;
11. run `npm run refresh:weapp` from latest main using the production API base;
12. clean candidate service, SSH tunnel, task worktree, and published task branch while retaining the database backup and rollback TemplateSet.

Expected: production reports 80 talent slots, 40 specs/80 gear templates, 80 shared identity matches, zero pending slots, and a valid rollback generation.

---

## Self-Review

- **Spec coverage:** Tasks 1-8 cover shared identity, distinct players, fail-closed first activation, same-slot LKG, direct source ingestion, local talent/gear mapping, atomic TemplateSet publication, existing API/import contracts, health/timer, candidate isolation, exhaustive 80/40 verification, rollback, and DevTools handoff.
- **Scope control:** Combat SimC, BiS optimization, new recommendation scoring, WCL ranking, new frontend election logic, and legacy compatibility retirement remain outside this implementation.
- **Type consistency:** `sourceIdentity`, `snapshotId`, `projectionId`, `templateSetId`, `pointerGeneration`, `slotStatus`, `selectionIntent`, and the pointer scope names are consistent across snapshot, projection, TemplateSet, store, read model, API, client, and audit steps.
- **Placeholder scan:** The plan contains no deferred implementation markers; every test, interface, command, activation gate, and expected outcome is specified.
- **Execution topology:** Execute inline in the current session with `superpowers:executing-plans`; multi-agent execution is disabled for this thread.
