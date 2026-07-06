# Current-Season M+ AOE Recommended Gear Template Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent current-season M+ AOE recommended gear template generator that fills the `baseline` subtype for all 40 specs without pretending the result is an absolute BiS proof.

**Architecture:** Keep real community gear templates and generated recommendations separate. The final recommended winner is written to the existing `cache.websim_community_gear_templates` read model with `sourceKey=season_recommendation` and `templateSlot=baseline`, while candidate ledgers and SimC evidence live in new recommendation-specific tables. `simc_preset` and `default_template` stay as compatibility/diagnostic sources but no longer define the target baseline source.

**Tech Stack:** Python backend, PostgreSQL cache schema, SimulationCraft profile generation, Raider.IO-derived community talent read model, `unittest`, Node test runner for frontend read-model expectations, systemd sync service.

## 2026-07-06 First-Version Delivery Status

- First version shipped to production with `sourceKey=season_recommendation` and `sourceName=当前赛季大秘境 AOE 推荐模板`.
- Production sync entrypoint: `server/season_recommended_gear_sync.py`; cloud one-shot service: `wow-season-recommended-gear-sync.service`.
- First-version generation policy: use the current verified complete real community gear winner as the recommendation seed, attach a verified Raider.IO / WCL community talent anchor, and keep every generated recommendation at `recommendationConfidence=provisional`.
- Production verification: PG active `season_recommendation|complete|40 rows|40 specs`; `/api/data/health` `communityImportTemplates.coveredTemplateSlotCount=80`, `missingTemplateSlotCount=0`, `seasonRecommendation.completeSpecCount=40`, `provisionalSpecCount=40`, `blockedSpecCount=0`.
- API verification: all 40 specs passed `/api/websim/gear?compact=1&mode=initial` smoke with one real community template plus one `season_recommendation` baseline template, 16 importable slots, and no missing display name/icon metadata.
- Remaining work: add recommendation-specific candidate ledger tables and SimC optimizer scoring before marking any spec `recommendationConfidence=verified`.

---

## Product Contract

- The import UI still has two top-level groups: user-saved templates and community templates.
- The community template group contains two subtypes:
  - `community_best`: one real community gear winner per spec, target `40/40`.
  - `baseline`: one generated current-season recommendation per spec, target `40/40`.
- The health target remains `80/80` community import display slots.
- Recommended baseline templates are named `当前赛季大秘境 AOE 推荐模板`, not `BiS`, `最佳配装`, or `毕业配装`.
- A generated template may be importable with `status=complete` while its recommendation confidence is `provisional`; that still fills the baseline slot, but health/admin must show confidence separately.
- DPS specs can graduate to `recommendationConfidence=verified` after SimC winner validation under M+ AOE settings.
- Tanks, healers, and augmentation evoker start as `recommendationConfidence=provisional` unless a role-specific objective function is explicitly implemented and validated.

## Current State

- PG production currently gets baseline candidates from `cache.websim_profile_presets`.
- `PostgresCacheStore.build_community_gear_templates()` reads those presets and emits `sourceKey=simc_preset`.
- The older SQLite path has `build_default_community_gear_template()`, which emits `sourceKey=default_template` from verified current-season gear candidates plus `mplus_mixed_route` stat weights.
- `select_best_baseline_gear_templates()` already routes baseline-like sources into `baselineTemplates`; this is the correct integration point.
- `build_community_gear_template_preflight()` now counts `community_best + baseline` as the `communityImport` target, which is also the correct health target.

## Source Policy

Use this source priority for baseline selection:

1. `season_recommendation`: generated current-season M+ AOE recommendation.
2. `default_template`: legacy deterministic fallback, kept only while the new generator is rolling out.
3. `baseline_template`: any older explicit baseline rows.
4. `simc_preset`: SimulationCraft preset import compatibility.
5. `baseline_blocked`: API placeholder only; never persisted as a complete source.

The real community subtype must continue rejecting all baseline-like sources, including `season_recommendation`.

## Evidence Payload Contract

Every `season_recommendation` winner must carry this payload shape:

```json
{
  "templateSlot": "baseline",
  "sourceKey": "season_recommendation",
  "sourceName": "当前赛季大秘境 AOE 推荐模板",
  "scenarioKey": "mplus_aoe",
  "recommendationConfidence": "provisional",
  "rolePolicy": {
    "role": "healer",
    "objectiveKey": "community_consensus_plus_simc_sanity",
    "reason": "non-DPS specs need role-specific scoring before verified recommendation claims"
  },
  "talentAnchor": {
    "sourceKey": "raiderio",
    "classKey": "priest",
    "specKey": "discipline",
    "heroKey": "voidweaver",
    "templateId": "community-talent-priest-discipline-voidweaver",
    "evidenceTier": "verified"
  },
  "gearCatalogRevision": "gear-catalog-revision",
  "simcRuntimeRevision": "simulationcraft-build",
  "optimizerRunId": "season-rec-2026-07-06T000000Z",
  "candidateCount": 144,
  "simcRunCount": 24,
  "score": {
    "primaryMetric": "dps",
    "primaryValue": 1234567.0,
    "deltaPctVsLegacyBaseline": 3.2
  },
  "blockers": [],
  "warnings": [
    "trinket and healer value models are confidence-limited"
  ]
}
```

If a spec cannot produce a complete importable profile, keep `status=blocked`, `sourceStatus=blocked`, `canApplyGear=false`, and write the blocker into the recommendation run summary. Do not write a partial `season_recommendation` as the visible baseline winner unless it has a complete 16-slot profile.

## File Map

- Modify `server/websim_payload.py`
  - Add `SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY`.
  - Add the source key to `BASELINE_GEAR_TEMPLATE_SOURCE_KEYS`.
  - Prefer `season_recommendation` in `baseline_gear_template_sort_key()`.
  - Add source summary display for `season_recommendation`.
- Modify `server/postgres_cache_sync.py`
  - Add the source key to `BASELINE_GEAR_TEMPLATE_SOURCE_KEYS` and `BAD_REAL_GEAR_TEMPLATE_SOURCE_KEYS`.
  - Extend preflight rows to expose recommendation confidence and run id when the baseline row is a season recommendation.
- Modify `server/postgres_cache_store.py`
  - Read/write `season_recommendation` rows through the existing `cache.websim_community_gear_templates` table.
  - Add generator entrypoints that build recommendation rows from PG-native catalog/talent/stat/SimC evidence.
- Create `server/season_recommended_gear.py`
  - Pure recommendation builder, candidate pruning, evidence normalization, and role policy helpers.
- Create `server/season_recommended_gear_sync.py`
  - CLI/sync entrypoint for scheduled and targeted generation.
- Create `server/migrations/postgres/0013_season_recommended_gear.sql`
  - Candidate ledger and run summary tables.
- Create `server/wow-season-recommended-gear-sync.service`
  - Systemd unit for cloud refresh.
- Modify tests:
  - `tests/websim_payload_test.py`
  - `tests/postgres_cache_sync_test.py`
  - `tests/postgres_cache_store_test.py`
  - `tests/postgres_only_scripts_test.py`
  - `tests/news_backend_test.py`
- Modify docs:
  - `docs/community-template-import-full-chain-runbook.md`
  - `docs/gear-simulation-full-chain-runbook.md`

---

### Task 1: Source Key And Baseline Selection

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `server/postgres_cache_sync.py`
- Test: `tests/websim_payload_test.py`
- Test: `tests/postgres_cache_sync_test.py`

- [ ] **Step 1: Write the failing baseline selection test**

Add a test that proves `season_recommendation` wins over `default_template` and `simc_preset`, while remaining outside `communityTemplates`.

