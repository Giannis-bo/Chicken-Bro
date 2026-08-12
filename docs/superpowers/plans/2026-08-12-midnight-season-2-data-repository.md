# Midnight Season 2 End Game Data Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, deterministic Midnight Season 2 End Game data repository and dormant candidate Release containing equipment, tier sets, gems, enchants, embellishments, crafted data, and governed item-level tracks without changing the active Season 1 Manifest.

**Architecture:** Add a data-driven S2 End Game binding and repository builder beside the existing S1-compatible contracts. Feed official Battle.net/client evidence and SimC 12.1 probes into normalized source, item, option, set, and track records; then reuse the existing Catalog v3, Exact Registry, Gear Release, shadow, and candidate evidence gates. S2 is prepared as one complete End Game pool; official unlock dates are capture evidence only and never filter Catalog membership.

**Tech Stack:** Python 3 `unittest`, Node.js tests where existing contracts require them, PostgreSQL read-model staging, SimulationCraft 12.1/Midnight runtime, Battle.net Game Data API, JSON evidence packets, existing Harness scripts.

## Global Constraints

- Use `seasonId=midnight-season-2`; derive `seasonRevision` from canonical S2 End Game inputs and capture identity, never copy the S1 revision.
- Build the complete S2 End Game pool in one candidate; do not add preseason/season/raid-wing availability filtering.
- Preserve official announcement dates only inside `captureContext` and audit evidence; do not expose them as Catalog eligibility gates.
- Keep `verified`, `partial`, `blocked`, `pending`, `stale`, and `UNVERIFIED` literal; `pending` means evidence/authority is incomplete, not that a future stage is locked.
- Battle.net/official client owns item identity, source, equipment type, set membership, recipes, and metadata; SimC owns variant attributes, executable options, profile syntax, and runtime identity.
- Exact-first remains fail-closed; observed or community data cannot create a BrowseVariant or replace a missing official/SimC authority record.
- S1 files, S1 active Manifest, existing production pointer, and unrelated dirty files `server/deploy_lighthouse.sh` and `tests/deploy_lighthouse.test.js` remain unchanged.
- No production pointer switch, cleanup, async sync, dependency installation, or frontend behavior change is part of this build.
- Every new builder gets a failing `unittest` before implementation; each task ends with focused tests, `git diff --check`, and a narrow commit.

---

## File and Boundary Map

| Boundary | Responsibility | Planned files |
| --- | --- | --- |
| S2 identity | Canonical season/binding/revision and repository validation | Create `server/season_endgame_repository.py`, `scripts/build-season-2-endgame-repository.py`, `tests/season_endgame_repository_test.py` |
| Official capture | S2 source policy, complete End Game capture, checksums, client build | Modify `scripts/capture-season-pve-official-snapshot.py`, `scripts/build-season-pve-official-evidence.py`; add `tests/season_pve_official_capture_test.py` cases and `server/data/midnight-season-2/source-policy.json` |
| Universe | Source-to-item relation and gap ledger without stage filtering | Modify `server/season_pve_universe.py`, `scripts/season-pve-universe.py`, `tests/season_pve_universe_test.py` |
| Item/variant | Official item identity plus SimC 12.1 item-level/stat/variant matrix | Modify `scripts/gear-item-level-stat-probe.py`, `scripts/gear-item-level-stat-backfill.py`, `server/gear_variant_simc_matrix.py`, `tests/gear_item_level_stat_probe_test.py`, `tests/gear_variant_simc_matrix_test.py` |
| Enhancements | S2 gem/enchant/embellishment option catalog and management fields | Create `server/gear_enhancement_catalog.py`, `tests/gear_enhancement_catalog_test.py`; integrate `server/gear_release_tool.py` and `tests/gear_release_tool_test.py` |
| Tier sets | Official set identity, class membership, set bonus binding and conflict ledger | Create `server/season_set_membership.py`, `tests/season_set_membership_test.py`; integrate `server/pg_gear_authority_loader.py`, `server/gear_rule_matrix.py` tests |
| Tracks | Data-driven S2 Track Authority with no S1 fallback | Modify `server/gear_track_authority.py`, `tests/gear_track_authority_test.py` |
| Candidate | Dormant S2 Gear Release, Catalog v3, Exact Registry, dependency vector, shadow | Create `scripts/build-season-2-endgame-candidate.py`, `tests/season_endgame_candidate_test.py`; reuse `server/gear_release.py`, `server/gear_release_tool.py`, `scripts/gear-catalog-revision.py`, `scripts/catalog-candidate-evidence.py` |
| Evidence/closure | Requirement/evidence packet, 40-spec traversal, S1 pointer invariance | Add candidate artifacts under `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/`, update `docs/plans/README.md` |

