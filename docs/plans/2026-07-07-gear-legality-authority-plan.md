# Gear Legality Authority Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish a backend-owned authority layer that keeps every class/spec gear library, imported template, observed community template, baseline template, and saved gear snapshot accurate, legal, and auditable for the current live game version.

**Architecture:** Split "can this spec legally equip this item?" from "is this item a good recommendation?". Battle.net item metadata, SimulationCraft/client data, and current-season catalog evidence feed a backend legality evaluator; Raider.IO/WCL observed gear can only be validated samples, never rule authority. Frontend and template import flows consume backend legality results instead of duplicating weapon, slot, enchant, gem, or template trust rules.

**Tech Stack:** Python backend, PostgreSQL/SQLite cache read models, Battle.net Game Data API, SimulationCraft/client-derived data when verified, existing WebSim gear payloads, WeChat mini-program frontend, `unittest`, Node test runner, `/api/data/health` audit output.

## Current Case Summary

This plan comes from the 2026-07-07 Elemental Shaman investigation:

- The current `SPEC_WEAPON_EQUIPMENT_RULES` hardcoded Elemental Shaman as `Staff / Dagger / One-Handed Mace`, which confused preferred weapons with the full legal class weapon set.
- Elemental Shaman should allow `Staff`, `Dagger`, `Fist Weapon`, `One-Handed Axe`, and `One-Handed Mace` in main hand, plus `Shield` or `Held In Off-hand` in off hand where the mode allows it.
- The enhancement sheet problem was not missing options in the catalog. The first/import payload was intentionally light and did not include every slot's `socketOptions`, `enchantOptions`, and `embellishmentOptions`; the UI must fetch slot detail before building the configuration sheet.
- Raider.IO observed gear should not define legality. It is evidence that a player snapshot existed, but the imported template still needs legal-slot, source-trust, and current-season validation.
- Seeing a legal but suspicious setup, such as a suboptimal tier slot choice, should not be treated as the same class of failure as an illegal weapon or invalid off-hand combination.

## Design Principles

1. Backend is the source of truth for gear legality.
2. Frontend may mirror backend fields for instant interaction, but must not own legality rules.
3. Community observed templates are samples to audit, not sources of rules.
4. Hardcoded rules are temporary overrides only when they have source references, tests, and an explicit retirement path.
5. Legality blockers fail closed; recommendation-quality concerns become warnings unless they make the template non-executable.
6. Current-season item pool, class/spec rules, item metadata, and template trust are separate dimensions and should produce separate audit reasons.
7. Initial payloads stay small; slot detail remains the narrow API for complete socket/enchant/embellishment options.

## Authority Source Policy

Use this precedence when building or validating rules:

1. **Battle.net Game Data API**
   - Authoritative for item identity, `inventory_type`, `item_class`, `item_subclass`, item-level metadata, icons, names, and any exposed class/spec fields after schema verification.
   - Good source for item metadata; not yet confirmed as a complete source for per-spec weapon mode rules.
2. **SimulationCraft / client-derived DB data**
   - Candidate source for class weapon proficiencies, dual-wield/two-hand modes, shield/held-offhand eligibility, and specialization-specific exceptions.
   - Must be verified before becoming an automated generator input.
3. **Current project catalog and season manifests**
   - Authoritative for the active season item pool, verified variants, source trust, item-level tracks, crafted variants, sockets, enchants, embellishments, and serializer-ready gear lines.
4. **Raider.IO / WCL observed data**
   - Validates that a community/player snapshot exists.
   - Cannot define the legal equipment universe.
   - Can produce template quality warnings, stale-source warnings, and observed-sample audit records.
5. **Manual override**
   - Last resort for gaps in machine-readable sources.
   - Must include `sourceRefs`, `checkedAt`, `gameVersion` or `seasonRevision`, and tests.
   - Must show up in health as an override, not silent truth.

## Data Model

