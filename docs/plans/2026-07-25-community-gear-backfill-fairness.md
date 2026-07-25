# Community Gear Backfill Fairness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Ensure every retained Raider.IO candidate, including a player still referenced by the active observed TemplateSet after leaving the latest ranking payload, eventually receives bounded exact-gear SimC enrichment; make an incomplete exact variant ineligible for public community-template import.

**Architecture:** The scheduled PostgreSQL backfill owns bounded SimC work; observed-build compilation only consumes already verified evidence. Its candidate pool merges current cached Raider.IO profiles with immutable profiles still referenced by the active observed TemplateSet, deduplicated by profile identity and rotated through one persisted cursor. Every projected observed slot must resolve to a non-empty verified exact variant before the compiler or public read model calls it importable.

**Tech Stack:** Python 3, PostgreSQL cache/sync state, SimulationCraft worker, unittest, existing Harness release packet.

## Global Constraints

- Keep WOW_DATABASE_RUNTIME=postgres_only; no SQLite public or scheduled fallback.
- Do not execute combat SimulationCraft from server/observed_build_compiler.py.
- Do not synthesize or accept a blank/default observed variantKey.
- Selection still prefers the highest-ranked verified candidate per slot; rotation controls only the background evidence queue.
- An active observed snapshot remains eligible for background repair even if the newest cached ranking payload no longer contains that player; this does not add it to public ranking or change winner election.
- Preserve same-slot LKG. If no verified LKG exists, omit the incomplete candidate from the importable public list.
- The existing target_limit and profile_limit remain resource limits; a cursor moves only after a whole profile is handled.
- Do not commit, merge, push or promote retail until the frozen candidate smoke and manual acceptance contract are complete.

---

### Task 1: Freeze the Strict requirement and active-plan references

**Files:**
- Create: artifacts/releases/2026-07-25-community-gear-backfill-fairness/requirement.json
- Create: docs/plans/2026-07-25-community-gear-backfill-fairness.md
- Modify: docs/plans/README.md
- Modify: docs/roadmap.md

**Interfaces:**
- Consumes: the active observed-build cutover plan and current PG-only backfill.
- Produces: an implementation_allowed requirement with two frozen WeChat acceptance observations.

- [ ] **Step 1: Validate the requirement before runtime changes**

Run:

~~~powershell
node scripts/project-harness.js --check-requirement --requirement-file artifacts/releases/2026-07-25-community-gear-backfill-fairness/requirement.json
~~~

Expected: Strict requirement is accepted. This is a contract check only, not a deployment claim.

- [ ] **Step 2: Register the plan and product rule**

Add this row to docs/plans/README.md:

~~~markdown
| 社区装备 SimC 回填公平性与导入门禁 | 正在推进 | [2026-07-25-community-gear-backfill-fairness.md](2026-07-25-community-gear-backfill-fairness.md) |
~~~

Add one P1 note to docs/roadmap.md: bounded community-gear SimC enrichment must rotate through its candidate pool, and an unverified exact variant has no import entry.

- [ ] **Step 3: Verify documentation scope**

Run:

~~~powershell
git diff --check
git diff -- artifacts/releases/2026-07-25-community-gear-backfill-fairness/requirement.json docs/plans/README.md docs/roadmap.md
~~~

Expected: only this task's requirement, active-plan registration, and active P1 rule are changed.

### Task 2: Add a deterministic persisted profile rotation to the PG worker

**Files:**
- Create: server/observed_gear_backfill_window.py
- Modify: server/postgres_cache_store.py:6301-6470
- Modify: server/postgres_cache_sync.py:4097-4169
- Modify: tests/postgres_cache_store_test.py
- Modify: tests/postgres_cache_sync_test.py

**Interfaces:**
- Consumes: cached Raider.IO candidate profiles, immutable active observed-snapshot profiles, and prior gear_observed_backfill sync-state payload.
- Produces: build_observed_profile_window(profiles, after_profile_identity, profile_limit) and results containing profileCursor, profileWindowWrapped, and candidateProfileCount.