---

### Task 1: Add the S2 End Game identity and repository contract

**Files:**
- Create: `server/season_endgame_repository.py`
- Create: `scripts/build-season-2-endgame-repository.py`
- Create: `tests/season_endgame_repository_test.py`
- Create: `server/data/midnight-season-2/README.md`

**Interfaces:**
- Consumes: season metadata, source policy, official capture manifest, client build, and SimC runtime identity.
- Produces: `build_endgame_binding(season_id, season_metadata, source_policy, capture_manifest, client_build, simc_runtime_revision) -> dict[str, Any]`, `validate_endgame_binding(value) -> list[dict[str, str]]`, and a deterministic `seasonRevision` beginning with `season-midnight-season-2:`.

- [ ] **Step 1: Write the failing contract tests**

```python
class SeasonEndgameRepositoryTest(unittest.TestCase):
    def test_binding_is_deterministic_and_contains_complete_endgame_scope(self):
        first = build_endgame_binding(
            season_id="midnight-season-2",
            season_metadata={"label": "至暗之夜 Season 2", "captureContext": {"officialAnnouncementRefs": ["blizzard-s2"]}},
            source_policy={"sourcePolicyRevision": "s2-policy-r1", "sources": [{"sourceKey": "raid:venomous-abyss", "required": True}]},
            capture_manifest={"captureRevision": "capture-s2-r1", "files": [{"path": "raw.json", "sha256": "a" * 64}]},
            client_build="12.1.0.69214",
            simc_runtime_revision="simc:12.1.0.69214:abc",
        )
        second = build_endgame_binding(
            season_id="midnight-season-2",
            season_metadata={"label": "至暗之夜 Season 2", "captureContext": {"officialAnnouncementRefs": ["blizzard-s2"]}},
            source_policy={"sourcePolicyRevision": "s2-policy-r1", "sources": [{"sourceKey": "raid:venomous-abyss", "required": True}]},
            capture_manifest={"captureRevision": "capture-s2-r1", "files": [{"path": "raw.json", "sha256": "a" * 64}]},
            client_build="12.1.0.69214",
            simc_runtime_revision="simc:12.1.0.69214:abc",
        )
        self.assertEqual(first, second)
        self.assertTrue(first["seasonRevision"].startswith("season-midnight-season-2:"))
        self.assertEqual(first["scope"], "end_game")
        self.assertNotIn("availabilityStage", first)

    def test_missing_capture_or_runtime_identity_blocks_without_s1_fallback(self):
        result = build_endgame_binding(
            season_id="midnight-season-2",
            season_metadata={"label": "至暗之夜 Season 2"},
            source_policy={"sourcePolicyRevision": "s2-policy-r1", "sources": []},
            capture_manifest={},
            client_build="",
            simc_runtime_revision="",
        )
        self.assertIn("S2_CAPTURE_IDENTITY_MISSING", {row["code"] for row in result["problems"]})
        self.assertNotEqual(result.get("seasonRevision"), "season-17-f131dd36ddf1")
        self.assertEqual(result["status"], "blocked")
```

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.season_endgame_repository_test -v`

Expected: import failure because the S2 repository module and builder do not exist.

- [ ] **Step 3: Implement the minimal pure contract**

Implement canonical JSON sorting and SHA-256 hashing. `build_endgame_binding` must require `season_id == "midnight-season-2"`, `scope == "end_game"`, non-empty source/capture/runtime identities, and return `status="verified"` only when those identities and checksum-shaped capture files are present. Do not accept a `season-midnight-season-1` value or silently substitute any S1 constant.

- [ ] **Step 4: Add the offline CLI**

`scripts/build-season-2-endgame-repository.py` must accept `--season-metadata`, `--source-policy`, `--capture-manifest`, `--client-build`, `--simc-runtime-revision`, and `--output`; load JSON, call `build_endgame_binding`, atomically write the result, and exit `2` for `blocked`.

- [ ] **Step 5: Run focused tests and commit**

Run: `python3 -m unittest tests.season_endgame_repository_test -v && git diff --check`

Expected: all contract tests pass. Commit with:

```bash
git add server/season_endgame_repository.py scripts/build-season-2-endgame-repository.py tests/season_endgame_repository_test.py server/data/midnight-season-2/README.md
git commit -m "feat: add Season 2 end game repository identity"
```

### Task 2: Make official capture configurable for the complete S2 End Game pool

**Files:**
- Modify: `scripts/capture-season-pve-official-snapshot.py`
- Modify: `scripts/build-season-pve-official-evidence.py`
- Modify: `tests/season_pve_official_capture_test.py`
- Create: `server/data/midnight-season-2/source-policy.json`

**Interfaces:**
- Consumes: `server/data/midnight-season-2/source-policy.json`, Battle.net credentials from `WOW_BLIZZARD_CLIENT_ID`/`WOW_BLIZZARD_CLIENT_SECRET`, region/locale, and S2 official source references.
- Produces: an isolated raw capture manifest whose entries include URL, namespace, request identity, checksum, capture time, and `clientBuild`; no database or pointer writes.

- [ ] **Step 1: Add failing capture-profile tests**

Add tests that call the existing capture configuration helper with `season_id="midnight-season-2"` and assert that it resolves the S2 End Game source names, includes `raid:venomous-abyss`, `mythic_plus:midnight-season-2`, `crafted:midnight-season-2`, and `tier_set:midnight-season-2`, and never uses the S1 hard-coded dungeon tuple. Add a test that an empty configured source member produces a `blocked` capture result instead of an empty verified source.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.season_pve_official_capture_test -v`

