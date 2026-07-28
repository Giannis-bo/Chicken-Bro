# Equipment Simulator Track Authority Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The repository Harness owns execution topology, evidence and closure; do not dispatch subagents for this task.

**Goal:** Replace the Phase 0 audit's universal Browse rank requirement with a versioned progression authority that maps regular upgrade tracks, crafted quality and Ascendant states without inventing rank or changing runtime data.

**Architecture:** Add one pure `gear_track_authority` module that resolves the active season/rule binding and validates legacy Browse rows into a discriminated `ProgressionState`. Keep PostgreSQL access in the existing bounded read-only store, then update the pure migration audit to group legacy rows into canonical Browse candidates and separate crafted-stat combinations. The CLI binds the exact active season/rule revision, and a new task-scoped release packet records a zero-write production rerun while leaving Phase 1 blocked.

**Tech Stack:** Python 3 standard library, `unittest`, PostgreSQL/psycopg through the existing read-only store, Node Project Harness, JSON release evidence.

**Execution status (2026-07-28):** Tasks 1-5 and the production read-only audit are complete. The current report maps 1265/1313 canonical Browse candidates, preserves 438 crafted EnhancementSelection associations, records zero writes and a stable generation-24 pointer, and keeps Phase 1 blocked with `allowedNextPlan=none`. Final closure truth is owned by the task evidence packet.

## Global Constraints

- Work only on `codex/equipment-simulator-track-authority`; never implement on `main`.
- Keep `allowedNextPlan=none` unless the complete fresh Phase 0 decision mechanically says otherwise; this slice must not manufacture a passing decision.
- Do not add or alter PostgreSQL schema, Gear Release rows, Community Release rows, active Manifest pointers, public APIs, Taro code, Resolver behavior, serializers, timers, services or SimC runtime.
- Do not infer rank from item level alone, generic `payload.rank`, display text, tooltip text or bonus IDs. A regular-track rank may be supplied only by the exact season/rule authority record after both track key and governed maximum item level match.
- `upgrade_track` requires positive `rank == maxRank`; `crafted_quality` and `ascendant` forbid rank.
- Crafted-stat rows are EnhancementSelection evidence and must not create duplicate BrowseVariant identities.
- The 48 known missing-static-stat rows remain explicit problems.
- Every PostgreSQL session remains `BEGIN READ ONLY` with `statement_timeout <= 30000ms`, `lock_timeout <= 5000ms`, bounded batches and zero writes.
- Production output is aggregate-only, sample-bounded and contains no database URL, profile, account, character, realm, token or raw template.
- No dependency install, third-party download, runtime deployment or production write is authorized.
- PR #101 is the base dependency. Do not open or verify a new PR against `main` until that task lands and the new diff contains exactly one complete Track Authority release packet.

---

### Task 1: Freeze the Track Authority Harness contract

**Files:**
- Create: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/requirement.json`
- Create: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/evidence.json`
- Create: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/manifest.json`
- Modify: `tests/project-state.test.js`

**Interfaces:**
- Consumes: approved design `docs/plans/2026-07-28-equipment-simulator-track-authority-correction.md`.
- Produces: one Strict, `implementation_allowed`, `pg_read_model` requirement and a truthful in-progress packet with manual acceptance disabled.

- [x] **Step 1: Write the failing requirement/current-truth tests**

Add assertions that load the new requirement and current contract:

```javascript
assert.equal(trackAuthorityRequirement.status, 'implementation_allowed')
assert.equal(trackAuthorityRequirement.classification, 'Strict')
assert.equal(trackAuthorityContract.path, 'docs/plans/2026-07-28-equipment-simulator-track-authority-correction.md')
assert.equal(
  trackAuthorityContract.implementationPlan,
  'docs/plans/2026-07-28-equipment-simulator-track-authority-implementation.md'
)
```

The test must fail because the new requirement packet and task contract do not exist.

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
node --test tests/project-state.test.js
```

