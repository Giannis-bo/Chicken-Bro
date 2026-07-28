# Equipment Simulator Phase 0 Unblock Implementation Plan

> Status: `implementation_allowed`
>
> Scope: clear the five independent Phase 0 blockers without introducing the
> target Catalog schema or changing the approved equipment-simulator entry flow.

**Goal:** Produce one current-season Gear/Community Release pair whose Browse
variants are losslessly mappable, whose Community templates cover all 40
specializations, whose builder has measured hard resource bounds, and whose
caller inventory has no unclassified repository references. Promote it only
after candidate, shadow, rollback and user-path gates pass.

**User experience:** A player enters equipment simulation for a chosen
class/specialization, sees current PVE equipment and its legal progression
variants, can import a current community template or build their own, saves the
template, and hands it to the existing SimC flow. Unsupported tank/healer/
Augmentation SimC execution remains a deterministic explicit block; equipment
browsing and saving still cover 40/40.

**Method:** Strict Harness control, test-driven implementation, candidate-first
runtime/data cutover, append-only Releases, CAS Manifest pointer, and fail-closed
resource/data gates.

## Frozen current facts

- Active retail pointer generation is `24`; its Gear Release is
  `gear-release:sha256:de40793805a84934497c645be2ccc914ef44191744cc76d03f765001bc6dfe6a`
  and it has no Community Release.
- The current Phase 0 audit maps `1,265 / 1,313` canonical Browse candidates.
  All 48 failures are the same data family: 12 raid items from instance `1305`,
  encounter `2711`, across Champion 263, Hero 276, Myth 289 and Ascendant 298.
  Their current item-level probe reports `SimC JSON did not include target item
  stats`.
- Production staging contains `3,253` complete Raider.IO observed gear rows
  covering 40 specializations. Historical Community Releases cannot be rebound
  because they were validated against older Gear Releases.
- The configured SimC runtime was observed at
  `725322f2671504615a37474b68561025198412f8` with
  `updateAvailable=true`. The exact configured target revision must be refreshed
  at execution time; this snapshot is evidence, not a permanently frozen latest
  version.
- A read-only current-release Community preflight repeatedly rebuilt indexes
  across 3,253 templates and 46,631 variants. At 5m31s it used `2,450,200 KiB`
  RSS and one CPU core; the diagnostic process was terminated without sealing a
  Release or changing the pointer.
- The five unclassified caller references are all in repository tooling:
  `scripts/audit-observed-build-cutover.py` (2),
  `scripts/perf_probe.py` (2), and
  `scripts/publish-runtime-media.js` (1).

## Hard boundaries

- Do not add the target Catalog schema, CatalogRevision API, new frontend entry,
  or SimulationSnapshot contract in this task.
- Do not mutate an existing sealed Gear/Community Release.
- Do not derive static stats by scaling an observed item, copying another
  difficulty, parsing display text, or inventing bonus IDs.
- Do not promote a partial Community Release or a Gear Release with any of the
  48 static-stat gaps.
- Do not call an operational script `testsDocs` merely to make
  `unresolvedCount=0`; it remains an explicit runtime-tooling caller.
- Do not run the full builder without process memory, elapsed-time, temporary
  directory and output-size bounds.
- Preserve the existing Resolver, SimC task kernel, Taro route ownership and
  26-supported/14-unsupported execution policy.

## Resource contract

The preflight and release build must run in an isolated transient unit with:

- `MemoryMax=2200M`;
- task pass threshold `peakRssObservedBytes <= 2,000,000,000`;
- `TimeoutStartSec=300`;
- `temporaryBytesObserved <= 268,435,456`;
- PostgreSQL default read-only for preflight, statement timeout `15s`, lock
  timeout `1s`;
- zero source writes and stable pointer for preflight;
- no residual temporary directory after success, failure, timeout or signal.

The lower task pass threshold leaves headroom below the existing release-refresh
service ceiling. Any exceeded bound is a blocker, never a warning.

## Task 1: Freeze Harness and root-cause evidence

**Files**

- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/requirement.json`
- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json`
- Create:
  `artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/manifest.json`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `docs/plans/README.md`