Expected: the new profile tests fail because capture currently has S1 constants and no S2 source-policy input.

- [ ] **Step 3: Implement policy-driven capture selection**

Add `--season-id`, `--source-policy`, and `--content-scope` arguments while retaining the current default behavior for existing S1 tests. For `--content-scope end_game`, load source names and required source families from the policy; resolve Journal instance IDs by official names before fetching loot, rather than guessing numeric IDs. Keep every raw response in the caller-provided output directory and include a deterministic manifest entry.

The parsed capture configuration must have this concrete shape before any network request:

```python
capture_config = {
    "seasonId": "midnight-season-2",
    "contentScope": "end_game",
    "sourcePolicyRevision": "midnight-season-2-pve-source-policy-v1",
    "sourceKeys": [
        "raid:venomous-abyss",
        "mythic_plus:midnight-season-2",
        "crafted:midnight-season-2",
        "tier_set:midnight-season-2",
    ],
    "region": "us",
}
```

The capture writer must persist `capture_config` into the manifest and include it in the manifest hash. A request made with `contentScope="end_game"` and an S1 source policy must fail before the first HTTP call.

Update the evidence builder to read the configured S2 membership filename and season identity instead of the literal `midnight-season-1-crafted-pve-membership.json` path. It must preserve raw upstream gaps and return `blocked` when any required official authority is missing.

- [ ] **Step 4: Add the S2 source policy**

Create `server/data/midnight-season-2/source-policy.json` with `seasonRevision` supplied by the repository builder, `scope="end_game"`, and independent source keys for Venomous Abyss, S2 dungeon/Mythic+, Delves, Prey, Lair/World Boss, Great Vault, crafted, tier set, and governed world/vendor sources. Do not add `availabilityStage`, stage-specific selection fields, or a policy rule that filters by announcement date.

- [ ] **Step 5: Re-run tests and commit**

Run: `python3 -m unittest tests.season_pve_official_capture_test tests.season_pve_official_evidence_test -v && git diff --check`

Expected: existing S1 capture/evidence tests and new S2 profile tests pass. Commit with:

```bash
git add scripts/capture-season-pve-official-snapshot.py scripts/build-season-pve-official-evidence.py tests/season_pve_official_capture_test.py server/data/midnight-season-2/source-policy.json
git commit -m "feat: capture the complete Season 2 end game source pool"
```

### Task 3: Add End Game Universe mode without availability-window filtering

**Files:**
- Modify: `server/season_pve_universe.py:615-960`
- Modify: `scripts/season-pve-universe.py`
- Modify: `tests/season_pve_universe_test.py`

**Interfaces:**
- Consumes: policy/discovery/staging/catalog payloads with the same S2 `seasonRevision` and `scope="end_game"`.
- Produces: `build_season_pve_universe(policy, discovery, staging, catalog, exclusions=None, mode="end_game") -> dict` with source/item/gap ledger, deterministic `universeRevision`, and no stage-date exclusion.

