# Mage Candidate Validation and Elemental Shaman Effects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide an isolated Mage Arcane/Frost candidate with two importable hero-template rows per specialization, then implement the first non-Mage stable-effect slice for Elemental Shaman without changing the formal active Manifest.

**Architecture:** The formal retail pointer remains untouched. A sealed `community-release-v2` candidate is bound only to `wow-backend-candidate` using `WOW_COMMUNITY_GEAR_PREVIEW_RELEASE_ID` and, only if required, `WOW_GEAR_PREVIEW_RELEASE_ID`. Mage validation uses the existing verified source-effect mappings; Elemental Shaman adds only unconditional effects selected by a decoded source loadout, while panel calculation remains unavailable when canonical static facts are incomplete.

**Tech Stack:** Python 3, PostgreSQL, immutable Gear/Community Release registry, systemd candidate service, Taro mini-program API override, Python unittest.

## Global Constraints

- Never move `cache.websim_active_manifest_pointer` for candidate or user testing.
- Keep `WOW_DEPLOY_START_ASYNC_SYNCS=0`; only explicitly targeted Raider.IO slots may be refreshed.
- Community rows must remain `raiderio_observed_profile`, exact class/spec/source identity, resolver-verified, and hero-scoped; do not add cross-hero or cross-spec fallback.
- A candidate preview release may cover only the Mage validation scope because it runs on the isolated candidate service; the formal active Community Release must not be replaced by a partial release.
- Elemental Shaman panel numbers are out of scope. Missing canonical item, gem, or enchant facts must keep the panel fail-closed.

---

### Task 1: Record the narrowed first-slice contract

**Files:**
- Modify: `docs/superpowers/specs/2026-07-23-elemental-shaman-stable-effects-design.md`
- Create: `docs/superpowers/plans/2026-07-23-mage-candidate-validation-and-elemental-effects.md`
- Modify: `docs/plans/README.md`

**Interfaces:**
- Consumes: the user-approved Elemental Shaman scope and the active gear-template projection plan.
- Produces: a registered execution authority that distinguishes candidate import validation from formal release promotion.

- [ ] **Step 1: Update the design acceptance boundary**

Replace the attribute-panel requirement with this exact rule:

```markdown
属性面板在缺少完整静态事实时仍明确不可用，不以不完整装备、宝石或附魔数据计算数值。
```

- [ ] **Step 2: Register this implementation plan**

Add this row under `docs/plans/README.md` current plans:

```markdown
| 法师候选验证与元素萨满稳定效果首批 | 正在推进 | [2026-07-23-mage-candidate-validation-and-elemental-effects.md](../superpowers/plans/2026-07-23-mage-candidate-validation-and-elemental-effects.md) |
```

- [ ] **Step 3: Verify the documentation delta**

Run: `git diff --check -- docs/superpowers/specs/2026-07-23-elemental-shaman-stable-effects-design.md docs/superpowers/plans/2026-07-23-mage-candidate-validation-and-elemental-effects.md docs/plans/README.md`

Expected: no whitespace errors and exactly one narrowed scope plus one registered plan.

- [ ] **Step 4: Commit the design and plan only**

```bash
git add docs/superpowers/specs/2026-07-23-elemental-shaman-stable-effects-design.md \
  docs/superpowers/plans/2026-07-23-mage-candidate-validation-and-elemental-effects.md \
  docs/plans/README.md
git commit -m "docs: plan mage candidate and elemental effects slice"
```

### Task 2: Seal a Mage-only candidate preview pair

**Files:**
- Modify: PostgreSQL staging and immutable release tables through existing store/tool APIs only.
- Modify temporarily on candidate host: `wow-backend-candidate.service` environment drop-in.
- Test: remote `load_active_public_gear`, `load_active_community_template_import`, and candidate HTTP smoke.

**Interfaces:**
- Consumes: `sync_community_template_cache_postgres(mode="targeted_slots")`, `capture_gear_projection_profiles`, `run_gear_observed_backfill_postgres`, `prepare_staging_community_release`, and the active formal Gear Release descriptor.
- Produces: a sealed `community-release-v2` candidate containing exactly four Mage hero rows, plus an isolated candidate API binding that identifies itself as `candidatePreview`.

- [ ] **Step 1: Refresh exactly four Mage source slots**

Run under the existing remote sync lock with only these slots:

```python
sync_community_template_cache_postgres(
    mode="targeted_slots",
    refresh_raiderio=True,
)
```