Expected: FAIL on the missing Track Authority requirement, not on JSON syntax.

- [x] **Step 3: Add the requirement and packet bindings**

Create a requirement with:

```json
{
  "schemaVersion": 1,
  "slug": "equipment-simulator-track-authority-correction",
  "classification": "Strict",
  "status": "implementation_allowed",
  "goal": "Classify legacy Browse rows through a versioned progression authority, separate crafted-stat selections, and rerun the bounded Phase 0 audit without changing runtime data, schemas, APIs, releases or pointers.",
  "releaseTrigger": "pg_read_model",
  "manualAcceptanceContract": {
    "required": false,
    "requiredItemIds": []
  },
  "rollback": ["code_rollback"]
}
```

Complete all existing Strict fields using the approved design:

- current truth includes project-state, roadmap, plans index, target architecture, Track Authority design, Phase 0 plan, owner maps, Harness and verification matrix;
- `mustChange` names the pure authority, read-only projection, audit grouping, evidence and control-plane updates;
- `mustNotChange` names runtime/API/schema/release/pointer/UI/SimC surfaces;
- evidence requires TDD, zero-write production audit, stable pointer and unchanged other blockers;
- ownership makes `server/gear_track_authority.py` the pure progression-rule owner and keeps SQL in `server/gear_catalog_audit_store.py`.

Create an evidence v2 packet at `implementation_allowed` with pending verification/closure identities, `runtime.status=not_applicable`, no false passing verification, manual acceptance not applicable, and cleanup pending only for the future isolated production audit. Create the standard v0.6.4 manifest bound to this requirement/evidence path.

- [x] **Step 4: Run the tests and verify GREEN**

Run:

```bash
node --test tests/project-state.test.js
```

Expected: PASS with the new requirement reachable from current truth.

- [x] **Step 5: Commit the requirement gate**

```bash
git add \
  artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction \
  tests/project-state.test.js
git commit -m "chore(gear): gate track authority correction"
```

---

### Task 2: Implement the pure versioned Track Authority

**Files:**
- Create: `server/gear_track_authority.py`
- Create: `tests/gear_track_authority_test.py`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `tests/backend-owner-map.test.js`

**Interfaces:**
- Consumes: binding `{seasonRevision, gearRuleRevision}` and one aggregate legacy Browse row.
- Produces:
  - `track_authority_for_binding(binding: Any) -> dict[str, Any]`
  - `resolve_legacy_browse_progression(binding: Any, row: Any) -> dict[str, Any]`
  - constants `TRACK_AUTHORITY_SCHEMA_REVISION` and `TRACK_AUTHORITY_RULE_REVISION`.

- [x] **Step 1: Write failing binding and regular-track tests**

Use literal current binding:

```python
CURRENT_BINDING = {
    "seasonRevision": "season-17-f131dd36ddf1",
    "gearRuleRevision": "gear-rule-matrix-v1",
}
```

Assert that `track_authority_for_binding(CURRENT_BINDING)` returns a verified, versioned rule set with source refs, and:

```python
resolved = resolve_legacy_browse_progression(
    CURRENT_BINDING,
    {
        "difficultyKey": "hero",
        "trackKey": "hero",
        "itemLevel": 276,
        "trackRank": 0,
        "rank": 527,
        "slot": "head",
        "sourceType": "raid",
    },
)
self.assertEqual(resolved["status"], "verified")
self.assertEqual(resolved["progressionState"], {
    "kind": "upgrade_track",
    "trackKey": "hero",
    "rank": 6,
    "maxRank": 6,
})
self.assertNotEqual(resolved["progressionState"]["rank"], 527)
```

Also assert that an unknown season/rule binding and an item-level mismatch are blocked with stable problem codes.

Add owner-map assertions:

```javascript
assert.equal(
  catalogAuditOwner.owners[0].trackAuthorityOwner,
  'server/gear_track_authority.py'
)
assert.ok(
  catalogAuditOwner.owners[0].characterization.includes(
    'tests/gear_track_authority_test.py'
  )
)
```

- [x] **Step 2: Run the authority tests and verify RED**

Run:

```bash
python3 -m unittest tests.gear_track_authority_test -v
node --test tests/backend-owner-map.test.js
```

Expected: both commands FAIL because the module and owner bindings do not exist.

- [x] **Step 3: Implement the minimum authority records**

Define six immutable records:

```python
("champion", "upgrade_track", 263, 6)
("hero", "upgrade_track", 276, 6)
("myth", "upgrade_track", 289, 6)
("crafted_myth", "crafted_quality", 285, None)
("void_upgrade", "ascendant", 298, None)
("crafted_void_upgrade", "ascendant", 295, None)
```

Each record includes the exact season/rule revision, public `trackKey`, progression kind, item level, conditional max rank, eligible source/slot/origin metadata, explicit source refs and `evidenceStatus=verified`.

Register the module/test under the Phase 0 audit owner in `docs/backend-owner-map.json`, and as a pure, unconsumed Track Authority foundation in the canonical gear domain of `docs/project-owner-map.json`.

Resolution rules:

- only exact binding matches may use the records;
- regular tracks synthesize `rank=maxRank=6` only when item level matches the bound record;
- a nonzero dedicated `trackRank` must equal the record max rank;
- generic `rank` is never read;
- crafted quality requires `sourceType=crafted` and a nonempty `simcOptions.crafted_stats`;
- ordinary Ascendant requires main-hand/trinket slot, a governed void-instance source, or verified observed Ascendant evidence;
- crafted Ascendant requires `sourceType=crafted`, main/off-hand slot, nonempty `crafted_stats` and `hasTrackEvidence=true`;
- crafted/Ascendant rows with dedicated rank are blocked as rank-forbidden;
- unknown track, malformed row, item-level mismatch and insufficient eligibility return deterministic problems.

- [x] **Step 4: Add crafted and Ascendant tests**

Assert these literal outcomes:

```python
self.assertEqual(crafted["progressionState"], {
    "kind": "crafted_quality",
    "trackKey": "myth",
    "qualityKey": "radiance_max",
})
self.assertEqual(crafted_void["progressionState"], {
    "kind": "ascendant",
    "trackKey": "void_upgrade",
    "originKind": "crafted_quality",
})
self.assertNotIn("rank", crafted["progressionState"])
self.assertNotIn("rank", crafted_void["progressionState"])
```

Add negative tests for forbidden rank and unsupported Ascendant eligibility.

- [x] **Step 5: Run authority tests and verify GREEN**

Run:

```bash
python3 -m unittest tests.gear_track_authority_test -v
node --test tests/backend-owner-map.test.js
```

Expected: all Track Authority and owner-map tests PASS.

- [x] **Step 6: Commit the pure authority**

```bash
git add \
  server/gear_track_authority.py \
  tests/gear_track_authority_test.py \
  docs/backend-owner-map.json \
  docs/project-owner-map.json \
  tests/backend-owner-map.test.js
git commit -m "feat(gear): add versioned track authority"
```

---

### Task 3: Project only the evidence Track Authority needs

**Files:**
- Modify: `server/gear_catalog_audit_store.py:422-480`
- Modify: `tests/gear_catalog_audit_store_test.py`

**Interfaces:**
- Consumes: immutable Gear Release variants and sources.
- Produces each aggregate variant row with `sourceType`, `hasVoidInstanceSource`, `hasTrackEvidence` and the existing structural fields; no raw source row or personal data.

- [x] **Step 1: Write the failing projection test**

Extend the fixed variant fixture with `source_type`, track evidence and one source row from governed instance `1305`. Assert:

```python
self.assertEqual(variant["sourceType"], "raid")
self.assertTrue(variant["hasVoidInstanceSource"])
self.assertTrue(variant["hasTrackEvidence"])
self.assertNotIn("sourceRows", variant)
```

Retain the existing assertions for `BEGIN READ ONLY`, bounded timeouts, rollback, zero commits and zero write statements.

- [x] **Step 2: Run the store test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.gear_catalog_audit_store_test.GearCatalogAuditStoreTest.test_snapshot_classifies_legacy_variant_families_without_ranking_leakage \
  -v
```

Expected: FAIL because the three authority evidence fields are absent.

- [x] **Step 3: Extend the fixed read-only query**

Add `source_type` and one bounded boolean evidence projection:

```sql
EXISTS (
    SELECT 1
    FROM cache.websim_gear_release_sources source
    WHERE source.release_id = variant.release_id
      AND source.item_id = variant.item_id
      AND source.instance_id = '1305'
) AS has_void_instance_source
```

Project:

```python
{
    "sourceType": _text(source_type),
    "hasVoidInstanceSource": has_void_instance_source is True,
    "hasTrackEvidence": (
        isinstance(payload.get("trackEvidence"), list)
        and bool(payload.get("trackEvidence"))
    ),
}
```

Do not project source labels, raw source payloads, ranking evidence or item names beyond the existing aggregate contract.

- [x] **Step 4: Run the full store tests and verify GREEN**

Run:

```bash
python3 -m unittest tests.gear_catalog_audit_store_test -v
```

Expected: all store tests PASS; query count stays at or below 12 and writes stay zero.

- [x] **Step 5: Commit the projection**

```bash
git add server/gear_catalog_audit_store.py tests/gear_catalog_audit_store_test.py
git commit -m "fix(gear): project track authority evidence"
```

---

### Task 4: Make Phase 0 mapping progression-aware

**Files:**
- Modify: `server/gear_catalog_migration_audit.py:17-420`
- Modify: `tests/gear_catalog_migration_audit_test.py`

**Interfaces:**
- Consumes: current binding with season/rule revision, projected aggregate variant rows, and `resolve_legacy_browse_progression`.
- Produces `equipment-simulator-catalog-migration-audit-v2` with legacy and canonical counts, progression-family counts, crafted enhancement counts and bounded problem evidence.

- [x] **Step 1: Write failing regular/Ascendant behavior tests**

Update the complete fixture to current Hero `276` and exact binding. Add tests proving:

- missing dedicated rank maps to authority rank 6;
- generic `rank=527` never overrides rank 6;
- mismatched dedicated rank blocks;
- ordinary Ascendant maps only with slot/source/observed evidence;
- crafted/Ascendant rank is forbidden.

Expected stable problem codes:

```text
TRACK_AUTHORITY_BINDING_UNSUPPORTED
TRACK_AUTHORITY_ILEVEL_MISMATCH
TRACK_AUTHORITY_RANK_MISMATCH
TRACK_AUTHORITY_RANK_FORBIDDEN
TRACK_AUTHORITY_ASCENDANT_ELIGIBILITY_UNPROVEN
```

- [x] **Step 2: Write the failing crafted-collapse test**

Generate 54 crafted-myth item groups and 19 crafted-Ascendant item groups, each with six literal `crafted_stats` values. Assert:

```python
self.assertEqual(result["legacyBrowseVariantTotal"], 438)
self.assertEqual(result["canonicalBrowseVariantTotal"], 73)
self.assertEqual(result["craftedEnhancementSelectionRowCount"], 438)
self.assertEqual(result["collapsedCraftedVariantRowCount"], 365)
self.assertEqual(result["progressionCounts"]["crafted_quality"]["canonicalCandidateCount"], 54)
self.assertEqual(result["progressionCounts"]["ascendant"]["craftedCanonicalCandidateCount"], 19)
```

Add one duplicate `crafted_stats` row and prove it blocks that candidate instead of silently deduplicating.

- [x] **Step 3: Write the failing static-stat regression**

Create exactly 48 otherwise valid Browse rows without static stats. Assert:

```python
self.assertEqual(
    result["problemCounts"]["CATALOG_VARIANT_STATIC_STATS_MISSING"],
    48,
)
```

The test must keep all 48 problems even though problem samples remain capped at 20.

- [x] **Step 4: Run audit tests and verify RED**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_test -v
```