- [ ] **Step 1: Write the failing pure-window regression**

Add three profiles alpha, bravo, and charlie. It must prove the next two-profile window continues after its persisted identity and wraps only after the pool end:

~~~python
first = build_observed_profile_window(profiles, after_profile_identity="", profile_limit=2)
self.assertEqual([profile["name"] for profile in first["profiles"]], ["alpha", "bravo"])

second = build_observed_profile_window(
    profiles,
    after_profile_identity=first["cursor"]["afterProfileIdentity"],
    profile_limit=2,
)
self.assertEqual([profile["name"] for profile in second["profiles"]], ["charlie", "alpha"])
self.assertTrue(second["wrapped"])
~~~

Also cover a removed cursor identity: select the deterministic next identity rather than silently restarting at the first ranking row.

- [ ] **Step 2: Run it to prove the characterization is missing**

Run:

~~~powershell
python -m unittest tests.postgres_cache_store_test.PostgresCacheStoreTest.test_observed_backfill_profile_cursor_rotates_candidates
~~~

Expected: FAIL because no window helper or cursor result exists.

- [ ] **Step 3: Implement the pure profile-window helper**

Create server/observed_gear_backfill_window.py. Its identity includes the source facts that distinguish one observed player, and its ordering does not depend on the mutable rank used later for product selection.

~~~python
def build_observed_profile_window(profiles, *, after_profile_identity="", profile_limit=None):
    ordered = _unique_profiles_sorted_by_identity(profiles)
    start = _next_profile_index(ordered, after_profile_identity)
    count = len(ordered) if profile_limit is None else min(len(ordered), max(0, int(profile_limit)))
    selected = [ordered[(start + offset) % len(ordered)] for offset in range(count)] if ordered else []
    return {
        "profiles": selected,
        "availableProfileCount": len(ordered),
        "cursor": {"afterProfileIdentity": profile_identity(selected[-1]) if selected else after_profile_identity},
        "wrapped": bool(selected and start + len(selected) > len(ordered)),
    }
~~~

- [ ] **Step 4: Run the pure-window regression**

Run the command from Step 2.

Expected: PASS; a later candidate is selected in the second bounded run.

- [ ] **Step 5: Write failing store and wrapper regressions**

Add a store test with more candidates than the configured profile and item budgets. Call a second run with the first run's profileCursor, assert its processed profile is outside the first window, and assert the returned cursor belongs to the last whole profile accepted.

Add a sync-wrapper test whose fake store returns:

~~~python
{"profileCursor": {"afterProfileIdentity": "raiderio:cn|realm|bravo"}}
~~~

Assert the wrapper forwards this value to backfill_observed_gear_from_raiderio and writes the returned value under GEAR_OBSERVED_BACKFILL_SYNC_KEY.

- [ ] **Step 6: Run those regressions and confirm failure**

Run:

~~~powershell
python -m unittest tests.postgres_cache_store_test.PostgresCacheStoreTest.test_observed_backfill_profile_cursor_rotates_candidates tests.postgres_cache_sync_test.PostgresCacheSyncTest.test_observed_backfill_postgres_persists_profile_cursor
~~~

Expected: FAIL because the store and wrapper do not accept profile_cursor.

- [ ] **Step 7: Thread cursor state through scheduled backfill**

Change run_gear_observed_backfill_postgres to read store.get_sync_state(GEAR_OBSERVED_BACKFILL_SYNC_KEY), pass profileCursor as profile_cursor, and persist the returned cursor with current-run facts.

Change PostgresCacheStore.backfill_observed_gear_from_raiderio to accept profile_cursor=None. For a scheduled window, merge the current Raider.IO profile candidates with valid active TemplateSet snapshots, dedupe by the same stable profile identity, then use the window helper. For mode == observed_build_compile, retain caller-provided exact profiles and never consume scheduled cursor state.