```python
def test_season_recommendation_is_preferred_baseline_source(self):
    templates = [
        {
            "id": "simc",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "simc_preset",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "updatedAt": "2026-07-01T00:00:00+00:00",
            "name": "SimC preset",
            "gearItems": [],
        },
        {
            "id": "default",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "default_template",
            "sourceStatus": "verified",
            "status": "complete",
            "readySlotCount": 16,
            "updatedAt": "2026-07-02T00:00:00+00:00",
            "name": "默认模板",
            "gearItems": [],
        },
        {
            "id": "recommended",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "season_recommendation",
            "sourceStatus": "synced",
            "status": "complete",
            "readySlotCount": 16,
            "updatedAt": "2026-07-03T00:00:00+00:00",
            "name": "当前赛季大秘境 AOE 推荐模板",
            "gearItems": [],
        },
    ]

    self.assertFalse(self.websim_payload.is_real_community_gear_template(templates[2]))
    baseline = self.websim_payload.select_best_baseline_gear_templates(templates)

    self.assertEqual(len(baseline), 1)
    self.assertEqual(baseline[0]["sourceKey"], "season_recommendation")
```

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_season_recommendation_is_preferred_baseline_source -v
```

Expected: fails because `season_recommendation` is not yet classified as a baseline source.

- [ ] **Step 2: Implement source constants and priority**

Add this constant near `DEFAULT_GEAR_TEMPLATE_SOURCE_KEY`:

```python
SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY = "season_recommendation"
SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME = "当前赛季大秘境 AOE 推荐模板"
```

Change baseline source sets:

```python
BASELINE_GEAR_TEMPLATE_SOURCE_KEYS = {
    SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY,
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "baseline_template",
    "simc_preset",
    "baseline_blocked",
}
```

Change the baseline sort key to:

```python
def baseline_gear_template_source_priority(source_key):
    return {
        SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY: 40,
        DEFAULT_GEAR_TEMPLATE_SOURCE_KEY: 30,
        "baseline_template": 20,
        "simc_preset": 10,
        "baseline_blocked": 0,
    }.get(str(source_key or "").strip(), 0)


def baseline_gear_template_sort_key(template):
    source_key = gear_template_source_key(template)
    return (
        baseline_gear_template_source_priority(source_key),
        1 if template.get("status") == "complete" else 0,
        1 if template.get("sourceStatus") in {"synced", "verified"} else 0,
        int(template.get("readySlotCount") or 0),
        str(template.get("updatedAt") or ""),
        str(template.get("name") or ""),
    )
```

Mirror the source key in `server/postgres_cache_sync.py`:

```python
BASELINE_GEAR_TEMPLATE_SOURCE_KEYS = {
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "season_recommendation",
    "baseline_template",
    "simc_preset",
}
BAD_REAL_GEAR_TEMPLATE_SOURCE_KEYS = {
    "",
    DEFAULT_GEAR_TEMPLATE_SOURCE_KEY,
    "season_recommendation",
    "baseline_template",
    "simc_preset",
    "manual_fixture",
    "fallback",
    "source_reference",
}
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_season_recommendation_is_preferred_baseline_source tests.postgres_cache_sync_test.PostgresCacheSyncTest.test_gear_template_preflight_counts_community_import_baseline_slots -v
```

Expected: both pass.

---

### Task 2: Recommendation Evidence Tables

**Files:**
- Create: `server/migrations/postgres/0013_season_recommended_gear.sql`
- Modify: `tests/postgres_schema_test.py`
- Modify: `server/migrations/postgres/data_copy_plan.py` only if shadow-copy tests require explicit ignore/copy behavior.

- [ ] **Step 1: Write schema expectations**

Add assertions that the migration creates these tables:

- `cache.season_recommended_gear_runs`
- `cache.season_recommended_gear_candidates`

Expected columns for `cache.season_recommended_gear_runs`:

- `id text primary key`
- `scenario_key text not null`
- `season_revision text not null default ''`
- `simc_runtime_revision text not null default ''`
- `status text not null default 'blocked'`
- `total_spec_count integer not null default 0`
- `complete_spec_count integer not null default 0`
- `verified_spec_count integer not null default 0`
- `provisional_spec_count integer not null default 0`
- `blocked_spec_count integer not null default 0`
- `payload_json jsonb not null default '{}'::jsonb`
- `started_at timestamptz not null default now()`
- `finished_at timestamptz`

Expected columns for `cache.season_recommended_gear_candidates`:

- `id text primary key`
- `run_id text not null references cache.season_recommended_gear_runs(id) on delete cascade`
- `class_key text not null`
- `spec_key text not null`
- `candidate_key text not null`
- `status text not null default 'blocked'`
- `score numeric`
- `rank integer not null default 0`
- `gear_items_json jsonb not null default '[]'::jsonb`
- `evidence_json jsonb not null default '{}'::jsonb`
- `blockers_json jsonb not null default '[]'::jsonb`
- `created_at timestamptz not null default now()`

- [ ] **Step 2: Create the migration**

Use this SQL:

```sql
CREATE TABLE IF NOT EXISTS cache.season_recommended_gear_runs (
    id text PRIMARY KEY,
    scenario_key text NOT NULL,
    season_revision text NOT NULL DEFAULT '',
    simc_runtime_revision text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'blocked',
    total_spec_count integer NOT NULL DEFAULT 0,
    complete_spec_count integer NOT NULL DEFAULT 0,
    verified_spec_count integer NOT NULL DEFAULT 0,
    provisional_spec_count integer NOT NULL DEFAULT 0,
    blocked_spec_count integer NOT NULL DEFAULT 0,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
);