Create a normalized internal model even if the first implementation stores it as generated Python constants:

```python
SpecGearAuthority = {
    "classKey": "shaman",
    "specKey": "elemental",
    "status": "verified",
    "ruleVersion": "2026-07-07-live",
    "sourceRefs": [
        {"type": "battle_net_class", "ref": "shaman", "checkedAt": "..."},
        {"type": "simc_or_client_db", "ref": "weapon_proficiency", "checkedAt": "..."}
    ],
    "primaryStatKey": "intellect",
    "armorTypes": ["Mail"],
    "slotRules": {
        "main_hand": {
            "inventoryTypes": ["INVTYPE_WEAPON", "INVTYPE_WEAPONMAINHAND", "INVTYPE_2HWEAPON"],
            "weaponTypes": ["Staff", "Dagger", "Fist Weapon", "One-Handed Axe", "One-Handed Mace"],
            "modes": ["staff", "one_hand_plus_shield_or_holdable"]
        },
        "off_hand": {
            "inventoryTypes": ["INVTYPE_SHIELD", "INVTYPE_HOLDABLE"],
            "weaponTypes": ["Shield", "Held In Off-hand"],
            "modes": ["one_hand_plus_shield_or_holdable"]
        }
    },
    "templatePolicy": {
        "illegalBlocksImport": True,
        "suboptimalTierSlotsWarnOnly": True
    }
}
```

The evaluator should return structured results:

```python
GearLegalityResult = {
    "status": "legal" | "blocked" | "warning",
    "reason": "weapon_type_not_allowed_for_spec",
    "severity": "blocker",
    "slot": "main_hand",
    "itemId": 123456,
    "sourceRefs": [...],
}
```

## Implementation Phases

### Phase 0: Land The Current Case Patch

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `pages/builds/detail.js`
- Test: `tests/websim_payload_test.py`
- Test: `tests/builds-page.test.js`
- Modify: `docs/roadmap/ideas.md`

**Steps:**

1. Keep the Elemental Shaman weapon rule fix as a narrow temporary patch.
2. Keep the enhancement sheet change that fetches missing selected-slot details before building socket/enchant/embellishment rows.
3. Keep regression coverage for Elemental Shaman axe/fist/mace/staff legality and slot-detail hydration.
4. Run:

```bash
python3 -m unittest tests.websim_payload_test
node --test tests/builds-page.test.js
git diff --check
```

**Expected result:** The current reported case is fixed without claiming the whole legality system is solved.

### Phase 1: Authority Source Spike

**Files:**
- Create: `docs/plans/2026-07-07-gear-legality-source-spike.md`
- Modify if needed: `docs/gear-database-governance.md`

**Steps:**

1. Verify Battle.net Game Data schemas for:
   - `/data/wow/playable-class/index`
   - `/data/wow/playable-class/{classId}`
   - `/data/wow/playable-specialization/index`
   - `/data/wow/playable-specialization/{specId}`
   - item and item-class endpoints already used by the project
2. Record whether class/spec endpoints expose weapon proficiencies, armor type, or only display metadata.
3. Inspect available SimulationCraft/client-derived data for weapon proficiencies and specialization equipment modes.
4. Produce a source decision table:
   - field
   - preferred source
   - fallback source
   - confidence
   - update cadence
   - implementation blocker
5. Do not save network-fetched content to disk without explicit approval.

**Expected result:** A documented source map before building a generator, so the project does not expand page-derived hardcoding.

### Phase 2: Extract A Backend Legality Evaluator

**Files:**
- Create: `server/gear_legality.py`
- Test: `tests/gear_legality_test.py`
- Modify: `server/websim_payload.py`

**Steps:**

1. Move class/spec primary stat, armor, slot, and weapon-mode decisions behind pure functions.
2. Keep existing `SPEC_WEAPON_EQUIPMENT_RULES` available as a temporary input, but rename its role in code comments to "manual override".
3. Add `gear_legality_for_item(class_key, spec_key, slot, item_payload)`.
4. Add `gear_legality_for_template(class_key, spec_key, gear_by_slot, enhancement_by_slot)`.
5. Return structured blocker/warning reasons instead of boolean-only compatibility.