- [ ] **Step 1: Write the failing mode tests**

Add a fixture whose source has a valid official start date after the discovery `asOf` but is explicitly part of the complete S2 End Game policy. Assert that `mode="end_game"` includes the source member and does not emit `SOURCE_OUTSIDE_EFFECTIVE_WINDOW`. Assert that default mode retains the existing current-season window behavior. Add a test that an S1 source revision mixed into the S2 payload remains blocked.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.season_pve_universe_test -v`

Expected: the new `mode` invocation fails because the function accepts only the current-season behavior.

- [ ] **Step 3: Implement the explicit End Game mode**

Add a keyword-only `mode="current"` argument. In `mode="end_game"`, require `policy.scope == "end_game"`, use source membership/status/authority checks, and record official date fields as evidence without invoking `_source_effective_window` for inclusion. Keep current mode unchanged so existing S1 window tests continue to pass. The output must carry `scope`, `seasonRevision`, `sourcePolicyRevision`, and `universeRevision` in its canonical hash input.

Use this branch at the source-ledger boundary:

```python
if mode == "end_game":
    if _text(policy.get("scope")) != "end_game":
        raise UniverseContractError("end_game mode requires an end_game policy")
    source_ledger_row = _source_ledger_row(
        policy_source,
        discovered_source,
        as_of=as_of,
        apply_effective_window=False,
    )
else:
    source_ledger_row = _source_ledger_row(
        policy_source,
        discovered_source,
        as_of=as_of,
        apply_effective_window=True,
    )
```

Change `_source_ledger_row` to accept the explicit boolean and preserve the date fields in both modes. Do not implement an implicit bypass based on the season name.

- [ ] **Step 4: Update the CLI and verify both modes**

Add `--mode {current,end_game}` to `scripts/season-pve-universe.py`, defaulting to `current`. Run:

```bash
python3 -m unittest tests.season_pve_universe_test -v
python3 -m unittest tests.season_pve_universe_cli_test -v
```

Expected: all existing tests plus new S2 End Game mode tests pass. Commit with:

```bash
git add server/season_pve_universe.py scripts/season-pve-universe.py tests/season_pve_universe_test.py
git commit -m "feat: reconcile Season 2 end game universe without stage gates"
```

### Task 4: Materialize S2 official items and SimC 12.1 variants

**Files:**
- Modify: `scripts/gear-item-level-stat-probe.py`
- Modify: `scripts/gear-item-level-stat-backfill.py`
- Modify: `server/gear_variant_simc_matrix.py`
- Modify: `tests/gear_item_level_stat_probe_test.py`
- Modify: `tests/gear_variant_simc_matrix_test.py`
- Create: `server/data/midnight-season-2/track-authority-input.json`

**Interfaces:**
- Consumes: S2 official item records, source relations, SimC 12.1 executable identity, and S2 track probe inputs.
- Produces: item-level/stat probe report and `gear_variant_simc_matrix` rows with one immutable identity per `(itemId, progressionState)`, `simcRuntimeRevision`, static facts, option fields, and explicit failure codes.

- [ ] **Step 1: Write failing S2 identity tests**

Add cases asserting that an S2 probe report rejects a missing SimC runtime revision, rejects a variant with missing `itemLevel`/`bonus_id`/static stats, preserves the S2 season revision, and never normalizes a S1 row into S2. Add an equivalent-observation case that collapses tertiary-only differences and a conflicting-core-facts case that returns `blocked` instead of selecting one row.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest tests.gear_item_level_stat_probe_test tests.gear_variant_simc_matrix_test -v`

Expected: the S2 binding assertions fail because the probes currently accept only the legacy revision shape.

- [ ] **Step 3: Implement revision-aware probe input**

Thread `seasonRevision` and `simcRuntimeRevision` through the probe report identity and matrix builder. Keep the existing S1 report format readable. Make the matrix verifier fail closed on mixed season/runtime identities and on two normal Browse rows with different core facts. Keep exact instances outside Browse membership.

Every promoted S2 row must carry the following identity before it reaches Catalog projection:

```python
row_identity = {
    "seasonRevision": season_revision,
    "simcRuntimeRevision": simc_runtime_revision,
    "itemId": item_id,
    "variantKey": variant_key,
    "rowFamily": "browse",
    "progressionState": progression_state,
}
```