Expected: FAIL on missing progression/canonical/crafted counts.

- [x] **Step 5: Implement progression grouping**

Import the pure resolver. Before Browse mapping, collect verified observed Ascendant evidence item IDs from `exact_instance` rows at item level `298` with nonempty static stats.

For every Browse row:

1. call `resolve_legacy_browse_progression`;
2. prefix its problems with `rows.variants[index]`;
3. build a canonical identity tuple from `itemId` and the canonical progression state;
4. for crafted-origin rows, require one nonempty `crafted_stats` per row and reject duplicate choices;
5. for non-crafted rows, reject multiple rows for one canonical identity;
6. count a canonical candidate as mapped only when its authority, static stats, bonus IDs, item identity and enhancement association are all valid.

Return both compatibility and new fields:

```python
{
    "schemaRevision": "gear-catalog-mapping-audit-v2",
    "variantTotal": len(variants),
    "browseVariantTotal": legacy_browse_total,
    "legacyBrowseVariantTotal": legacy_browse_total,
    "canonicalBrowseVariantTotal": canonical_candidate_total,
    "mappedBrowseVariantCount": mapped_candidate_total,
    "mappedVariantCount": mapped_candidate_total,
    "craftedEnhancementSelectionRowCount": crafted_enhancement_rows,
    "collapsedCraftedVariantRowCount": collapsed_crafted_rows,
    "progressionCounts": progression_counts,
}
```

Bump the aggregate audit schema to `equipment-simulator-catalog-migration-audit-v2`; identity hashing must include the new deterministic fields.

- [x] **Step 6: Run audit tests and verify GREEN**

Run:

```bash
python3 -m unittest tests.gear_track_authority_test tests.gear_catalog_migration_audit_test -v
```

Expected: all authority and mapping tests PASS.

- [x] **Step 7: Commit progression-aware mapping**

```bash
git add server/gear_catalog_migration_audit.py tests/gear_catalog_migration_audit_test.py
git commit -m "fix(gear): audit canonical progression variants"
```

---

### Task 5: Bind the CLI to the active season/rule revision

**Files:**
- Modify: `scripts/gear-catalog-migration-audit.py:784-828`
- Modify: `tests/gear_catalog_migration_audit_cli_test.py`

**Interfaces:**
- Consumes: `activeBinding.manifest.seasonRevision` and `manifest.dependencyVector.gearRuleRevision`.
- Produces: a content-addressed v2 report with the exact Track Authority revision in `catalogMapping.runtimeSnapshotIdentity`.

- [x] **Step 1: Write the failing CLI binding test**

Use fixture binding:

```python
"seasonRevision": "season-17-f131dd36ddf1",
"dependencyVector": {
    "gearRuleRevision": "gear-rule-matrix-v1",
}
```

Assert:

```python
self.assertEqual(
    report["catalogMapping"]["runtimeSnapshotIdentity"]["trackAuthorityRuleRevision"],
    "midnight-season-1-track-authority-v1",
)
self.assertEqual(
    report["catalogMapping"]["trackAuthority"]["seasonRevision"],
    "season-17-f131dd36ddf1",
)
```

Add a wrong `gearRuleRevision` fixture and assert literal blocked authority status.

- [x] **Step 2: Run CLI tests and verify RED**

Run:

```bash
python3 -m unittest tests.gear_catalog_migration_audit_cli_test -v
```

Expected: FAIL because the CLI does not pass season/rule binding.