Set `WOW_COMMUNITY_TEMPLATE_TARGET_SLOTS` to:

```text
mage:arcane:spellslinger,mage:arcane:sunfury,mage:frost:spellslinger,mage:frost:frostfire
```

Expected: all four targeted Talent rows are `verified`; no non-Mage target is refreshed.

- [ ] **Step 2: Capture only the elected Mage source identities and materialize observed gear**

Use the promoted candidate order as the sole input:

```python
captured_payload = capture_gear_projection_profiles(
    persisted_talent_rows,
    store.get_raiderio_payload(),
    request_limit=8,
)
store.save_raiderio_payload(captured_payload)
run_gear_observed_backfill_postgres(
    mode="mage_candidate_validation",
    store=store,
    target_limit=64,
    profile_limit=8,
    full_profile_gear=True,
    enable_simc_stats=False,
)
store.replace_community_gear_templates(
    store.build_community_gear_templates(scan_run_id=scan_run_id),
    scan_run_id=scan_run_id,
)
```

Expected: every projection candidate used for the four slots has a same-identity, complete observed gear template or is reported as a bounded rejection.

- [ ] **Step 3: Write and run a candidate preparation probe before sealing**

```python
prepared = prepare_staging_community_release(
    store,
    gear_release_descriptor=active_gear_release,
    gear_snapshot=active_gear_snapshot,
    dependency_revisions=active_gear_release["dependencyRevisions"],
    expected_specs=[("mage", "arcane"), ("mage", "frost")],
    now=utc_now(),
    source_revision="mage-effect-validation-r1",
)
assert prepared["gate"]["status"] == "validated"
assert prepared["gate"]["winnerHeroSlotCount"] == 4
```

Expected: four rows, each with v3 evidence whose `sourceStableEffects.status` is `verified`. If active Gear variants are missing, stop the Community seal and build a sealed candidate Gear Release from `prepare_staging_gear_release`; never use raw staging snapshots.

- [ ] **Step 4: Seal the candidate and bind only the candidate service**

```python
seal = store.seal_community_release(
    prepared["release"],
    prepared["rows"],
    gate_result=prepared["gate"],
    event={"mode": "mage-effect-validation-r1", "gate": prepared["gate"]},
)
assert seal["status"] == "sealed"
```

Set the sealed ID only in the candidate service drop-in:

```ini
[Service]
Environment=WOW_COMMUNITY_GEAR_PREVIEW_RELEASE_ID=<sealed-community-release-id>
```

If Step 3 used a candidate Gear Release, add:

```ini
Environment=WOW_GEAR_PREVIEW_RELEASE_ID=<sealed-gear-release-id>
```

Then run `systemctl daemon-reload` and restart only `wow-backend-candidate`.

- [ ] **Step 5: Prove candidate import readiness and hand off manual Mage validation**

For Arcane and Frost, verify exactly two `heroKey` rows, `candidatePreview=true`, four exact import requests, and no raw talent code in the response. The manual scenario is:

```text
奥法：Spellslinger、Sunfury 各导入一次。
冰法：Spellslinger、Frostfire 各导入一次。
每次均应填充装备并保留社区来源；正式入口的 Manifest revision 不变。
```

Expected: all four candidate imports succeed. Keep the candidate binding until the user reports the result; do not promote it.

### Task 3: Add Elemental Shaman unconditional stable-effect projection

**Files:**
- Modify: `server/websim_payload.py:6975-7089`
- Modify: `tests/gear_attribute_stable_effects_test.py`

**Interfaces:**
- Consumes: decoded Elemental Shaman source-loadout spell IDs.
- Produces: `derive_gear_attribute_stable_effect_context(loadout, "shaman", "elemental") -> verified` only when the source code decodes and includes supported unconditional effects.

- [ ] **Step 1: Write the failing projection test**

```python
def test_elemental_shaman_source_loadout_projects_only_unconditional_effects(self):
    decoded = {
        "status": "decoded",
        "classKey": "shaman",
        "specKey": "elemental",
        "loadout": [
            {"entryId": 1, "node": {"entries": [{"id": 1, "spell": {"id": 1269360}}]}},
            {"entryId": 2, "node": {"entries": [{"id": 2, "spell": {"id": 1269364}}]}},
            {"entryId": 3, "node": {"entries": [{"id": 3, "spell": {"id": 1270375}}]}},
            {"entryId": 4, "node": {"entries": [{"id": 4, "spell": {"id": 1270350}}]}},
        ],
    }
    with patch.object(websim_payload, "decode_external_talent_import_code", return_value=decoded):
        context = websim_payload.derive_gear_attribute_stable_effect_context(
            {"rawImportCode": "CEA_SOURCE_LOADOUT_MUST_NOT_LEAK"}, "shaman", "elemental"
        )
    self.assertEqual(context["status"], "verified")
    self.assertEqual(context["effectIds"], [
        "shaman:amped_up", "shaman:path_of_the_seer", "shaman:spiritual_awakening",
    ])
    self.assertNotIn("shaman:instinctive_imbuements", context["effectIds"])
```