The validator must compare `seasonRevision` and `simcRuntimeRevision` across every row, then compare `itemId + progressionState` core facts. A mismatch returns `GEAR_VARIANT_IDENTITY_MIXED_REVISION` or `GEAR_VARIANT_CANONICAL_DUPLICATE`; it must not select the first sorted row.

- [ ] **Step 4: Run the real 12.1 item probe in isolated output**

Use the configured SimC binary and commit identity with:

```bash
python3 scripts/gear-item-level-stat-probe.py --help
python3 scripts/gear-item-level-stat-backfill.py --help
```

Then run the existing probe/backfill commands against the S2 normalized item input, writing only under `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/raw/simc` and `normalized`. If the binary cannot execute an S2 item, retain the row as `blocked` with the exact SimC failure code.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m unittest tests.gear_item_level_stat_probe_test tests.gear_variant_simc_matrix_test tests.gear_catalog_revision_test -v && git diff --check`

Commit with:

```bash
git add scripts/gear-item-level-stat-probe.py scripts/gear-item-level-stat-backfill.py server/gear_variant_simc_matrix.py tests/gear_item_level_stat_probe_test.py tests/gear_variant_simc_matrix_test.py server/data/midnight-season-2/track-authority-input.json
git commit -m "feat: materialize Season 2 SimC variants"
```

### Task 5: Build the independent S2 enhancement option catalog

**Files:**
- Create: `server/gear_enhancement_catalog.py`
- Create: `tests/gear_enhancement_catalog_test.py`
- Modify: `server/gear_release_tool.py:377-1008`
- Modify: `tests/gear_release_tool_test.py`

**Interfaces:**
- Consumes: S2 official item metadata, SimC variant `gem_id/gem_bonus_id/gem_ilevel/enchant_id/embellishment`, socket capacities, crafted recipe modifiers, and the S2 binding.
- Produces: `build_enhancement_option_catalog(season_binding, official_items, variants) -> dict` with `schemaRevision`, `seasonRevision`, `optionRevision`, `options`, `management`, `coverage`, and per-option `status`/`blockers`.

- [ ] **Step 1: Write the failing option-catalog tests**

Add tests asserting:

```python
result = build_enhancement_option_catalog(
    season_binding=S2_BINDING,
    official_items={"gem-1": {"itemClass": "gem", "statSummary": "急速 +10"}},
    variants=[
        {"itemId": "1001", "simcOptions": {"gem_id": "gem-1", "enchant_id": "enchant-1", "embellishment": "embellishment-1"}, "socketCount": 1}
    ],
)
self.assertEqual(result["status"], "verified")
self.assertEqual({row["optionType"] for row in result["options"]}, {"socket", "enchant", "embellishment"})
self.assertEqual(result["options"][0]["seasonRevision"], S2_BINDING["seasonRevision"])
```

Also assert that a raw token without official metadata is `blocked`, a gem exceeding socket capacity is not promoted, and a built-in source-only embellishment is not exposed as an editor-managed option.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest tests.gear_enhancement_catalog_test -v`

Expected: import failure because the S2 option catalog builder does not exist.

- [ ] **Step 3: Implement pure option normalization**

Normalize gem sequences using `GEM_SIMC_SEQUENCE_FIELDS`, classify raw fields with `validated_enhancement_management_fields`, validate option identity against official metadata, and compute `optionRevision` from sorted option identity plus the S2 binding. Return blocked rows in diagnostics, never silently drop a malformed token.

- [ ] **Step 4: Integrate the existing release materializer**

Make `_materialize_enhancement_management` and the existing socket/enchant/embellishment projection consume the S2 option catalog when the input release carries `seasonRevision=midnight-season-2`. Keep the S1 path and all current `source_only`/`editor_managed` rules unchanged. Add regression tests for official gem metadata, source-only weapon enchant, built-in embellishment, and cross-season option rejection.

- [ ] **Step 5: Run focused tests and commit**

Run: `python3 -m unittest tests.gear_enhancement_catalog_test tests.gear_enhancement_management_test tests.gear_release_tool_test -v && git diff --check`

Commit with:

```bash
git add server/gear_enhancement_catalog.py tests/gear_enhancement_catalog_test.py server/gear_release_tool.py tests/gear_release_tool_test.py
git commit -m "feat: build Season 2 enhancement option catalog"
```