- [x] **Step 3: Pass the exact binding and record identity**

Call `audit_catalog_mapping` with:

```python
{
    "manifestRevision": manifest.get("manifestRevision"),
    "gearReleaseId": gear_release.get("releaseId"),
    "seasonRevision": manifest.get("seasonRevision"),
    "gearRuleRevision": _mapping(
        manifest.get("dependencyVector")
    ).get("gearRuleRevision"),
}
```

Copy only the public rule revision and authority status into runtime snapshot identity. Keep raw dependency vectors hashed and keep database connection data out of the report.

- [x] **Step 4: Run the full focused Python suite**

Run:

```bash
python3 -m unittest \
  tests.gear_track_authority_test \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_audit_store_test \
  tests.gear_catalog_migration_audit_cli_test \
  tests.gear_release_store_test \
  tests.postgres_personal_store_test \
  -v
```

Expected: all tests PASS with zero failures.

- [x] **Step 5: Commit CLI integration**

```bash
git add scripts/gear-catalog-migration-audit.py tests/gear_catalog_migration_audit_cli_test.py
git commit -m "fix(gear): bind catalog audit track authority"
```

---

### Task 6: Rerun the aggregate production audit and close local evidence

**Files:**
- Create: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/runtime-readonly-audit.json`
- Create: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/phase1-decision.json`
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/evidence.json`
- Modify: `artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/manifest.json`
- Modify: `docs/plans/2026-07-28-equipment-simulator-track-authority-correction.md`
- Modify: `docs/plans/2026-07-28-equipment-simulator-track-authority-implementation.md`
- Modify: `docs/plans/2026-07-28-equipment-simulator-target-architecture.md`
- Modify: `docs/plans/README.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-state.json`
- Modify: `docs/gear-database-governance.md`
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `tests/project-state.test.js`

**Interfaces:**
- Consumes: exact committed audit tool source, active production Manifest generation, existing caller inventory and read-only PostgreSQL.
- Produces: one new aggregate report/decision and a task-scoped local-verified Harness packet; it does not modify production.

- [x] **Step 1: Commit a clean audit-tool checkpoint**

Verify:

```bash
git status --short
git diff --check
```

Commit any remaining tracked implementation/docs changes before the remote run. Record the exact commit and SHA-256 of:

```text
server/gear_track_authority.py
server/gear_catalog_migration_audit.py
server/gear_catalog_audit_store.py
scripts/gear-catalog-migration-audit.py
```

- [x] **Step 2: Run the exact committed tools in an isolated remote directory**

Use one `mktemp -d` directory on `wow-lighthouse`, transfer the exact committed repository snapshot without modifying `/opt/wow-mini-program`, and run one transient collected systemd unit with:

```text
User=ubuntu
EnvironmentFile=/etc/wow-backend.env
WOW_DATABASE_RUNTIME=postgres_only
statement_timeout_ms=15000
lock_timeout_ms=1000
batch_size=500
```

The audit command must use the current tracked caller inventory, write only inside the isolated directory, and print only aggregate identity/status. Copy the finished aggregate report into the new task release directory, then remove the exact isolated directory and collect the transient unit.

- [x] **Step 3: Verify zero-write and pointer stability**

Check the report literally:

```bash
jq '{
  reportId,
  status,
  catalog: {
    legacyBrowseVariantTotal: .catalogMapping.legacyBrowseVariantTotal,
    canonicalBrowseVariantTotal: .catalogMapping.canonicalBrowseVariantTotal,
    mappedBrowseVariantCount: .catalogMapping.mappedBrowseVariantCount,
    craftedEnhancementSelectionRowCount: .catalogMapping.craftedEnhancementSelectionRowCount,
    collapsedCraftedVariantRowCount: .catalogMapping.collapsedCraftedVariantRowCount,
    problemCounts: .catalogMapping.problemCounts
  },
  writes: .catalogMapping.sourceQueryMetrics.writes,
  pointerStable: .catalogMapping.runtimeSnapshotIdentity.pointerStable
}' artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction/runtime-readonly-audit.json
```

Required invariant outcomes:

- `legacyBrowseVariantTotal=1678`;
- `canonicalBrowseVariantTotal=1313`;
- `craftedEnhancementSelectionRowCount=438`;
- `collapsedCraftedVariantRowCount=365`;
- `CATALOG_VARIANT_STATIC_STATS_MISSING=48`;
- writes `0`;
- pointer stable `true`.

Do not predeclare the mapped count or Ascendant eligibility count; record the measured values literally.

- [x] **Step 4: Write the mechanical Phase 1 decision**

The new decision must bind the new report ID. Keep:

```json
{
  "status": "blocked",
  "allowedNextPlan": "none"
}
```

unless every Phase 0 gate independently passes. Community Release absence, 40/40 blocked initial candidates, partial resource peaks and unresolved callers remain separate blockers and therefore cannot be cleared by Track Authority progress.

- [x] **Step 5: Update current truth and stable governance**

Record measured counts and the new report ID in project-state and roadmap. Mark the Track Authority correction `audit_rerun_complete_blocked` if the report remains blocked. Update:

- target architecture links to the new current report/decision;
- plans index status;
- gear governance so regular tracks require rank 6, crafted quality/Ascendant forbid fabricated rank, and the pure module owns the versioned table;
- owner maps with the final report path and test list;
- design and implementation plan status/evidence links.

Do not delete or rewrite the original Phase 0 packet; it remains historical evidence for PR #101.

- [x] **Step 6: Update evidence truthfully**

Set the new packet to `local_verified` only after fresh tests. Runtime identity remains not applicable because no code was activated. Candidate deployment and manual acceptance remain not applicable. Record:

- exact tool commit and file hashes;
- production service/pointer before and after;
- zero writes and collected transient unit;
- literal mapped/blocked progression counts;
- unchanged other Phase 0 gates;
- cleanup status complete;
- branch dependency on PR #101.

- [x] **Step 7: Run final focused verification**

Run:

```bash
python3 -m unittest \
  tests.gear_track_authority_test \
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