1. Register this plan and the Strict task packet.
2. Freeze the 12-item/48-variant, missing Community Release, 40-spec staging,
   resource amplification and five-caller facts above.
3. Validate the requirement alone:

```bash
node scripts/project-harness.js --json --check-requirement \
  --requirement-file artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/requirement.json
```

4. Commit the contract before production-code changes.

## Task 2: Classify runtime tooling callers

**Files**

- Modify: `tests/gear-catalog-callers-audit.test.js`
- Modify: `scripts/audit-gear-catalog-callers.js`
- Modify: `tests/gear_catalog_migration_audit_cli_test.py`

1. Add a failing fixture proving `scripts/` references are classified as
   `runtimeTooling`, included in `runtimeCallerCount`, and never silently moved
   to tests/docs.
2. Verify RED:

```bash
node --test tests/gear-catalog-callers-audit.test.js
```

3. Add `runtimeTooling` and bump the caller report schema revision. Keep the
   auditor itself excluded.
4. Update the CLI fixture to accept and summarize the new category.
5. Verify GREEN:

```bash
node --test tests/gear-catalog-callers-audit.test.js
python3 -m unittest tests.gear_catalog_migration_audit_cli_test -v
```

Acceptance: the real repository inventory has the five known references under
`runtimeTooling`, `unresolvedCount=0`, and a new deterministic report ID.

## Task 3: Reuse one immutable projection index

**Files**

- Modify: `tests/gear_release_tool_test.py`
- Modify: `server/gear_release_store.py`
- Modify: `server/gear_release_tool.py`

1. Add failing tests that:
   - allow the Gear snapshot item/variant/option collections to be indexed only
     once for a multi-template election;
   - produce byte-for-byte equivalent SelectionIntent, import evidence,
     resolver result, election rows and Community content hash;
   - reject an index bound to another Gear Release;
   - preserve exact-instance, enhancement and icon evidence gates.
2. Verify RED:

```bash
python3 -m unittest \
  tests.gear_release_tool_test.GearReleaseToolTest.test_community_preparer_reuses_one_projection_index \
  tests.gear_release_tool_test.GearReleaseToolTest.test_reused_projection_index_preserves_release_identity -v
```

3. Extend the existing immutable candidate index, or add one bounded companion,
   so `selection_intent_from_template`,
   `community_template_import_evidence_from_template`, `_template_candidate`
   and resolver preparation reuse the same item/variant/option lookup maps.
4. Do not cache template/private identity outside the process or change public
   rows.
5. Verify focused and related GREEN:

```bash
python3 -m unittest \
  tests.gear_release_tool_test \
  tests.gear_release_store_test \
  tests.gear_release_refresh_test \
  tests.community_winner_projection_test -v
```

## Task 4: Add a bounded read-only builder resource probe

**Files**

- Create: `server/gear_release_resource_probe.py`
- Create: `scripts/gear-release-resource-probe.py`
- Create: `tests/gear_release_resource_probe_test.py`
- Modify: `tests/gear_catalog_migration_audit_cli_test.py`
- Modify: `scripts/gear-catalog-migration-audit.py`
- Modify: `server/gear_catalog_migration_audit.py`

1. Write failing tests for:
   - explicit PG-only environment and read-only connections;
   - unchanged pointer before/after;
   - zero writes;
   - peak RSS, elapsed milliseconds and isolated temporary-byte measurement;
   - signal/error cleanup;
   - hard cap failure;
   - aggregate-only output with no template/profile/player identity;
   - a resource report hash bound to Gear Release, SimC revision and builder
     revision.
2. Verify RED.
3. Implement a no-seal/no-pointer Community prepare probe using the optimized
   index. The probe must write only its bounded aggregate report under the task
   artifact directory.
4. Let the Phase 0 audit consume a validated resource report; missing,
   mismatched or over-budget reports remain `RESOURCE_BASELINE_UNKNOWN` or
   `RESOURCE_BASELINE_EXCEEDED`.
5. Verify GREEN:

```bash
python3 -m unittest \
  tests.gear_release_resource_probe_test \
  tests.gear_catalog_migration_audit_cli_test \
  tests.gear_catalog_migration_audit_test -v
```

