# Equipment Simulator Catalog Phase 0 Audit Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct the Phase 0 migration audit so legacy Browse candidates, observed exact instances, incomplete placeholders, and reference-only previews are classified before Catalog mapping, and generic community ranking fields can never be interpreted as equipment track rank.

**Architecture:** Keep the existing read-only Phase 0 boundary. The PostgreSQL projection will expose explicit legacy row-family evidence and reference counts without user data; the pure audit owner will map only Browse candidates, record approved exclusions separately, and require dedicated `trackRank` or `upgradeRank` evidence. The same Phase 0 release packet will be regenerated from a fresh isolated production read-only run.

**Tech Stack:** Python 3 standard library, psycopg read-only projection, `unittest`, repository-native Project Harness.

## Global Constraints

- Stay on `codex/equipment-simulator-target-architecture`; this is a pre-merge correction to PR #101, not a Phase 1 task.
- Do not create a second Harness release packet.
- Do not add a schema, builder, public reader, API field, runtime consumer, timer, service restart, deployment, release seal, or Manifest pointer change.
- Do not infer track rank from generic `payload.rank`, item level, labels, leaderboard evidence, or frontend text.
- `difficultyKey=observed_profile` is legacy exact-instance evidence and is excluded from Browse mapping; it is not declared Exact-ready.
- `needs-variant` rows and Battle.net preview rows are explicit non-Browse exclusions and remain visible in aggregate evidence.
- Items without a canonical slot may be excluded only when the active release has neither a source reference nor a variant reference for that item.
- The production rerun must use the exact committed tool bytes, a read-only transaction, bounded queries, timeouts, rollback, and zero writes.
- The final decision remains mechanical. No corrected count may be promoted to `pass` unless every required gate condition is actually satisfied.

---

### Task 1: Freeze legacy row-family behavior in pure audit tests

**Files:**
- Modify: `tests/gear_catalog_migration_audit_test.py`
- Modify: `server/gear_catalog_migration_audit.py`

**Interfaces:**
- Consumes: `audit_catalog_mapping(binding: Any, rows: Any) -> dict[str, Any]`
- Produces: deterministic `browseVariantTotal`, `mappedBrowseVariantCount`, `excludedExactInstanceCount`, `excludedPlaceholderVariantCount`, `excludedReferenceVariantCount`, and `excludedNonCatalogItemCount`

- [ ] **Step 1: Write the failing exact-instance/ranking-field test**

Add a literal fixture with `rowFamily="exact_instance"`, `difficultyKey="observed_profile"`, `rank=527`, `rankingEvidence`, no `trackKey`, and no `trackRank`. Assert that:

```python
self.assertEqual(result["excludedExactInstanceCount"], 1)
self.assertEqual(result["browseVariantTotal"], 1)
self.assertNotIn("CATALOG_VARIANT_RANK_MISSING", result["problemCodes"])
self.assertEqual(result["mappedBrowseVariantCount"], 1)
```

The second variant in the same fixture is a valid Browse row with an explicit `trackRank`.

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_migration_audit_test.GearCatalogMigrationAuditTest.test_exact_instance_ranking_field_never_becomes_browse_track_rank \
  -v
```

Expected: FAIL because the current audit treats every variant as Browse and reads generic `rank`.

- [ ] **Step 3: Write failing exclusion tests**

Add independent tests proving:

```python
# Unreferenced metadata item
self.assertEqual(result["excludedNonCatalogItemCount"], 1)
self.assertNotIn("CATALOG_ITEM_SLOT_MISSING", result["problemCodes"])

# Referenced empty-slot item
self.assertIn("CATALOG_ITEM_SLOT_MISSING", result["problemCodes"])

# Placeholder and preview rows
self.assertEqual(result["excludedPlaceholderVariantCount"], 1)
self.assertEqual(result["excludedReferenceVariantCount"], 1)
self.assertEqual(result["browseVariantTotal"], 1)
```

- [ ] **Step 4: Run the new tests and verify RED**

Run all named correction tests. Each must fail because the result does not yet expose family/exclusion counts.

- [ ] **Step 5: Implement the smallest pure classification change**

In `audit_catalog_mapping`:

```python
row_family = _text(row.get("rowFamily"))
if row_family == "exact_instance":
    excluded_exact_instance_count += 1
    continue