### Task 6: Build S2 tier-set membership and data-driven Track Authority

**Files:**
- Create: `server/season_set_membership.py`
- Create: `tests/season_set_membership_test.py`
- Modify: `server/pg_gear_authority_loader.py`
- Modify: `server/gear_rule_matrix.py`
- Modify: `tests/gear_rule_matrix_test.py`
- Modify: `server/gear_track_authority.py`
- Modify: `tests/gear_track_authority_test.py`

**Interfaces:**
- Consumes: official S2 set identity/membership, SimC set-bonus probe evidence, S2 track input records, and one S2 binding.
- Produces: `build_set_membership(season_binding, set_rows) -> dict`, `validate_set_membership(value) -> list[dict]`, and `track_authority_for_binding(binding, records=None)` that accepts explicit S2 records without falling back to S1.

- [ ] **Step 1: Write failing set and track tests**

Add set tests for one verified class set, missing `setId`, and two conflicting set IDs on one item. Add track tests that bind a custom S2 ladder and assert its item levels are returned, while an S2 binding with no records returns `TRACK_AUTHORITY_RECORDS_MISSING` rather than the S1 263/276/289/298 ladder. Retain all existing S1 tests unchanged.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest tests.season_set_membership_test tests.gear_track_authority_test tests.gear_rule_matrix_test -v`

Expected: new modules/imports and S2 record behavior fail.

- [ ] **Step 3: Implement set membership**

Build canonical set records with `setId`, `classKeys`, `itemIds`, `sourceRefs`, `setBonusEvidence`, `seasonRevision`, and status. Reject missing/ambiguous set IDs before loader projection. Make the loader expose exactly one verified set identity per item; a conflict blocks the entire item authority.

- [ ] **Step 4: Make Track Authority data-driven**

Keep the existing S1 constants as the legacy default for S1 bindings. For an S2 binding, require an explicit validated record list with `seasonRevision`, `trackAuthorityRevision`, `gearRuleRevision`, source/slot eligibility, item level ladder, and bonus evidence. Reuse the existing fail-closed rank/slot/crafted checks against the selected record list. Do not infer S2 values from the generic `trackRank` field or from S1 constants.

Use an explicit S2 branch so a missing record list cannot fall through to S1:

```python
def track_authority_for_binding(binding, records=None):
    season_revision = _text(binding.get("seasonRevision"))
    if season_revision.startswith("season-midnight-season-2:"):
        selected_records = records if isinstance(records, list) else binding.get("trackRecords")
        if not selected_records:
            return _blocked(
                "TRACK_AUTHORITY_RECORDS_MISSING",
                "S2 Track Authority requires explicit end game track records.",
            )
        return _build_data_driven_authority(binding, selected_records)
    return _build_legacy_s1_authority(binding)
```

`_build_data_driven_authority` must validate every record's season, rule revision, source refs, rank/level ladder, and eligibility before returning `verified`.

- [ ] **Step 5: Run focused tests and commit**

Run: `python3 -m unittest tests.season_set_membership_test tests.gear_track_authority_test tests.gear_rule_matrix_test tests.pg_gear_authority_loader_test -v && git diff --check`

Commit with:

```bash
git add server/season_set_membership.py tests/season_set_membership_test.py server/pg_gear_authority_loader.py server/gear_rule_matrix.py tests/gear_rule_matrix_test.py server/gear_track_authority.py tests/gear_track_authority_test.py
git commit -m "feat: bind Season 2 sets and tracks to explicit authority"
```

### Task 7: Seal a dormant S2 Catalog/Exact Registry candidate

**Files:**
- Create: `server/season_endgame_candidate.py`
- Create: `scripts/build-season-2-endgame-candidate.py`
- Create: `tests/season_endgame_candidate_test.py`
- Modify: `server/gear_release.py`
- Modify: `server/gear_release_tool.py`
- Modify: `tests/gear_release_test.py`
- Modify: `tests/gear_release_tool_test.py`

**Interfaces:**
- Consumes: S2 repository binding, normalized Universe, item/variant matrix, option catalog, set membership, track authority, SimC runtime revision, and existing PG staging snapshot.
- Produces: `build_season_endgame_candidate(repository, gear_snapshot, option_catalog, set_membership, track_authority, simc_runtime_revision) -> dict` with candidate-only Gear Release, Catalog v3 revision, Exact Registry revision, dependency vector, gate status, and no pointer mutation.

- [ ] **Step 1: Write failing candidate-gate tests**

Add tests asserting:

```python
candidate = build_season_endgame_candidate(
    repository=S2_REPOSITORY,
    gear_snapshot=S2_GEAR_SNAPSHOT,
    option_catalog=S2_OPTIONS,
    set_membership=S2_SETS,
    track_authority=S2_TRACKS,
    simc_runtime_revision="simc:12.1.0.69214:abc",
)
self.assertEqual(candidate["status"], "candidate")
self.assertEqual(candidate["seasonRevision"], S2_REPOSITORY["seasonRevision"])
self.assertFalse(candidate["activePointerChanged"])
```

Add negative tests for mixed S1/S2 revision, missing option revision, missing track authority, exact-instance leakage into BrowseVariants, and a Catalog duplicate progression shape. Each returns `blocked` and records a stable problem code.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m unittest tests.season_endgame_candidate_test -v`