Expected: all focused tests PASS.

- [x] **Step 8: Create the clean verification checkpoint**

Record the focused test results, keep the Harness verification entry at `not_run`, commit all evidence/control-plane changes and confirm the worktree is clean. Then run:

```bash
node scripts/verify-project.js \
  --profile harness \
  --release artifacts/releases/2026-07-28-equipment-simulator-track-authority-correction
```

Expected: Harness PASS for the clean checkpoint HEAD. Do not run frontend/runtime candidate verification because this slice changes no active runtime or UI consumer.

- [x] **Step 9: Bind final Harness evidence**

Change only the Harness verification entry from `not_run` to `pass`, include the command and observed summary, commit that evidence-only change, then rerun the same Harness command on the new clean HEAD.

Expected: Harness PASS again, now on the exact final evidence HEAD.

- [x] **Step 10: Perform local CR**

Review the task-only diff from base commit `1c6ad24b` to HEAD. Check:

- no runtime consumer imports the new authority;
- no SQL write or schema change exists;
- generic rank and ungoverned item-level inference remain prohibited;
- crafted rows collapse without losing enhancement associations;
- problem samples remain bounded and sensitive fields absent;
- report/decision/project-state identities agree;
- old Phase 0 packet remains unchanged.

Fix valid findings and rerun the affected verification.

- [x] **Step 11: Commit any CR correction and reverify**

If CR produces a correction, commit only the corrected task files, update the evidence verification identity/result, and rerun the affected focused tests plus Harness on the new clean HEAD. If CR finds nothing, do not create an empty commit.

Do not push or open the new PR while PR #101 remains unmerged, because the `origin/main...HEAD` diff would contain two task packets and must fail closed.