if row_family == "placeholder":
    excluded_placeholder_variant_count += 1
    continue
if row_family == "reference":
    excluded_reference_variant_count += 1
    continue
if row_family != "browse":
    problems.append(_problem(
        "CATALOG_VARIANT_FAMILY_UNCLASSIFIED",
        f"rows.variants[{index}].rowFamily",
        "Legacy variant must be classified before Catalog mapping.",
    ))
    continue
```

For Browse rows, consume only `trackRank` or `upgradeRank`; do not consume generic `rank`.

For items, exclude an empty-slot row only when both `hasSourceRefs` and `hasVariantRefs` are false.

- [ ] **Step 6: Run the pure audit suite and verify GREEN**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_test -v
```

Expected: all tests pass and the complete fixture remains `verified`.

- [ ] **Step 7: Commit**

```bash
git add tests/gear_catalog_migration_audit_test.py server/gear_catalog_migration_audit.py
git commit -m "fix(gear): classify legacy catalog audit rows"
```

### Task 2: Project explicit family and reference facts from PostgreSQL

**Files:**
- Modify: `tests/gear_catalog_audit_store_test.py`
- Modify: `server/gear_catalog_audit_store.py`

**Interfaces:**
- Consumes: immutable active Gear Release item and variant rows
- Produces: aggregate-safe item reference booleans plus `rowFamily`, `trackKey`, `trackRank`, `simcOptions`, and existing variant facts

- [ ] **Step 1: Write the failing projection test**

Use real `GearCatalogAuditStore.snapshot()` behavior with fake database rows. The fixture must include:

```python
{
    "difficultyKey": "observed_profile",
    "payload": {"rank": 527, "rankingEvidence": {"rank": 527}},
}
```

Assert:

```python
self.assertEqual(variant["rowFamily"], "exact_instance")
self.assertEqual(variant["trackRank"], 0)
self.assertNotIn("rank", variant)
```

Add fixtures for `needs-variant`, `battle_net_preview`, and one ordinary Browse track.

- [ ] **Step 2: Run the store test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_audit_store_test.GearCatalogAuditStoreTest.test_snapshot_classifies_legacy_variant_families_without_ranking_leakage \
  -v
```

Expected: FAIL because the current projection has no `rowFamily`/`trackRank` split and exposes generic `rank`.

- [ ] **Step 3: Write the failing item-reference test**

Extend the item row fixture with source/variant reference booleans and assert they are preserved as booleans in `catalogRows.items`.

- [ ] **Step 4: Run the item-reference test and verify RED**

Expected: FAIL because `_items` currently selects six columns and has no reference evidence.

- [ ] **Step 5: Implement the fixed-query projection**

Update the item query with bounded `EXISTS` projections for active release sources and variants. Add a private pure family classifier with these exact branches:

```text
observed_profile -> exact_instance
needs-variant / needs_variant -> placeholder
battle_net_preview -> reference
all other non-empty difficulty keys -> browse
empty/unknown -> unclassified
```

Project `trackKey` from dedicated payload keys or `itemLevelTrack`/difficulty, and `trackRank` only from `trackRank` or `upgradeRank`. Preserve normalized `simcOptions`; do not persist payload, player identity, ranking evidence, names, URLs, or realms in the report.

- [ ] **Step 6: Run store, CLI, and pure suites**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_audit_store_test \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_migration_audit_cli_test \
  -v
```

Expected: all tests pass, query count remains bounded, and write count remains zero.

- [ ] **Step 7: Commit**

```bash
git add tests/gear_catalog_audit_store_test.py server/gear_catalog_audit_store.py
git commit -m "fix(gear): project catalog audit row families"
```

### Task 3: Re-run the exact production read-only audit

**Files:**
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json`
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/phase1-decision.json`

**Interfaces:**
- Consumes: exact committed correction tool hashes, active production pointer, unchanged caller inventory
- Produces: one compact aggregate audit report and one mechanical Phase 1 decision

- [ ] **Step 1: Commit all tool bytes before production use**

Confirm `git status --short` contains no source/test changes and record the exact commit plus SHA-256 for the CLI, store, and pure policy.

- [ ] **Step 2: Capture pre-run service, pointer, timer, and health identity**