Expected: import failure because the candidate wrapper does not exist.

- [ ] **Step 3: Implement the candidate wrapper**

Use `gear_release.build_release`, `gear_release.validate_release`, `scripts/gear-catalog-revision.py` inputs, and the existing Exact Registry builder. Add `seasonRevision`, `optionRevision`, `setMembershipRevision`, and `trackAuthorityRevision` to the dependency identity. The wrapper may write only candidate evidence/output; it must never invoke `promote`, CAS the active pointer, or start sync/backfill jobs.

- [ ] **Step 4: Add the CLI and candidate artifact shape**

`scripts/build-season-2-endgame-candidate.py` accepts repository, normalized snapshot, option catalog, set membership, track input, `--simc-runtime-revision`, and `--output`. It writes `requirement.json`, candidate manifest, gate summary, and blocked diagnostics under `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/candidate`.

- [ ] **Step 5: Run candidate tests and commit**

Run: `python3 -m unittest tests.season_endgame_candidate_test tests.gear_release_test tests.gear_release_tool_test tests.gear_catalog_revision_test tests.gear_exact_item_registry_test -v && git diff --check`

Commit with:

```bash
git add server/season_endgame_candidate.py scripts/build-season-2-endgame-candidate.py tests/season_endgame_candidate_test.py server/gear_release.py server/gear_release_tool.py tests/gear_release_test.py tests/gear_release_tool_test.py
git commit -m "feat: build dormant Season 2 end game candidate"
```

### Task 8: Run the authorized S2 build and evidence gates

**Files:**
- Create: `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/requirement.json`
- Create: `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/manifest.json`
- Create: `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json`
- Create: raw/normalized/candidate outputs below the same artifact root
- Modify: `docs/plans/README.md`

**Interfaces:**
- Consumes: committed S2 builders, existing Battle.net credentials, configured SimC 12.1 runtime, and the current PG staging environment.
- Produces: one auditable S2 End Game repository revision, one candidate dependency vector, 40-spec coverage report, and explicit remaining blockers.

- [ ] **Step 1: Register the active execution plan**

Add this row to the current execution-plan table in `docs/plans/README.md`:

```markdown
| 至暗之夜 S2 End Game 数据仓库候选构建 | 正在推进 | [设计](../superpowers/specs/2026-08-12-midnight-season-2-data-repository-design.md) · [实施计划](../superpowers/plans/2026-08-12-midnight-season-2-data-repository.md) |
```

- [ ] **Step 2: Create the isolated evidence root**

Create `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/` with `raw/blizzard`, `raw/client-db2`, `raw/simc`, `normalized`, `audits`, and `candidate`. Record the current Git SHA, capture timestamp, SimC binary SHA-256, SimC runtime revision, API namespace, region, and locale in the manifest.

- [ ] **Step 3: Capture official S2 End Game evidence**

Run the policy-driven capture with the repository's configured environment variables and no database target:

```bash
python3 scripts/capture-season-pve-official-snapshot.py --help
python3 scripts/build-season-pve-official-evidence.py --help
```

Then run the S2 capture using `--season-id midnight-season-2 --content-scope end_game --source-policy server/data/midnight-season-2/source-policy.json` and write only below the evidence root. Missing credentials or incomplete official coverage must produce a bounded `blocked` report, not an empty verified repository.

- [ ] **Step 4: Build the S2 repository and normalize all components**