Before running SimC for a scheduled profile, do not start a new profile if its complete gear set would exceed remaining target_limit after a prior profile was accepted. Advance profileCursor only after the profile's accepted rows are built. Return:

~~~python
{
    "candidateProfileCount": window["availableProfileCount"],
    "profileCursor": cursor_after_last_whole_profile,
    "profileWindowWrapped": window["wrapped"],
    "stopReason": "target_limit_reached",
}
~~~

- [ ] **Step 8: Run cursor coverage**

Run:

~~~powershell
python -m unittest tests.postgres_cache_store_test tests.postgres_cache_sync_test
~~~

Expected: PASS. Direct compiler preparation still passes enable_simc_stats=False and does not mutate scheduled cursor state.

### Task 3: Block unresolved exact variants during observed-build compilation

**Files:**
- Modify: server/observed_build_compiler.py:679-803
- Modify: tests/observed_build_compiler_test.py

**Interfaces:**
- Consumes: selection_intent_from_template plus one immutable snapshot's observed gear slots.
- Produces: a verified gear projection only when every observed slot resolves to a non-empty canonical exact variantKey; otherwise a bounded gear_observed_variant_evidence_incomplete problem.

- [ ] **Step 1: Write the failing compiler regression**

Build a snapshot with an observed head item but no verified matching variant in the release snapshot. Stub Resolver only if reached:

~~~python
result = _compile_gear_with_postgres(store, snapshot, dependencies, "simc-r1")
self.assertEqual(result["status"], "blocked")
self.assertEqual(result["problems"][0]["code"], "gear_observed_variant_evidence_incomplete")
self.assertEqual(store.get_gear_authority_context_calls, [])
~~~

- [ ] **Step 2: Run it to verify it currently fails**

Run:

~~~powershell
python -m unittest tests.observed_build_compiler_test.ObservedBuildCompilerTest.test_compile_blocks_empty_observed_variant_key
~~~

Expected: FAIL because a blank variant key is currently passed to Resolver.

- [ ] **Step 3: Implement the minimal exact-variant gate**

Immediately after parse_selection_intent, require the parsed slot set to equal the source snapshot's observed slot set and reject empty exact keys before loading Resolver authority:

~~~python
incomplete_slots = [
    slot for slot, selection in (parsed_intent.get("slots") or {}).items()
    if not _text((selection or {}).get("variantKey"))
]
if incomplete_slots:
    return {
        "status": "blocked",
        "problems": [{
            "code": "gear_observed_variant_evidence_incomplete",
            "stage": "gear_projection",
            "message": "Observed gear is waiting for exact SimulationCraft variant evidence.",
        }],
    }
~~~

- [ ] **Step 4: Run compiler coverage**

Run:

~~~powershell
python -m unittest tests.observed_build_compiler_test tests.observed_build_projection_test tests.gear_resolver_test tests.gear_runtime_test
~~~

Expected: PASS. Compilation remains SimC-free and blocks only incomplete observed evidence.

### Task 4: Make public templates and exact import sources agree

**Files:**
- Modify: server/observed_build_read_model.py:222-335
- Modify: tests/observed_build_read_model_test.py
- Test: tests/community_template_import_test.py

**Interfaces:**
- Consumes: an active record's verified projection, exact selectionIntent, and projected gearItems.
- Produces: only fully exact public templates and import sources. An invalid active record is omitted and direct import raises a bounded error.

- [ ] **Step 1: Write failing public-read regressions**

Start with active_record() and blank both selectionIntent.slots.head.variantKey and the projected head item's variantKey:

~~~python
self.assertEqual(gear_templates_from_active_records([record]), [])
with self.assertRaisesRegex(ValueError, "exact variant"):
    gear_import_source_from_active_record(record)
~~~

Keep the stale-LKG test unchanged: a stale but fully verified projection stays importable.