Use read-only SSH/systemd/API checks. Do not print the database URL or EnvironmentFile contents.

- [ ] **Step 3: Run the exact committed CLI in an isolated transient context**

Use `/tmp` only, load the existing backend EnvironmentFile through a transient unit, preserve statement/lock/batch/sample limits, and produce no file under `/opt/wow-mini-program`.

- [ ] **Step 4: Verify the corrected distribution**

The report must show four disjoint variant families whose totals sum to `variantTotal`. Generic community ranking fields must not increase `mappedBrowseVariantCount`. Missing track-rank problems must be limited to Browse rows.

- [ ] **Step 5: Verify zero-write and unchanged runtime witnesses**

Require:

```text
pointer before == pointer after
audit query writes == 0
release/template/stat/SimC rows created by audit == 0
service identity before == after
timer state before == after
health reported literally
```

- [ ] **Step 6: Replace aggregate evidence and decision**

Keep `status=blocked` and `allowedNextPlan=none` unless all existing mechanical gates pass. Scan for database URLs, tokens, user IDs, character names, realms, raw profiles, and source URLs before staging.

- [ ] **Step 7: Commit**

```bash
git add \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/runtime-readonly-audit.json \
  artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/phase1-decision.json
git commit -m "evidence(gear): correct catalog migration audit result"
```

### Task 4: Bind the corrected result to the current control plane and packet

**Files:**
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/plans/2026-07-28-equipment-simulator-target-architecture.md`
- Modify: `docs/plans/2026-07-28-equipment-simulator-catalog-migration-phase0-implementation.md`
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/requirement.json`
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/evidence.json`
- Test: `tests/project-state.test.js`

**Interfaces:**
- Consumes: corrected immutable report ID and mechanical decision
- Produces: one non-conflicting Phase 0 conclusion and one complete Harness packet

- [ ] **Step 1: Write the failing current-truth assertion**

Assert the corrected report identity, family counts, `status=blocked`, and `allowedNextPlan=none`. The test must reject the old claim that 356 Browse variants mapped.

- [ ] **Step 2: Run the assertion and verify RED**

Run:

```bash
node --test tests/project-state.test.js
```

Expected: FAIL against the old report identity/counts.

- [ ] **Step 3: Update current truth and Phase 0 packet**

Record the corrected root cause: the legacy release mixes Browse rows, Exact evidence, placeholders, and previews; generic leaderboard rank is not equipment rank; real Browse rows still lack dedicated track-rank authority. Preserve the no-runtime-activation and zero-write boundaries.

- [ ] **Step 4: Run focused verification**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_audit_store_test \
  tests.gear_catalog_migration_audit_cli_test \
  tests.gear_release_store_test \
  tests.postgres_personal_store_test \
  -v

node --test \
  tests/gear-catalog-callers-audit.test.js \
  tests/project-state.test.js \
  tests/project-harness.test.js \
  tests/backend-owner-map.test.js
```

- [ ] **Step 5: Commit the corrected packet**

Commit docs, requirement, evidence, and manifest only after all implementation/evidence bytes are final.

- [ ] **Step 6: Run clean-head Harness verification**

Run:

```bash
node scripts/project-harness.js --json --check \
  --requirement-file artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/requirement.json \
  --evidence-file artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/evidence.json \
  --manifest-file artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0/manifest.json

node scripts/verify-project.js \
  --profile harness \
  --release artifacts/releases/2026-07-28-equipment-simulator-catalog-migration-phase0
```

- [ ] **Step 7: Review, push, and wait for PR CI**

Review `origin/main...HEAD`, run `git diff --check`, push the existing branch, verify local/remote SHA parity, and wait for PR #101 `Project Harness / verify` to reach a successful terminal state. Do not merge.

## Exit Criteria

This correction is complete only when:

1. observed exact rows and generic ranking fields cannot contribute to Browse mapping;
2. item and variant exclusions are explicit, deterministic, counted, and target-scope justified;
3. the corrected production audit is aggregate-only, zero-write, pointer-stable, and bound to exact committed tool hashes;
4. remaining Browse rank/static/template/spec/resource/caller blockers are reported literally;
5. the same Phase 0 Harness packet and PR CI pass on the corrected branch HEAD.