CREATE TABLE IF NOT EXISTS cache.season_recommended_gear_candidates (
    id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES cache.season_recommended_gear_runs(id) ON DELETE CASCADE,
    class_key text NOT NULL,
    spec_key text NOT NULL,
    candidate_key text NOT NULL,
    status text NOT NULL DEFAULT 'blocked',
    score numeric,
    rank integer NOT NULL DEFAULT 0,
    gear_items_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    evidence_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    blockers_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_season_recommended_gear_candidates_run_candidate
ON cache.season_recommended_gear_candidates (run_id, class_key, spec_key, candidate_key);

CREATE INDEX IF NOT EXISTS idx_cache_season_recommended_gear_candidates_spec
ON cache.season_recommended_gear_candidates (class_key, spec_key, status, rank);

GRANT SELECT, INSERT, UPDATE, DELETE ON cache.season_recommended_gear_runs TO wow_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON cache.season_recommended_gear_candidates TO wow_app;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0013_season_recommended_gear',
    'Add current-season M+ AOE recommended gear candidate and run ledger tables'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
```

- [ ] **Step 3: Run schema tests**

Run:

```bash
python3 -m unittest tests.postgres_schema_test -v
```

Expected: passes.

---

### Task 3: Pure Recommendation Template Builder

**Files:**
- Create: `server/season_recommended_gear.py`
- Test: `tests/season_recommended_gear_test.py`

- [ ] **Step 1: Write builder tests**

Cover these cases:

- complete 16-slot candidate emits `sourceKey=season_recommendation`, `templateSlot=baseline`, `status=complete`, `canApplyGear=true`.
- missing slot emits a blocked result and does not return an importable winner.
- healer/tank/augmentation role policy emits `recommendationConfidence=provisional`.
- DPS with SimC score emits `recommendationConfidence=verified`.

Use this minimal test shape:

```python
def test_builds_complete_recommended_baseline_template(self):
    from server.season_recommended_gear import build_season_recommended_gear_template

    gear_items = [
        {"slot": slot, "simcSlot": slot, "itemId": f"item-{slot}", "id": f"item-{slot}", "simcReady": True}
        for slot in self.websim_payload.CANONICAL_GEAR_SLOTS
    ]
    template = build_season_recommended_gear_template(
        class_key="mage",
        spec_key="frost",
        gear_items=gear_items,
        evidence={
            "optimizerRunId": "season-rec-test",
            "scenarioKey": "mplus_aoe",
            "talentAnchor": {"sourceKey": "raiderio", "evidenceTier": "verified"},
            "gearCatalogRevision": "gear-catalog-test",
            "simcRuntimeRevision": "simc-test",
            "candidateCount": 3,
            "simcRunCount": 3,
            "role": "damage",
            "score": {"primaryMetric": "dps", "primaryValue": 1000.0},
        },
    )

    self.assertEqual(template["sourceKey"], "season_recommendation")
    self.assertEqual(template["payload"]["templateSlot"], "baseline")
    self.assertEqual(template["status"], "complete")
    self.assertEqual(template["readySlotCount"], 16)
    self.assertEqual(template["missingSlots"], [])
    self.assertEqual(template["payload"]["templateEvidence"]["recommendationConfidence"], "verified")
    self.assertTrue(template["canApplyGear"])
```

- [ ] **Step 2: Implement the pure builder**

The builder imports existing helpers from `server.websim_payload`:

- `CANONICAL_GEAR_SLOTS`
- `COMMUNITY_TEMPLATE_REVISION`
- `build_websim_gear_lines`
- `gear_template_signature`
- `gear_template_slot_coverage`
- `normalize_source_refs`
- `gear_template_source_ref`
- `season_expires_at`
- `utc_now`
- `slugify`

Required public functions:

```python
SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_KEY = "season_recommendation"
SEASON_RECOMMENDED_GEAR_TEMPLATE_SOURCE_NAME = "当前赛季大秘境 AOE 推荐模板"
SEASON_RECOMMENDED_GEAR_SCENARIO_KEY = "mplus_aoe"


def season_recommended_role_policy(class_key, spec_key, role=""):
    normalized_role = str(role or "").strip().lower()
    if normalized_role in {"tank", "healer", "support"} or (class_key, spec_key) == ("evoker", "augmentation"):
        return {
            "role": normalized_role or "support",
            "objectiveKey": "community_consensus_plus_simc_sanity",
            "recommendationConfidence": "provisional",
            "reason": "non-DPS specs need role-specific scoring before verified recommendation claims",
        }
    return {
        "role": normalized_role or "damage",
        "objectiveKey": "dps_mplus_aoe",
        "recommendationConfidence": "verified",
        "reason": "DPS recommendation is ranked by M+ AOE SimC score",
    }
```

`build_season_recommended_gear_template()` must:

- normalize class/spec keys.
- compute canonical coverage with `gear_template_slot_coverage()`.
- reject missing canonical slots by returning `None` plus a blocker helper, or by raising a local `ValueError` that the sync layer converts to blocked.
- build `rawString` using `build_websim_gear_lines()`.
- put the full evidence payload under `payload.templateEvidence`.
- set `templateSlot=baseline`.
- set `status=complete` and `sourceStatus=synced` only when 16 slots are covered and raw SimC gear lines exist.

- [ ] **Step 3: Run builder tests**

Run:

```bash
python3 -m unittest tests.season_recommended_gear_test -v
```

Expected: passes.

---

### Task 4: PG Candidate Reader And Pruner

**Files:**
- Modify: `server/postgres_cache_store.py`
- Test: `tests/postgres_cache_store_test.py`

- [ ] **Step 1: Write candidate reader tests**

Create a fake PG connection rowset that includes:

- verified current-season raid/dungeon/tier variants.
- one wrong-season or `source_reference` candidate.
- one non-SimC-ready candidate.

Assert that the candidate reader:

- groups candidates by canonical slot.
- rejects wrong-season/source-reference/non-SimC-ready rows.
- caps normal slots to a deterministic small number.
- keeps trinket candidates by item level plus source quality, not secondary stat weights only.

- [ ] **Step 2: Implement `recommended_gear_candidate_items()`**

Add a PG-store method with this behavior:

```python
def recommended_gear_candidate_items(self, class_key, spec_key, season=None, per_slot_limit=8):
    class_key = slugify(class_key, "")
    spec_key = slugify(spec_key, "")
    if not class_key or not spec_key:
        return {}
    with self.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.name, i.slot, i.item_level, i.payload_json,
                       v.id, v.slot, v.item_level, v.simc_options_json, v.status,
                       v.blockers_json, v.payload_json, v.updated_at
                FROM cache.websim_gear_variants v
                JOIN cache.websim_items i ON i.id = v.item_id
                WHERE v.status = 'verified'
                  AND COALESCE(v.payload_json->>'simcReady', '') IN ('true', '1', 'yes')
                ORDER BY v.item_level DESC, i.name, v.id
                """
            )
            rows = cur.fetchall()
    candidates_by_slot = {slot: [] for slot in CANONICAL_GEAR_SLOTS}
    for row in rows:
        item = self._gear_variant_candidate_item(row, class_key, spec_key, season)
        if not item:
            continue
        for slot in gear_candidate_slots(item, class_key, spec_key):
            if slot in candidates_by_slot:
                candidates_by_slot[slot].append(gear_candidate_for_slot(item, slot))
    return {
        slot: limit_replacement_candidates(unique_gear_candidates(items), per_slot_limit)
        for slot, items in candidates_by_slot.items()
    }
```

Use existing candidate helpers instead of inventing new slot compatibility rules.

- [ ] **Step 3: Run PG store tests**

Run:

```bash
python3 -m unittest tests.postgres_cache_store_test.PostgresCacheStoreTest.test_recommended_gear_candidate_items_filters_to_verified_current_season_simc_ready -v
```

Expected: passes.

---

### Task 5: Talent Anchor Selection

**Files:**
- Modify: `server/postgres_cache_store.py`
- Test: `tests/postgres_cache_store_test.py`

- [ ] **Step 1: Write talent anchor tests**

Assert that the selector:

- prefers active verified Raider.IO community talent rows for the same class/spec.
- ignores `websim_baseline`, `manual_fixture`, `fallback`, stale expired rows, and wrong class/spec.
- records the selected `heroKey`, `templateId`, `sourceKey`, and `evidenceTier`.

- [ ] **Step 2: Implement `recommended_gear_talent_anchor()`**

Read from the existing community talent PG table and return this shape:

```python
{
    "sourceKey": "raiderio",
    "classKey": "mage",
    "specKey": "frost",
    "heroKey": "frostfire",
    "templateId": "community-talent-template-id",
    "evidenceTier": "verified",
    "updatedAt": "2026-07-06T00:00:00+00:00"
}
```

If no verified community talent exists, return a blocker:

```python
{
    "status": "blocked",
    "reason": "missing verified Raider.IO community talent anchor",
    "nextAction": "refresh_community_talent_templates"
}
```

- [ ] **Step 3: Run talent anchor tests**

Run:

```bash
python3 -m unittest tests.postgres_cache_store_test.PostgresCacheStoreTest.test_recommended_gear_talent_anchor_prefers_verified_raiderio_template -v
```

Expected: passes.

---

### Task 6: Candidate Assembly And SimC Scoring

**Files:**
- Modify: `server/season_recommended_gear.py`
- Create: `tests/season_recommended_gear_test.py`
- Modify: `server/postgres_cache_store.py`

- [ ] **Step 1: Write deterministic assembly tests**

Assert:

- tier/catalyst slots are selected as valid set combinations, not one slot at a time.
- unique-equipped rings/trinkets do not duplicate beyond their limit.
- embellishment count does not exceed the allowed cap.
- off-hand is marked occupied for two-handed specs and still counts toward 16 canonical slots.

- [ ] **Step 2: Implement candidate assembly**

Add pure functions:

```python
def assemble_recommended_gear_candidates(candidates_by_slot, class_key, spec_key, max_candidates=24):
    """Return complete 16-slot candidate gear lists ordered by deterministic pre-score."""
```

Rules:

- Start with top candidates per canonical slot.
- Generate tier-set combinations before non-tier filler.
- Keep trinket pair combinations explicit.
- Enforce unique-equipped limits.
- Enforce embellishment cap from existing enhancement/mod-option helpers.
- Return only candidates where `gear_template_slot_coverage()` has no missing slots.

- [ ] **Step 3: Add SimC scoring wrapper**

The first scoring wrapper can use a fake runner in tests and the real runner in production:

```python
def score_recommended_gear_candidates(candidates, simc_runner, profile_context):
    scored = []
    for candidate in candidates:
        result = simc_runner(candidate, profile_context)
        if not result.get("ok"):
            scored.append({"candidate": candidate, "status": "blocked", "blockers": result.get("errors") or ["simc failed"]})
            continue
        scored.append({
            "candidate": candidate,
            "status": "verified",
            "score": float(result.get("dps") or result.get("primaryValue") or 0),
            "rawResult": result,
        })
    return sorted(scored, key=lambda row: row.get("score") or 0, reverse=True)
```

- [ ] **Step 4: Run assembly/scoring tests**

Run:

```bash
python3 -m unittest tests.season_recommended_gear_test -v
```

Expected: passes.

---

### Task 7: Sync Entrypoint And Health Integration

**Files:**
- Create: `server/season_recommended_gear_sync.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/postgres_cache_sync.py`
- Modify: `server/news_backend.py`
- Test: `tests/postgres_only_scripts_test.py`
- Test: `tests/postgres_cache_sync_test.py`
- Test: `tests/news_backend_test.py`

- [ ] **Step 1: Write sync entrypoint tests**

Assert:

- PG-only mode calls the new PG-native sync function.
- SQLite mode rejects the entrypoint with the same fail-closed pattern as other PG-only jobs.
- sync result contains `totalSpecCount`, `completeSpecCount`, `verifiedSpecCount`, `provisionalSpecCount`, `blockedSpecCount`, and `communityImportTemplates`.

- [ ] **Step 2: Implement `sync_season_recommended_gear_postgres()`**

The sync function should:

- create a run id such as `season-recommended-gear-YYYYMMDDTHHMMSSZ`.
- loop the expected 40 specs.
- read talent anchor.
- read candidate items.
- assemble candidates.
- score/prune candidates according to role policy.
- build one template with `build_season_recommended_gear_template()`.
- write the winner through `replace_community_gear_templates()`.
- write the run and candidate ledger rows.
- return a summary payload.

- [ ] **Step 3: Update health summaries**

Add `seasonRecommendation` details under `community_templates.details`, without replacing `communityImportTemplates`.

Required details:

```json
{
  "sourceKey": "season_recommendation",
  "status": "partial",
  "totalSpecCount": 40,
  "completeSpecCount": 32,
  "verifiedSpecCount": 18,
  "provisionalSpecCount": 14,
  "blockedSpecCount": 8,
  "blockedSpecs": ["priest:discipline"],
  "lastRunId": "season-recommended-gear-20260706T000000Z"
}
```

- [ ] **Step 4: Run targeted backend tests**

Run:

```bash
python3 -m unittest tests.postgres_only_scripts_test tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.news_backend_test -v
```

Expected: passes.

---

### Task 8: Scheduled Refresh And Deployment Runbook

**Files:**
- Create: `server/wow-season-recommended-gear-sync.service`
- Modify: `docs/community-template-import-full-chain-runbook.md`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Test: `tests/deploy_lighthouse_test.py` if service-file deployment expectations are encoded there.

- [ ] **Step 1: Add service file**

Use the same lock discipline as other sync jobs:

```ini
[Unit]
Description=WOW Mini Program current-season recommended gear sync
After=network-online.target wow-backend.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/wow-mini-program
EnvironmentFile=/etc/wow-mini-program.env
ExecStart=/usr/bin/flock -w 7200 /run/lock/wow-mini-program-sync.lock /usr/bin/python3 /opt/wow-mini-program/server/season_recommended_gear_sync.py
User=wow
Group=wow
Nice=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Update runbooks**

Document:

- `season_recommendation` is the target baseline source.
- `simc_preset` and `default_template` are compatibility/fallback diagnostics.
- `communityImportTemplates` still owns `80/80`.
- non-DPS recommendations may be complete/importable but confidence-limited.
- production acceptance requires health details and one sampled `/api/websim/gear` payload to show `baselineTemplates[0].sourceKey=season_recommendation`.

- [ ] **Step 3: Run full verification before deployment**

Run:

```bash
python3 -m unittest tests.news_backend_test tests.postgres_cache_sync_test tests.postgres_cache_store_test tests.postgres_only_scripts_test tests.websim_payload_test tests.season_recommended_gear_test -v
node --test tests/builds-page.test.js tests/frontend-api-client.test.js
python3 -m py_compile server/news_backend.py server/websim_payload.py server/postgres_cache_store.py server/postgres_cache_sync.py server/season_recommended_gear.py server/season_recommended_gear_sync.py
git diff --check
```

Expected: Python tests pass, Node tests pass, py_compile passes, and `git diff --check` exits 0.

- [ ] **Step 4: Production rollout**

After tests pass:

1. Deploy code to the known cloud server with the existing deploy script.
2. Apply migration `0013_season_recommended_gear`.
3. Run the sync service once manually.
4. Smoke `/health`.
5. Smoke `/api/data/health` and confirm `communityImportTemplates.totalTemplateSlotCount=80`.
6. Smoke sample specs, including at least one DPS and one healer:
   - `mage:frost`
   - `priest:discipline`
   - `deathknight:frost`
7. Confirm sampled payloads show importable `baselineTemplates` with `sourceKey=season_recommendation`, or a blocked reason recorded in `seasonRecommendation.blockedSpecs`.

## Acceptance Criteria

- `community_best` remains real community only and stays `40/40`.
- `baseline` target is `40/40` with `season_recommendation` as the preferred source.
- `communityImportTemplates` reaches `80/80` only when both subtypes are covered.
- No `season_recommendation` row appears in `communityTemplates`.
- `simc_preset` no longer defines the product baseline target, but remains available as a lower-priority compatibility source during rollout.
- Every generated template has item icons, Chinese names, SimC-ready gear lines, and a complete evidence payload.
- Non-DPS specs are not presented as absolute SimC-verified BiS unless the role objective has been implemented and verified.
