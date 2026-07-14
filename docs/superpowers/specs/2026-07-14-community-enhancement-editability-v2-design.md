# Community Enhancement Editability v2 Design

**Date:** 2026-07-14

**Status:** approved by user; implementation allowed; implementation and runtime verification not started

**Supersedes:** [Community Template Enhancement Import Design v1](2026-07-13-community-template-enhancement-import-design.md) for socket-capacity derivation, unmatched enhancement presentation, and editability semantics. PR #85 remains immutable historical implementation and deployment evidence.

**Harness:** [community-enhancement-editability requirement](../../../artifacts/releases/2026-07-14-community-enhancement-editability/requirement.json)

## 1. Concrete product contract

For the accepted Frost Mage community template, import must produce this state immediately:

| Type | Imported state | Editing contract |
| --- | --- | --- |
| Gems | `8/8` | All eight occurrences are normal selections. Any occupied socket can be replaced without first deleting another gem. Duplicate gem IDs remain separate occurrences. |
| Enchants | `6/8` | The six imported enchants are normal selections. Each eligible slot can replace, remove, or add an enchant within canonical constraints. |
| Embellishments | `2/2` | Both imported embellishments are normal selections. Either occupied embellishment slot can be replaced or removed; a third empty slot remains blocked while the total is two. |

The user interface must not show “继承事实”, “已继承”, “当前目录不可编辑”, or any equivalent implementation vocabulary. These are not useful player concepts. The player sees the imported configuration, normal editable rows, and only plain actionable warnings when current verified option coverage is missing.

This design intentionally corrects v1. The v1 behavior (`1/8 + 7` read-only gem facts and locked enhancement facts) was a safe fail-closed intermediate implementation, but it is not the target product behavior.

## 2. Correct evidence model

### 2.1 Static at request time, maintained dynamically at release time

The socket evidence chain is static for players:

- changing gear, importing a template, opening the sheet, or calling Resolve reads only the immutable Active Gear Release;
- those request paths do not call Battle.net, Raider.IO, SimC, Wowhead, or any other external source;
- periodic or differential candidate refresh may re-check upstream evidence, materialize changed facts into a new inactive release, compare it with the active release, and require controlled promotion.

“Static” therefore means versioned published truth, not hard-coded truth that can never be updated.

### 2.2 What the Midnight rule actually proves

Midnight Season 1 evidence distinguishes armor socketing from jewelry:

- `Radiant Jewelbinder` adds a socket only to an eligible Season 1 helm, bracer, or belt that does not already have one, and excludes PvP gear. It does not add sockets to rings or necks. This mechanism proves a total-capacity claim of one; a compatible stronger exact item/variant fact may still raise the final `max`.
- Midnight jewelry has a one-socket season floor. A particular item or exact variant may carry stronger intrinsic evidence, including two sockets, but that fact stays scoped to that item/variant.
- Observing two occupied gems on one ring proves a lower bound for that exact variant. It does not prove that every ring supports two sockets.

External research evidence used for this rule decision:

- [Radiant Jewelbinder tooltip and eligible slots](https://warcraft.wiki.gg/wiki/Radiant_Jewelbinder)
- [Independent item tooltip mirror for item 263897](https://www.wowdb.com/items/263897-radiant-jewelbinder)

Repository fixtures and candidate release evidence remain the executable authority. External pages are discovery/audit evidence, not request-time dependencies.

### 2.3 Every source is a minimum total, never an additive fragment

Every socket claim is normalized to:

```json
{
  "minimumTotal": 2,
  "scope": "exact_variant",
  "source": "official_item_payload | season_rule | simc_bonus | observed_gem_occupancy",
  "sourceRevision": "..."
}
```

The final capacity is the maximum compatible `minimumTotal`:

```text
socketCount = max(official socket entries,
                  season floor,
                  exact item/variant fact,
                  SimC socket bonus minimum,
                  observed occupied-gem lower bound)
```

Claims are never summed. For example, a jewelry floor of one plus an exact two-socket variant still yields two, not three. This prevents double-counting the same socket through multiple evidence channels.

Contradictions are release problems, not user-facing inherited facts. If an observed exact variant contains more occupied gems than the candidate authority can explain, the inactive candidate is blocked until the evidence is corrected. It must not silently publish a lower capacity or defer the contradiction to every player interaction.

## 3. Static socket authority

### 3.1 New pure owner

Create `server/gear_socket_authority.py` as the only pure owner of socket derivation. It defines:

```python
LEGACY_CAPABILITY_REVISION = "gear-capability-matrix-v1"
CAPABILITY_REVISION = "gear-capability-matrix-v2"
SUPPORTED_CAPABILITY_REVISIONS = (LEGACY_CAPABILITY_REVISION, CAPABILITY_REVISION)
SOCKET_FACT_SCHEMA_REVISION = "gear-socket-fact-v1"

count_payload_socket_entries(payload)
parse_simc_socket_bonus_minimums(output)
derive_item_socket_fact(...)
derive_variant_socket_fact(...)
materialize_gear_socket_facts(snapshot, ...)
```

The module is deterministic, side-effect-free, and does not mutate the source snapshot. It understands evidence semantics; it does not run subprocesses or query databases.

### 3.2 Candidate-time evidence acquisition

`server/gear_release_tool.py` acquires the bounded SimC bonus map once while constructing an inactive candidate (`show_bonus_ids=1`), passes the output into the pure parser, and materializes socket facts before snapshot validation, summary, and content hashing.

`server/gear_release_refresh.py` owns orchestration. If the probe fails, parsing is incomplete, or a socket contradiction exists, candidate construction fails closed and the active pointer remains unchanged.

No scheduled or deployment path may auto-promote a capability revision. `gear-capability-matrix-v1 -> v2` is a high-risk capability change and therefore requires a manual candidate cutover.

### 3.3 Materialized shape

Use the existing release JSONB payloads; no SQL migration is required. Each governed item and exact variant receives the final capacity plus internal provenance, for example:

```json
{
  "baseCapabilities": {
    "socketCount": 1
  },
  "socketEvidence": {
    "schemaRevision": "gear-socket-fact-v1",
    "authorityRevision": "gear-capability-matrix-v2",
    "minimumTotal": 1,
    "claims": [
      {
        "scope": "season_slot",
        "source": "midnight_s1_jewelry_floor",
        "minimumTotal": 1
      }
    ]
  },
  "variants": [
    {
      "capabilityOverrides": {
        "socketCount": 2
      },
      "socketEvidence": {
        "schemaRevision": "gear-socket-fact-v1",
        "authorityRevision": "gear-capability-matrix-v2",
        "minimumTotal": 2,
        "claims": [
          {
            "scope": "exact_variant",
            "source": "official_item_payload",
            "minimumTotal": 2
          }
        ]
      }
    }
  ]
}
```

The exact schema may follow the existing item/variant payload style, but the final facts, revisions, scope, and claim source must remain explicit and testable.

### 3.4 Capability revision in every identity

`capabilityRevision` joins the immutable dependency vector used by:

- runtime authority projection;
- active manifest compatibility;
- PostgreSQL Authority Context loading;
- release context;
- resolved gear signatures;
- stat/profile identities that already consume the dependency vector.

Rollout must avoid an availability gap:

1. deploy a reader that advertises v2 but supports both v1 and v2;
2. prove the current active v1 manifest still resolves identically;
3. generate and shadow an inactive v2 release;
4. manually switch the Manifest pointer;
5. retain v1 pointer rollback while the compatible reader is active.

A reader may reject an unknown future capability revision, but it must accept the explicit v1/v2 compatibility window.

### 3.5 Runtime consumption

For v2 releases, `server/pg_gear_authority_loader.py` accepts socket capacity only when the materialized fact has the expected schema and authority revision. Raw `gem_id` token count no longer raises capacity in the request path.

For v1 releases, the existing projection remains available only as a rollout/rollback compatibility branch. New v2 facts must not be interpreted with v1 heuristics.

`gear_resolver.py` and `gear_rule_matrix.py` continue to consume exact item/variant capabilities. They do not gain a second socket rule table. `constraints.slots[*].socketCount` remains the only frontend editing authority.

## 4. Frost Mage reference proof

The fixed reference template `observed_profile_mage_frost` must be frozen at candidate time with its `sourceKey`, `profileHash`, `gearHash`, Gear Release ID and Community Release ID. Its six socket-bearing instances must resolve to this ordered source-of-capacity vector:

```text
[head, neck, wrist, waist, finger1, finger2]
= [1, 2, 1, 1, 2, 1]
= 8 total sockets
```

This vector is a release fixture, not a frontend hard-code. It proves all important cases together:

- armor slot made eligible by the Season 1 rule;
- jewelry one-socket floor;
- exact two-socket jewelry fact;
- different capacities between two items of the same general jewelry family;
- eight valid canonical gem occurrences and a blocked ninth occurrence.

The enchant and embellishment acceptance values come from canonical option reconciliation, not socket capacity:

```text
enchant selected/eligible = 6/8
embellishment selected/max = 2/2
```

## 5. Editable canonical import

### 5.0 Preserve occurrences at source extraction

`server/raiderio_payload.py::raiderio_option_ids` currently deduplicates all option IDs through insertion-ordered dictionary keys. That behavior is appropriate for bonus IDs, but it destroys a legitimate pair of equal gem occurrences before reconciliation can see them.

The extractor must preserve `gems[]` order and multiplicity when building slash-separated `gem_id`; bonus and enchant callers may retain their existing deduplication contract. A template with `gem A, gem A` must reach the release/import pipeline as two occurrences, not one. Frontend `socketIndex` handling cannot repair data already lost at this boundary.

### 5.1 Reconciliation output

Community template values are clues until they match verified options. Import reads explicit `enhancementBySlot` and each observed gear item, then reconciles by exact normalized SimC value to stable option identity.

The canonical frontend representation is occurrence-aware:

```json
{
  "neck": {
    "gemOptionIds": ["gem-meta", "gem-secondary"]
  },
  "finger1": {
    "gemOptionIds": ["gem-secondary", "gem-secondary"],
    "enchantOptionId": "ring-enchant"
  },
  "back": {
    "enchantOptionId": "cloak-enchant",
    "embellishmentOptionId": "arcanoweave-lining"
  }
}
```

Array order is socket order. Duplicate values are preserved. Editing targets `{slot, enhancementType, socketIndex}` rather than “the gem with this ID”, so replacing one duplicate does not replace or remove another occurrence.

### 5.2 Full-capacity replacement

Full capacity is not a lock:

- At `8/8`, choosing a new gem for an occupied `socketIndex` replaces that occurrence and remains `8/8`.
- At `6/8`, choosing a new enchant for an occupied eligible slot replaces the existing enchant and remains `6/8`.
- At `2/2`, choosing a new embellishment for either occupied slot replaces it and remains `2/2`.
- At `2/2`, an unrelated empty third embellishment slot is disabled until one selected embellishment is removed.
- Selected options remain removable even when the global maximum is reached.

Unique-gem or unique-equipped rules still come from backend constraints and are evaluated over occurrences. Editability does not weaken legality.

### 5.3 Draft, Resolve, and atomic commit

Opening the sheet creates a draft from the latest verified snapshot. Local taps update only the draft.

- Closing without confirmation discards the draft.
- Confirm submits a Selection Intent and waits for the matching Resolve response.
- Only a verified response with the current request serial, intent version, and signature atomically replaces committed enhancement state from `resolvedSlots[*].selectedOptions`.
- A blocked, offline, malformed, or stale response preserves the previous verified committed state and keeps the draft available for correction.
- Save, Profile, SimC, summary counts, slot badges, and reopening the sheet all read committed verified state, never an unverified draft.

This removes the current risk where the UI commits local selections before the server has accepted them.

### 5.4 Gear replacement

Replacing gear in one slot:

1. clears only that slot's previous enhancement selections;
2. resolves the new exact item/variant;
3. rebuilds that slot's capacity from canonical constraints;
4. preserves all other slots;
5. removes any now-out-of-range socket occurrence (for example, a two-socket ring replaced by a one-socket ring);
6. exposes empty new socket rows when capacity grows.

The frontend never guesses new capacity from a slot name or old selection count.

### 5.5 Unknown values

If a community item is valid but one enhancement value cannot match current verified option authority:

- import the gear;
- leave that enhancement type empty in the normal editable selector;
- show a plain warning such as “模板中的 1 个宝石暂未被当前资料库识别，可重新选择”;
- record bounded telemetry/data-quality evidence;
- never put the raw value, a forged option ID, or an “inherited fact” into Intent, WXML, Profile, or SimC.

An unknown value is a catalog-coverage problem. A capacity contradiction is stricter and blocks the candidate release because every runtime consumer would otherwise receive an internally inconsistent fact.

## 6. Public payload preservation

`server/websim_payload.py` must preserve official nested socket array counts. It must not collapse an array to a boolean and then hard-code jewelry to one. Catalog enrichment must carry `socketCount` through `modCapabilities` reconstruction.

The public compact payload may provide useful first-paint rows, but final exact-variant editing capacity still comes from the matching Resolve snapshot. This keeps the backend ownership boundary intact while avoiding the current `0/0` or `1/8` presentation.

## 7. End-to-end flow

```text
periodic/differential refresh
        |
        +--> official item sockets
        +--> season-scoped rules
        +--> bounded SimC bonus map
        +--> exact observed occupancy lower bounds
        |
        v
pure max-not-sum socket authority
        |
        v
inactive Gear Release v2 -- validate/hash/shadow --> manual Manifest cutover
        |
        v
request-time PG Authority Context (no external fetch)
        |
        v
Resolver constraints + selectedOptions + Profile
        |
        v
editable frontend draft -- verified Resolve --> atomic committed state
```

## 8. Acceptance matrix

The implementation is not complete until all of these are evidenced:

1. Clean exact candidate imports the frozen `observed_profile_mage_frost` identity as 15/15 gear, 8/8 gems, 6/8 enchants, and 2/2 embellishments; other Mage templates are checked for complete editable import but do not inherit these fixed counts.
2. No inherited/read-only copy appears.
3. Every imported selected enhancement is operable.
4. Replacing one gem by `socketIndex` at 8/8 stays 8/8.
5. Replacing one occurrence of a duplicate gem changes only that occurrence.
6. Unique-gem restrictions remain enforced.
7. Enchant replace/remove/add remains canonical and counts correctly.
8. Replacing an occupied embellishment at 2/2 stays 2/2.
9. A third empty embellishment slot is blocked until capacity is freed.
10. Closing the sheet discards draft changes.
11. Verified Resolve atomically commits and reopening shows the same selections.
12. Blocked/offline Resolve preserves the old verified configuration and excludes draft values from Save/Profile.
13. Gear replacement clears only the replaced slot and recalculates capacity.
14. A two-socket to one-socket replacement removes the stale second occurrence; the reverse shows two empty rows.
15. Saving and re-importing a personal template round-trips ordered occurrences.
16. Unknown enhancement values import the gear, leave an editable empty type, show plain warning copy, and never enter Intent.
17. Rapid consecutive imports keep only the newer result.
18. Resolve, Profile, summary, badges, and sheet preserve order and multiplicity without truncation.
19. Stat-snapshot refresh cannot mutate enhancement state.
20. Cross-class samples cover every armor type plus dual-wield/off-hand boundaries.
21. Real WeChat exact-candidate evidence covers items 1–10 and 13–14 with the candidate signature visible.
22. Production candidate evidence records identity/parity, inactive release IDs, 40-spec shadow, health/API, timers/backflow, logs, and rollback before merge.

## 9. Release and rollback

The release order is mandatory:

1. deploy the v1/v2-compatible reader with `WOW_DEPLOY_START_ASYNC_SYNCS=0`;
2. prove the current v1 active Manifest still serves unchanged behavior;
3. generate an inactive v2 Gear/Community/Manifest candidate and record SimC revision plus socket-probe hash;
4. classify the change as `capability_change` and require manual cutover;
5. run 40-spec shadow, including the exact Mage vector and ninth-gem rejection;
6. switch the pointer with compare-and-swap;
7. run Resolve/Profile/API, operations, timer/backflow, log, and real WeChat smoke;
8. merge only after user-visible evidence passes.

Rollback is pointer-first: switch back to the previous v1 Manifest while the compatible reader remains deployed. If the reader itself is faulty, restore the checksummed runtime backup and restart only affected services. Probe, materialization, signature, shadow, or real-edit failure must leave or return the active pointer to the previous verified release.

If the separate talent-link candidate is still unmerged, exact WeChat verification uses an isolated composite worktree/build. It must not alter the root talent branch, and a clean-main deployment must not overwrite that candidate accidentally.

## 10. Historical boundary

Do not rewrite the v1 design, v1 implementation plan, or PR #85 deployment report. They accurately describe what was implemented and verified at the time. This v2 document and its Strict packet are the new current contract, and the roadmap labels v1 as superseded only for capacity and editability semantics.