**Required tests:**

```bash
python3 -m unittest tests.gear_legality_test
python3 -m unittest tests.websim_payload_test
```

**Key cases:**

- Elemental Shaman allows one-handed axe and fist weapon in main hand.
- Elemental Shaman rejects two-handed mace if the source says it is not valid for the current spec rule.
- Enhancement Shaman rejects shield and held-offhand in off hand.
- Fury Warrior rejects shield and one-handed off-hand under the current rule.
- Caster specs reject off-hand weapons but allow held-offhand where eligible.
- Legal but suspicious tier-slot choices return warning, not blocker.

### Phase 3: Apply Legality To Candidate Libraries

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `server/postgres_cache_store.py`
- Modify: `server/postgres_cache_sync.py`
- Test: `tests/websim_payload_test.py`
- Test: `tests/postgres_cache_store_test.py`
- Test: `tests/postgres_cache_sync_test.py`

**Steps:**

1. Filter `replacementCandidates` through `gear_legality_for_item`.
2. Attach `legalityStatus`, `legalityReasons`, and `sourceTrust` to backend candidate objects where useful for admin/debug output.
3. Keep player-facing compact payload clean; do not show blocked candidates as selectable.
4. Preserve examples of excluded candidates for health/admin.
5. Ensure source filtering still distinguishes:
   - official current-season item pool
   - crafted items
   - observed-only items
   - baseline recommendation items
   - stale or partial variants

**Expected result:** Every class/spec candidate library is generated from the same legality evaluator.

### Phase 4: Apply Legality To Template Import And Save

**Files:**
- Modify: `server/websim_payload.py`
- Modify: `server/news_backend.py`
- Modify: `server/postgres_cache_store.py`
- Test: `tests/websim_payload_test.py`
- Test: `tests/news_backend_test.py`
- Test: `tests/postgres_cache_store_test.py`

**Steps:**

1. Validate imported Raider.IO/WCL/community templates before exposing them as complete.
2. Validate `season_recommendation` baseline templates before writing or promoting them.
3. Validate user-saved `gearBySlot` snapshots before converting them into SimC profile lines.
4. Block illegal slots with specific reasons; if the template still has legal gear slots, expose it as `partial` and allow partial import while skipping illegal slots. Only mark the whole template `blocked` when no legal slots remain or the source itself is non-importable:
   - invalid weapon type
   - invalid off-hand mode
   - wrong armor type
   - wrong inventory slot
   - source item not in trusted current-season pool where required
   - invalid socket/enchant/embellishment selection
5. Keep recommendation-quality concerns separate:
   - suspicious tier slot choice
   - unusual embellishment distribution
   - stale observed sample
   - lower-confidence baseline source

**Expected result:** Template status reflects whether it is legal and executable, not merely whether it came from a community source.

### Phase 5: Preserve Slot Detail Enhancement Contract

**Files:**
- Modify: `pages/builds/detail.js`
- Modify: `pages/builds/websim-api.js` only if request contract needs extension
- Test: `tests/builds-page.test.js`

**Steps:**

1. Keep `mode=initial` lightweight.
2. Before opening the enhancement sheet, fetch `mode=slot` for selected slots whose current payload lacks concrete socket/enchant/embellishment options.
3. Do not infer enchant capacity from frontend-held weapon-type lists if the backend can provide slot capability.
4. If an item becomes illegal after gear swap or source refresh, clear stale draft enhancement for that slot and surface the backend blocker.
5. Keep `buildGearEnhancementSheet(...)` as the draft-edit boundary and `confirmGearEnhancementSheet()` as the commit path.

**Expected result:** The sheet can show full valid configuration options without bloating the initial gear payload.