## Task 5: Refresh SimC and repair the 12-item staging facts

**Runtime sequence**

1. Record current SimC binary/revision and rollback target.
2. Use the configured server-side SimC updater to atomically install the exact
   configured target revision. Do not change `SIMC_GITHUB_REPO` or `SIMC_BRANCH`.
3. Re-run a no-write probe for all 48 item/ilevel pairs.
4. If any pair still lacks exact SimC item stats, stop promotion and continue
   source-authority diagnosis in this same task. Do not scale or substitute
   stats.
5. When 48/48 probe rows are exact, run the existing controlled instance-1305
   item-level backfill against mutable staging only.
6. Verify staging now has 48 verified variants with exact item stats and no
   `SimC JSON did not include target item stats` blocker.

Evidence must include only item IDs, levels, aggregate statuses, immutable SimC
revision/hash and bounded error codes.

## Task 6: Build and validate an inactive Gear/Community pair

1. Deploy the exact task branch as the candidate runtime with async syncs off.
2. Run the optimized resource probe in the bounded transient unit.
3. Build and seal one new inactive Gear Release from staging.
4. Build and seal one Community Release validated against that exact Gear
   Release.
5. Require:
   - Gear Release `validated`;
   - Community Release `validated`;
   - 40/40 winner specs and the expected 80 Hero-slot winners;
   - exact Community template replay;
   - resource contract pass;
   - zero public pointer change during build.
6. Run existing release shadow/Resolve/Profile/import checks against the
   inactive pair. Any partial row blocks promotion.

## Task 7: Candidate promotion, rollback and user path

1. Build a Manifest that cross-binds the new Gear Release, Community Release,
   current Talent catalog and exact dependency vector.
2. CAS-promote from the observed active generation with the prior Manifest as
   rollback target.
3. Run:
   - 40/40 initial gear candidate matrix;
   - 40/40 community-template availability/import matrix;
   - representative Browse/Resolve/Profile and enhancement checks;
   - 26 supported specialization SimC smoke and the existing deterministic
     14-specialization unsupported matrix, to the level required by the target
     architecture gate;
   - service, timer, log, PG-only and file/build identity checks.
4. Prove the pointer can roll back to the prior Manifest and then restore the
   accepted candidate using CAS, without mutating sealed rows.
5. Refresh the WeChat build and obtain explicit user acceptance for the frozen
   manual items:
   - `wechat_gear_current_community_import`;
   - `wechat_gear_saved_template_simc_handoff`.

## Task 8: Re-run Phase 0 and make the mechanical decision

1. Generate the caller v2 inventory.
2. Run the exact committed Phase 0 audit against the promoted candidate state.
3. Require:
   - `1,313 / 1,313` canonical Browse candidates mapped;
   - active Community Release present and exact;
   - 40/40 specialization coverage verified;
   - resource facts measured and within bounds;
   - `unresolvedCount=0`;
   - stable pointer during the read-only audit and zero source writes.
4. Generate a new Phase 1 decision mechanically. Only a fully passing report may
   change `allowedNextPlan` from `none` to `schema_shadow`.
5. Update project state, roadmap, target architecture, governance and evidence.
6. Run full local CR, focused/related/full Harness, candidate identity checks,
   PR CI, merge, post-merge scoped verification, main/origin parity and cleanup.

## Verification matrix

```bash
node --test tests/gear-catalog-callers-audit.test.js
python3 -m unittest \
  tests.gear_release_resource_probe_test \
  tests.gear_release_tool_test \
  tests.gear_release_store_test \
  tests.gear_release_refresh_test \
  tests.gear_catalog_migration_audit_test \
  tests.gear_catalog_migration_audit_cli_test -v
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/requirement.json \
  --evidence-file artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/evidence.json \
  --manifest-file artifacts/releases/2026-07-28-equipment-simulator-phase0-unblock/manifest.json \
  --base origin/main
```

No completion claim is allowed until the fresh Phase 0 decision, candidate/live
identity, rollback, manual acceptance and main/origin/cloud parity all pass.