- [ ] **Step 2: Run the focused test to prove the current failure**

Run: `python3 -m unittest tests.gear_attribute_stable_effects_test.GearAttributeStableEffectsTest.test_elemental_shaman_source_loadout_projects_only_unconditional_effects -v`

Expected: FAIL because `shaman/elemental` has no stable-effect mapping.

- [ ] **Step 3: Add the minimal unconditional mapping**

```python
("shaman", "elemental"): {
    1269360: "shaman:amped_up",
    1269364: "shaman:path_of_the_seer",
    1270375: "shaman:spiritual_awakening",
},
```

Do not register spell `1270350` (`Instinctive Imbuements`): it depends on Lightning Shield being active and is not source-loadout-stable. Do not add an Elemental Shaman base-effect set in this slice.

- [ ] **Step 4: Prove the unchanged fail-closed branches**

Add and run this assertion in the same test module:

```python
with patch.object(websim_payload, "decode_external_talent_import_code", return_value={
    "status": "decoded", "classKey": "shaman", "specKey": "restoration", "loadout": [],
}):
    unavailable = websim_payload.derive_gear_attribute_stable_effect_context(
        {"rawImportCode": "CEA_UNSUPPORTED"}, "shaman", "restoration"
    )
self.assertEqual(unavailable["status"], "unavailable")
```

Run: `python3 -m unittest tests.gear_attribute_stable_effects_test -v`

Expected: PASS; Mage expectations stay unchanged and Restoration Shaman remains unavailable.

- [ ] **Step 5: Commit the tested source change**

```bash
git add server/websim_payload.py tests/gear_attribute_stable_effects_test.py
git commit -m "feat: project elemental shaman stable effects"
```

### Task 4: Verify and stage the next candidate without formal promotion

**Files:**
- Test: `tests/gear_attribute_stable_effects_test.py`
- Test: `tests/community_template_import_test.py`
- Test: `tests/gear_release_tool_test.py`
- Test: `tests/gear_release_store_test.py`
- Test: candidate service health and four Mage import responses.

**Interfaces:**
- Consumes: Tasks 2–3, the existing candidate service, and user-reported Mage manual results.
- Produces: a truthful candidate evidence record and an Elemental Shaman-ready next source slice; no formal Manifest promotion.

- [ ] **Step 1: Run scoped local verification**

Run:

```bash
python3 -m unittest \
  tests.gear_attribute_stable_effects_test \
  tests.community_template_import_test \
  tests.gear_release_tool_test \
  tests.gear_release_store_test -v
```

Expected: PASS.

- [ ] **Step 2: Run local review checks**

Run:

```bash
git diff --check
git diff -- server/websim_payload.py tests/gear_attribute_stable_effects_test.py
```

Expected: no raw import code in public projections, no new fallback context, and no non-Elemental Shaman effect mapping.

- [ ] **Step 3: Wait for explicit Mage manual result before Elemental candidate binding**

Record the user’s four Mage candidate-import outcomes as accepted, pending, or failed. If any fails, inspect the isolated candidate only and do not start an Elemental candidate. If all pass, deploy the tested mapping to the candidate tree and refresh only `shaman:elemental:farseer` and `shaman:elemental:stormbringer` for the next candidate stage.

## Self-Review

- **Spec coverage:** Task 2 provides the requested immediate Mage validation without replacing the formal entry; Task 3 starts exactly one non-Mage specialization; Task 4 keeps Elemental progression contingent on observed Mage behavior.
- **Trust coverage:** all candidate rows stay source-identity-bound and resolver-verified; candidate preview never moves the formal pointer; conditional effects and incomplete panel facts remain fail-closed.
- **Type consistency:** `sourceStableEffects`, `heroKey`, `candidatePreview`, `WOW_COMMUNITY_GEAR_PREVIEW_RELEASE_ID`, and `WOW_GEAR_PREVIEW_RELEASE_ID` use their current repository spellings.