### Phase 6: Health, Admin, And Audit Output

**Files:**
- Modify: `server/news_backend.py`
- Modify: `server/websim_payload.py`
- Modify: `server/postgres_cache_sync.py`
- Test: `tests/news_backend_test.py`
- Test: `tests/websim_payload_test.py`

**Add health component:**

```json
{
  "gear_legality_authority": {
    "status": "verified",
    "totalSpecs": 40,
    "verifiedSpecs": 40,
    "manualOverrideSpecs": 3,
    "blockedTemplateCount": 0,
    "warningTemplateCount": 12,
    "excludedCandidateCount": 48,
    "examples": [
      {
        "classKey": "shaman",
        "specKey": "elemental",
        "slot": "main_hand",
        "itemId": 123456,
        "reason": "weapon_type_not_allowed_for_spec"
      }
    ]
  }
}
```

**Rules:**

- Missing source authority is not `verified`.
- Manual override can be acceptable for user-facing operation, but health must disclose it.
- Illegal promoted templates should make the component `blocked`.
- Warning-only recommendation quality concerns should make the component `partial` only if they exceed a defined threshold.

### Phase 7: Full-Coverage Verification And Deployment

**Files:**
- Add or extend traversal scripts only if an existing script cannot cover the checks.
- Modify docs:
  - `docs/gear-simulation-full-chain-runbook.md`
  - `docs/gear-database-governance.md`

**Local verification:**

```bash
python3 -m unittest tests.gear_legality_test
python3 -m unittest tests.websim_payload_test
python3 -m unittest tests.news_backend_test
python3 -m unittest tests.postgres_cache_store_test
python3 -m unittest tests.postgres_cache_sync_test
node --test tests/builds-page.test.js
git diff --check
```

**Runtime smoke:**

- `/health`
- `/api/data/health`
- `/api/websim/gear?compact=1&mode=initial` for all 40 specs
- selected `mode=slot` calls for `main_hand`, `off_hand`, `neck`, `finger1`, `legs`
- template import for:
  - `shaman:elemental`
  - `shaman:enhancement`
  - `warrior:fury`
  - `deathknight:frost`
  - one healer caster with shield
  - one caster with held-offhand

**Deployment rule:** Run cloud sync/deploy only after the user explicitly asks for deployment or live verification.

## Acceptance Criteria

- All 40 specs have a legality authority record.
- Candidate libraries contain no selectable item that the backend evaluator marks `blocked`.
- Community observed templates cannot become `complete` if they contain illegal gear.
- Baseline `season_recommendation` templates cannot become visible if they contain illegal gear.
- User-saved templates remain structured snapshots and are rejected by the backend serializer if stale or illegal.
- Enhancement sheet fetches missing slot detail before rendering full socket/enchant/embellishment options.
- `/api/data/health` reports source coverage, manual overrides, blocked templates, warning templates, and excluded candidate examples.
- No frontend code path hardcodes weapon rules, armor rules, class/spec legality, or item-name exceptions.

## Risks And Non-Goals

- Battle.net class/spec endpoints may not expose complete equip rules. The plan must not assume they do until Phase 1 proves it.
- SimC/client-derived data may require generated tables or build artifacts. Do not add downloads or generated files without explicit approval.
- This plan does not try to prove BiS. It proves legal/executable templates and flags recommendation-quality concerns separately.
- This plan does not replace the existing gear catalog governance; it adds a legality authority layer used by catalog, templates, and serializer.
- This plan does not broaden the initial gear payload. Slot detail remains the expansion mechanism for heavy option lists.

## Suggested Commit Slices

1. `fix: patch elemental shaman gear case`
2. `docs: map gear legality authority sources`
3. `feat: add backend gear legality evaluator`
4. `feat: apply gear legality to candidate libraries`
5. `feat: validate imported and saved gear templates`
6. `feat: expose gear legality health audit`
7. `test: add full spec legality traversal coverage`