- [ ] **Step 2: Run them to verify the false-positive behavior**

Run:

~~~powershell
python -m unittest tests.observed_build_read_model_test.ObservedBuildReadModelTest.test_incomplete_exact_variant_is_not_public_or_importable
~~~

Expected: FAIL because _gear_template currently sets status=complete and canApplyGear=True unconditionally.

- [ ] **Step 3: Implement one shared exact-importability predicate**

Add a private predicate in observed_build_read_model.py. It requires matching non-empty item IDs and variant keys for every selection slot:

~~~python
def _has_complete_exact_gear_identity(gear, gear_items):
    slots = gear.get("selectionIntent", {}).get("slots", {})
    items_by_slot = {item.get("slot"): item for item in gear_items}
    return bool(slots) and set(slots) == set(items_by_slot) and all(
        isinstance(selection, dict)
        and _text(selection.get("itemId"))
        and _text(selection.get("variantKey"))
        and _text(items_by_slot[slot].get("itemId")) == _text(selection.get("itemId"))
        and _text(items_by_slot[slot].get("variantKey")) == _text(selection.get("variantKey"))
        for slot, selection in slots.items()
    )
~~~

Use it to filter gear_templates_from_active_records and to guard gear_import_source_from_active_record before it builds slots. Leave server/community_template_import.py unchanged as the final immutable matcher.

- [ ] **Step 4: Run public-contract coverage**

Run:

~~~powershell
python -m unittest tests.observed_build_read_model_test tests.community_template_import_test tests.pg_gear_template_selectors_test tests.news_backend_test
~~~

Expected: PASS. An incomplete active record has no false import action; verified LKG and the final importer are unchanged.

### Task 5: Candidate proof, cited-mage repair, and manual acceptance

**Files:**
- Create: artifacts/releases/2026-07-25-community-gear-backfill-fairness/evidence.json
- Create: artifacts/releases/2026-07-25-community-gear-backfill-fairness/manifest.json
- Modify: artifacts/releases/2026-07-25-community-gear-backfill-fairness/requirement.json
- Modify: docs/roadmap.md

**Interfaces:**
- Consumes: clean task commit, candidate backend, cached candidate pool, and existing scheduled units.
- Produces: task-scoped candidate proof and a one-route WeChat handoff; it does not authorize retail promotion or merge before user acceptance.

- [ ] **Step 1: Run local verification at a clean task head**

Run focused tests from Tasks 2-4, git diff --check, then the repository Harness profile. Create evidence/manifest only with evidence actually collected.

- [ ] **Step 2: Candidate-deploy the immutable task commit**

Record branch, commit/tree, runtime file parity, health, /api/data/health, and the prior retail pointer before starting a bounded backfill.

- [ ] **Step 3: Prove rotation and repair the cited exact variant**

Run bounded candidate backfill until the persisted cursor passes 皓月当空. Record cursor and stop reason on each run. Compose observed-build candidate data, then prove item 258516, level 298, bonus IDs 13440/6652/12701/13654, and enchant IDs 7981/8052 are a verified exact variant.

Check both public reads:

~~~text
GET /api/websim/gear?class=mage&spec=arcane&compact=1
POST /api/websim/gear/community-import for the active mage projection
~~~

Expected: incomplete records never advertise canApplyGear=true; after evidence and composition, exact mage import succeeds without a blank key.

- [ ] **Step 4: Verify timer/backflow and rollback**

Inspect the observed-backfill service/timer or follow-up trigger and wow-community-template-sync.service. Confirm the next scheduled run preserves the cursor and cannot overwrite verified data with partial data. Record candidate code rollback/feature-hide and retail-pointer preservation.

- [ ] **Step 5: Request the frozen manual acceptance in one route**

Ask the user to run:

~~~text
装备详情 → 导入装备模板 → 社区模板 → 皓月当空
~~~

Record two observations against the frozen IDs: no false import action while incomplete, then successful exact import after verified candidate repair.