Run the new repository CLI, End Game Universe CLI, crafted membership builder, item-level/variant probes, enhancement catalog builder, set membership builder, and track authority validator in this order. Every output must carry the same `seasonRevision`; capture/build identities must be recorded in `evidence.json`.

- [ ] **Step 5: Build and shadow the candidate**

Run the new candidate CLI, then the existing Catalog/Exact Registry and candidate evidence checks with `WOW_DATABASE_RUNTIME=postgres_only`. Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`. Record active Manifest generation before and after; require no pointer change and no write SQL from shadow.

- [ ] **Step 6: Run the verification matrix**

Run:

```bash
python3 -m unittest \
  tests.season_endgame_repository_test \
  tests.season_pve_official_capture_test \
  tests.season_pve_official_evidence_test \
  tests.season_pve_universe_test \
  tests.gear_item_level_stat_probe_test \
  tests.gear_variant_simc_matrix_test \
  tests.gear_enhancement_catalog_test \
  tests.gear_enhancement_management_test \
  tests.season_set_membership_test \
  tests.gear_track_authority_test \
  tests.gear_rule_matrix_test \
  tests.season_endgame_candidate_test \
  tests.gear_catalog_revision_test \
  tests.gear_release_test \
  tests.gear_release_tool_test
git diff --check
node scripts/project-harness.js --json --check-requirement --requirement-file artifacts/releases/2026-08-12-midnight-season-2-data-foundation/requirement.json
```

The evidence packet must report, separately: official source coverage, item/variant coverage, option coverage, set conflicts, track blockers, 40-spec candidate readiness, active S1 pointer invariance, and SimC executable coverage. A passing HTTP/CI command cannot upgrade a `partial` or `blocked` component.

- [ ] **Step 7: Commit the candidate evidence only**

Stage only the S2 design/plan registration and candidate artifact files; do not stage `server/deploy_lighthouse.sh` or `tests/deploy_lighthouse.test.js`. Commit with:

```bash
git add docs/plans/README.md artifacts/releases/2026-08-12-midnight-season-2-data-foundation
git commit -m "data: record Season 2 end game candidate evidence"
```

### Task 9: Candidate handoff and promotion boundary

**Files:**
- Modify: `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/evidence.json`
- Modify: `artifacts/releases/2026-08-12-midnight-season-2-data-foundation/manifest.json`
- Modify: `docs/plans/README.md`

**Interfaces:**
- Consumes: fresh candidate evidence and current active Manifest snapshot.
- Produces: a handoff report that says `candidate_verified`, `partial`, or `blocked`; it does not promote S2.

- [ ] **Step 1: Record the candidate identity vector**

Record `seasonRevision`, `gearReleaseId`, `gearCatalogRevision`, `gearExactRegistryRevision`, `optionRevision`, `setMembershipRevision`, `trackAuthorityRevision`, `gearRuleRevision`, `simcRuntimeRevision`, and active S1 manifest/generation.

- [ ] **Step 2: Record user-visible acceptance cases**

Cover at least one raid item, M+ item, crafted item with selectable secondary stats, crafted item with built-in embellishment, socketed item with verified gem, enchantable weapon, one class tier set, one normal track at max rank, one blocked/missing-authority row, and one exact instance that remains outside Browse.

- [ ] **Step 3: Preserve the promotion gate**

If any required source, verified option, set identity, track record, or 40-spec shadow is incomplete, mark the candidate accordingly and keep S1 active. Do not call `server.gear_release_tool promote`, do not change the retail pointer, and do not claim production readiness.

- [ ] **Step 4: Mark the plan status**

Only after the candidate artifact is complete, change the `docs/plans/README.md` row to `下一步` for controlled acceptance/cutover or `暂缓` with the exact blocker codes. A later user acceptance is required before any Manifest promotion.

## Self-Review Checklist

- [ ] The plan covers all design sections: S2 identity, End Game scope, official/SimC boundary, equipment, enhancements, sets, tracks, candidate release, verification, and rollback.
- [ ] No task introduces stage-specific availability filtering or silently reuses S1 values.
- [ ] Every new pure builder has a failing test, focused command, and stable output identity.
- [ ] Every later task consumes exact fields produced by an earlier task: `seasonRevision`, `optionRevision`, `setMembershipRevision`, `trackAuthorityRevision`, and `simcRuntimeRevision`.
- [ ] Active Manifest, production pointer, and unrelated dirty files are explicitly protected.
- [ ] The final output distinguishes candidate evidence from production acceptance.
