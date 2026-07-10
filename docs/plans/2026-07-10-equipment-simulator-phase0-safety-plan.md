# Equipment Simulator Phase 0 Production Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Every behavior change requires `superpowers:test-driven-development`; every completion claim requires `superpowers:verification-before-completion`. This plan is executed inline without subagents.

**Goal:** Close the three approved current-production safety gaps without introducing the Phase 1 contracts, Phase 2 Resolver, Phase 3 `/resolve` route, or Phase 5 asynchronous Worker.

**Architecture:** Deliver three ordered, independently reviewable runtime PRs. Slice 0A makes enhancement application depend on server-attached catalog authority, Slice 0B makes the Catalyst cutover gate blocked regardless of parser allowlist compatibility, and Slice 0C adds a `stat_snapshot_v1` serializer flavor plus a process-global single-execution guard while keeping the legacy endpoint response contract.

**Tech Stack:** Python 3, `unittest`, `ThreadingHTTPServer`, PostgreSQL-only production routes, SimulationCraft stdin/JSON output, repo-native Harness v0.5, systemd deployment, GitHub PRs.

## Global Constraints

- Keep the legacy `POST /api/websim/gear/stats` HTTP 200 response structure compatible.
- Do not add `POST /api/websim/gear/resolve`.
- Do not add `POST /api/websim/gear/stat-snapshots`, a job table, queue, lease, heartbeat, or Worker.
- Do not add a PostgreSQL Authority Context loader; Slice 0A must fail closed until Phase 2 supplies server authority.
- Keep `redirected_base_stats` parser compatibility, but never report Catalyst retained-secondary-stat conversion as verified.
- Do not change public community-template source policy, baseline-empty policy, PG-only runtime, personal-template ownership, news/talent semantics, or deploy async-sync defaults.
- Keep `.superpowers/` untracked and untouched.
- Each slice uses its own `codex/` branch, PR, Strict Harness packet, candidate deployment, rollback record, merge, and post-merge live smoke.
- A slice is not complete until its PR is merged and its evidence packet reflects the real candidate and main identities.

---

## File Structure

### Slice 0A — PG enhancement authority guard

- Modify: `server/websim_payload.py` — sanitize the private catalog-authority marker and require it before applying a submitted enhancement.
- Modify: `tests/websim_payload_test.py` — add the PostgreSQL-style `conn=None` forged embellishment regression while retaining catalog-backed behavior.
- Modify: `docs/backend-owner-map.json` — record the new serializer characterization under `gear_serializer_golden_payload`.
- Modify: `docs/project-owner-map.json` — add the regression to `simc_template_task_pipeline` characterization.
- Modify: `docs/verification-matrix.md` — register the Phase 0A targeted profile.
- Modify: `docs/project-state.json` and `docs/roadmap.md` — point current truth to the active Slice 0A release packet and status.
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/{requirement.json,evidence.json,manifest.json}`.

### Slice 0B — Catalyst false-green guard

- Modify: `server/news_backend.py` — return blocked Catalyst capability with an explicit external-proof blocker.
- Modify: `tests/news_backend_test.py` — prove parser allowlisting does not promote the capability and season cutover stays blocked.
- Modify: `docs/backend-owner-map.json` and `docs/project-owner-map.json` — record the health/admin consumer characterization.
- Modify: `docs/verification-matrix.md`, `docs/project-state.json`, and `docs/roadmap.md` — register and activate Slice 0B evidence.
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed/{requirement.json,evidence.json,manifest.json}`.

### Slice 0C — Legacy stat endpoint containment

- Modify: `server/websim_payload.py` — add execution-flavor constants, keep standard profile defaults, use `iterations=1` for stat snapshots, and serialize legacy stat SimC execution with one process-global semaphore.
- Modify: `tests/websim_payload_test.py` — prove the endpoint uses `stat_snapshot_v1`, preserves required response fields, and never overlaps two SimC executions.
- Modify: `docs/backend-owner-map.json` and `docs/project-owner-map.json` — record serializer/runtime characterization.
- Modify: `docs/verification-matrix.md`, `docs/project-state.json`, `docs/roadmap.md`, and `docs/gear-simulation-full-chain-runbook.md` — register and close Phase 0.
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/{requirement.json,evidence.json,manifest.json}`.

## Slice 0A: PostgreSQL Enhancement Authority Guard

### Task 1: Open the Slice 0A Harness contract

**Files:**
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/requirement.json`
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`

**Interfaces:**
- Consumes: Harness packet schema from `scripts/project-harness.js`.
- Produces: requirement slug `equipment-simulator-phase0a-pg-enhancement-guard`, status `implementation_allowed`, release trigger `backend_api`.

- [ ] **Step 1: Create the Strict requirement packet**

Create `requirement.json` with this complete contract:

```json
{
  "schemaVersion": 1,
  "slug": "equipment-simulator-phase0a-pg-enhancement-guard",
  "classification": "Strict",
  "status": "implementation_allowed",
  "goal": "Reject PostgreSQL-only client-supplied enhancement options unless the backend successfully attached the verified server catalog for the selected gear.",
  "userValue": "A crafted client payload cannot turn an unverified embellishment, gem, or enchant into an executable SimC gear line.",
  "nonGoals": [
    "No PostgreSQL Authority Context loader",
    "No canonical Resolver",
    "No resolve endpoint",
    "No public gear template policy change",
    "No sync write backfill cleanup change",
    "No dependency installation or third-party download"
  ],
  "currentTruth": {
    "sources": [
      "docs/project-state.json",
      "docs/roadmap.md",
      "docs/harness.md",
      "docs/plans/2026-07-10-equipment-simulator-capability-architecture-design.md",
      "docs/plans/2026-07-10-equipment-simulator-phase0-safety-plan.md",
      "docs/backend-owner-map.json",
      "docs/project-owner-map.json"
    ],
    "activeMilestone": "equipment_simulator_phase0",
    "featureIteration": "allowed_under_harness"
  },
  "impactMap": {
    "mustChange": [
      "server/websim_payload.py enhancement catalog attachment and validation",
      "tests/websim_payload_test.py PostgreSQL-only forged enhancement regression",
      "backend and project owner characterization",
      "Phase 0A verification and release evidence"
    ],
    "mustNotChange": [
      "valid SQLite catalog-backed enhancement serialization",
      "public observed-only community template entry",
      "PostgreSQL-only runtime boundary",
      "frontend state and UI",
      "sync write backfill cleanup paths"
    ],
    "evidenceRequired": [
      "red test proving conn=None accepts a forged client embellishment before the fix",
      "green targeted serializer tests",
      "backend and full verification profiles",
      "local CR and git diff check",
      "candidate POST profile smoke with a forged enhancement",
      "timer backflow and runtime hash parity evidence"
    ]
  },
  "ownership": {
    "factOwner": "server/websim_payload.py",
    "consumers": [
      "server/news_backend.py PostgreSQL-only profile and gear-stats routes",
      "SimC profile serializer",
      "pages/builds/detail.js structured enhancement snapshots"
    ]
  },
  "engineeringHealth": {
    "status": "health_watch",
    "reason": "The change is a narrow compatibility-facade guard in a hotspot file; it adds no new domain responsibility and is protected by characterization, candidate smoke, and rollback."
  },
  "acceptanceEvidence": [
    "python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_pg_only_structured_enhancement_rejects_client_catalog_forgery tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_uses_server_catalog_over_client_options",
    "python3 -m unittest tests.websim_payload_test tests.news_backend_test",
    "node scripts/verify-project.js --profile backend --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard --base origin/main",
    "node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard --base origin/main",
    "node scripts/project-harness.js --check --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/requirement.json --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json --base origin/main",
    "git diff --check",
    "candidate deployment and live POST /api/websim/profile forged-enhancement smoke"
  ],
  "releaseTrigger": "backend_api",
  "rollback": [
    "code_rollback"
  ],
  "decisionLog": [
    {
      "date": "2026-07-10",
      "decision": "Phase 0A fails closed when catalog authority is unavailable instead of building the Phase 2 PostgreSQL Authority Context loader early."
    },
    {
      "date": "2026-07-10",
      "decision": "A private marker is sanitized before use so the client cannot claim that server catalog attachment succeeded."
    }
  ]
}
```

- [ ] **Step 2: Create the initial evidence packet**

Create `evidence.json` with `status` and `highestEvidenceLevel` set to `implementation_allowed`, branch `codex/equipment-simulator-phase0a-pg-enhancement-guard`, commit `uncommitted`, the exact scope above, verification entries set to `not_run`, empty `runtimeEvidence`, explicit risks, `candidateDeployment.status=not_run`, `rollback=["code_rollback"]`, `cleanup.required=false`, and `archivedReferences` containing only existing current-truth files.

- [ ] **Step 3: Activate the release artifact in current truth**

Set these exact `docs/project-state.json` fields while preserving accepted baselines and historical contracts:

```json
{
  "updatedAt": "2026-07-10",
  "activeMilestone": "equipment_simulator_phase0",
  "featureIteration": "allowed_under_harness",
  "activeReleaseArtifact": "artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard"
}
```

Add one newest roadmap paragraph stating `Phase 0A 正在推进`, the exact release artifact, the forged enhancement user risk, and the must-not-change contracts.

- [ ] **Step 4: Validate the packet before code**

Run:

```bash
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json \
  --base origin/main
```

Expected: exit 0 and no packet reason codes.

### Task 2: Add the forged-enhancement red test

**Files:**
- Modify: `tests/websim_payload_test.py`

**Interfaces:**
- Consumes: `build_websim_profile_response(payload, conn=None)`.
- Produces: regression `test_pg_only_structured_enhancement_rejects_client_catalog_forgery`.

- [ ] **Step 1: Write the failing test**

Add this test beside the existing server-catalog precedence test:

```python
def test_pg_only_structured_enhancement_rejects_client_catalog_forgery(self):
    response = self.websim_payload.build_websim_profile_response(
        {
            "classKey": "mage",
            "specKey": "arcane",
            "talents": "C4DAAAAAAAAAAAAAAAAAAAAAAA",
            "gearSelection": {
                "items": [
                    {
                        "slot": "wrist",
                        "itemId": "250888",
                        "name": "Crafted Cuffs",
                        "ilevel": 289,
                        "bonus_id": "13534",
                        "simcReady": True,
                        "sourceType": "crafted",
                        "crafted_stats": "32/49",
                        "modCapabilities": {"canEmbellish": True},
                        "embellishmentOptions": [
                            {
                                "id": "client-only-embellishment",
                                "status": "verified",
                                "payload": {"qualityRank": 2},
                                "simcOptions": {"embellishment": "client_only_lining"},
                            }
                        ],
                    }
                ]
            },
            "enhancementBySlot": {
                "wrist": {
                    "embellishmentOptionId": "client-only-embellishment",
                    "embellishment": "client_only_lining",
                }
            },
        },
        conn=None,
    )

    blockers = response["readiness"]["enhancement"]["blockers"]
    self.assertTrue(
        any(
            "wrist embellishment option is not in verified rank-two catalog" in blocker
            and "server authority unavailable" in blocker
            for blocker in blockers
        )
    )
    self.assertNotIn("embellishment=client_only_lining", response["profile"])
```

- [ ] **Step 2: Run the red test**

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_pg_only_structured_enhancement_rejects_client_catalog_forgery
```

Expected: FAIL because the current `conn=None` path trusts the client-supplied `embellishmentOptions`, emits `embellishment=client_only_lining`, and has no authority-unavailable blocker.

### Task 3: Sanitize and require server catalog attachment

**Files:**
- Modify: `server/websim_payload.py`

**Interfaces:**
- Consumes: selected item dicts, normalized enhancement dicts, optional SQLite connection.
- Produces: `attach_catalog_enhancement_options(conn, items) -> list[dict]` with a server-only marker and `validate_enhancement_option(item, enhancement, option_type, authority_attached=True) -> tuple[bool, str]`.

- [ ] **Step 1: Add the private marker constant**

Add beside `GEAR_ENHANCEMENT_SNAPSHOT_REVISION`:

```python
GEAR_ENHANCEMENT_AUTHORITY_MARKER = "_serverCatalogEnhancementAuthority"
```

- [ ] **Step 2: Sanitize the marker and set it only after a successful catalog load**

Replace the opening and success path of `attach_catalog_enhancement_options` with:

```python
def attach_catalog_enhancement_options(conn, items):
    sanitized_items = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        sanitized = dict(item)
        sanitized.pop(GEAR_ENHANCEMENT_AUTHORITY_MARKER, None)
        sanitized_items.append(sanitized)
    if conn is None:
        return sanitized_items
    try:
        options_by_type = {
            "socketOptions": display_ready_gear_mod_options_by_slot(conn, "socket"),
            "enchantOptions": display_ready_gear_mod_options_by_slot(conn, "enchant"),
            "embellishmentOptions": display_ready_gear_mod_options_by_slot(conn, "embellishment"),
        }
    except Exception:
        return sanitized_items
    enhanced = []
    for item in sanitized_items:
        slot = item.get("slot") or ""
        next_item = dict(item)
        for key, by_slot in options_by_type.items():
            if key == "enchantOptions":
                next_item[key] = [
                    option
                    for option in by_slot.get(slot) or []
                    if gear_enchant_option_applies_to_item(option, next_item)
                ]
            elif key == "embellishmentOptions":
                next_item[key] = [
                    option
                    for option in by_slot.get(slot) or []
                    if gear_embellishment_option_applies_to_item(option, next_item)
                ]
            else:
                next_item[key] = by_slot.get(slot) or []
        next_item[GEAR_ENHANCEMENT_AUTHORITY_MARKER] = True
        enhanced.append(next_item)
    return enhanced
```

- [ ] **Step 3: Make validation fail closed without the marker**

Change the validator signature and first branch to:

```python
def validate_enhancement_option(item, enhancement, option_type, authority_attached=True):
    if not authority_attached:
        return (
            False,
            f"{item.get('slot')} {option_type} option is not in verified rank-two catalog "
            "(server authority unavailable)",
        )
    if not item_supports_enhancement_type(item, option_type):
        return False, f"{item.get('slot')} {option_type} incompatible with selected gear"
    options = enhancement_options_for_type(item, option_type)
    if not options:
        return False, f"{item.get('slot')} {option_type} option is not in verified rank-two catalog"
    if not matching_enhancement_option(item, enhancement, option_type):
        return False, f"{item.get('slot')} {option_type} option is not in verified rank-two catalog"
    return True, ""
```

- [ ] **Step 4: Pass the trusted marker to all three enhancement validators**

At the start of each item loop, compute:

```python
catalog_authority_attached = next_item.get(GEAR_ENHANCEMENT_AUTHORITY_MARKER) is True
```

Pass `authority_attached=catalog_authority_attached` in the socket, enchant, and embellishment calls. Before appending the item, remove both private markers:

```python
next_item.pop("_catalogEnhancementOptionsAttached", None)
next_item.pop(GEAR_ENHANCEMENT_AUTHORITY_MARKER, None)
```

- [ ] **Step 5: Run the green target and adjacent regressions**

Run:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_pg_only_structured_enhancement_rejects_client_catalog_forgery \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_blocks_uncatalogued_options \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_uses_server_catalog_over_client_options \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_rejects_catalog_options_without_item_capability
```

Expected: 4 tests pass; the forged option is absent, existing `not in verified rank-two catalog` substrings remain compatible, and real catalog-backed validation still works.

### Task 4: Close Slice 0A locally, candidate-deploy, merge, and archive

**Files:**
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Modify: `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json`
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/manifest.json`

- [ ] **Step 1: Update owner and verification contracts**

Add the new test name to `gear_serializer_golden_payload.characterization` and `simc_template_task_pipeline.characterization`. Add a Phase 0A verification section with the four-test target, `tests.websim_payload_test`, `tests.news_backend_test`, backend profile, full profile, Harness check, JSON parse, and `git diff --check`.

- [ ] **Step 2: Run local verification**

Run the exact Phase 0A target, then:

```bash
python3 -m unittest tests.websim_payload_test tests.news_backend_test
node scripts/verify-project.js --profile backend --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard --base origin/main
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard --base origin/main
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 3: Perform local CR**

Inspect `git diff --stat`, `git diff -- server/websim_payload.py tests/websim_payload_test.py`, and the control-plane diff. Confirm no public selector, sync/write/backfill/cleanup, frontend, migration, or unrelated file changed; confirm a forged private marker is stripped; confirm valid catalog-backed behavior remains.

- [ ] **Step 4: Generate and validate the manifest**

Update evidence with the red/green outputs and local review, then run:

```bash
node scripts/project-harness.js --json --write \
  --date 2026-07-10 \
  --slug equipment-simulator-phase0a-pg-enhancement-guard \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json \
  --base origin/main
```

Expected: manifest written and packet check exits 0.

- [ ] **Step 5: Commit and open the PR**

Stage only Slice 0A files and commit:

```bash
git commit -m "fix: reject unauthoritative gear enhancements"
```

Push `codex/equipment-simulator-phase0a-pg-enhancement-guard` and open a non-draft PR only after local verification is green.

- [ ] **Step 6: Candidate-deploy the exact PR commit**

Run:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 \
WOW_DEPLOY_START_ASYNC_SYNCS=0 \
./server/deploy_lighthouse.sh
```

Smoke `/health`, `/api/data/health`, `/api/websim/gear` initial/slot, and a `POST /api/websim/profile` payload derived from an active observed template but with a forged client-only wrist embellishment. Expected: HTTP 200 compatibility, `profileReadiness.simcReady=false`, authority blocker present, and no forged `embellishment=` line. Record runtime hashes, `WOW_DATABASE_RUNTIME=postgres_only`, timers/services, recent error/SQLite-fallback log scan, and code rollback to the previous main commit.

- [ ] **Step 7: Merge and archive**

Merge after candidate verification, fast-forward local main, prove `git rev-list --left-right --count HEAD...origin/main` is `0 0`, rerun live forged-enhancement smoke, update evidence to `archived`, and proceed to Slice 0B.

## Slice 0B: Catalyst False-Green Guard

### Task 5: Open Slice 0B and add the red tests

**Files:**
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed/{requirement.json,evidence.json}`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `tests/news_backend_test.py`

**Interfaces:**
- Consumes: `catalyst_overlay_cutover_gate() -> dict` and `season_cutover_readiness_component(...)`.
- Produces: a blocked capability that retains `simcOption=redirected_base_stats` and a deterministic blocker.

- [ ] **Step 1: Create and validate the Strict packet**

Use slug `equipment-simulator-phase0b-catalyst-fail-closed`, branch `codex/equipment-simulator-phase0b-catalyst-fail-closed`, release trigger `health_admin`, fact owner `server/news_backend.py`, and active artifact `artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed`. The requirement must state that parser compatibility remains, capability activation does not, no UI is exposed, no manifest schema changes, and Slice 0A behavior must not change. Acceptance commands are the two Catalyst tests below, `tests.news_backend_test`, backend/full profiles, Harness check, JSON checks, and candidate `/api/data/health` smoke.

- [ ] **Step 2: Add the direct gate red test**

Add:

```python
def test_catalyst_overlay_allowlist_does_not_prove_cutover_capability(self):
    gate = self.backend.catalyst_overlay_cutover_gate()

    self.assertIn("redirected_base_stats", gate["supportedSimcOptions"])
    self.assertEqual(gate["simcOption"], "redirected_base_stats")
    self.assertEqual(gate["status"], "blocked")
    self.assertEqual(gate["capabilityEnabled"], False)
    self.assertTrue(any("proof matrix" in blocker for blocker in gate["blockers"]))
```

In the existing season cutover test, change the Catalyst expectations to:

```python
self.assertEqual(details["catalystOverlay"]["simcOption"], "redirected_base_stats")
self.assertEqual(details["catalystOverlay"]["status"], "blocked")
self.assertTrue(any("proof matrix" in blocker for blocker in details["blockers"]))
```

- [ ] **Step 3: Run red**

Run:

```bash
python3 -m unittest \
  tests.news_backend_test.NewsBackendTest.test_catalyst_overlay_allowlist_does_not_prove_cutover_capability \
  tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_season_cutover_readiness_control_plane
```

Expected: FAIL because the current gate returns `verified` solely from `SIMC_GEAR_OPTION_KEYS` and does not expose `capabilityEnabled=false` or the proof-matrix blocker.

### Task 6: Make Catalyst capability fail closed

**Files:**
- Modify: `server/news_backend.py`

- [ ] **Step 1: Replace the false-green gate**

Use this implementation:

```python
def catalyst_overlay_cutover_gate():
    option_parse_supported = "redirected_base_stats" in SIMC_GEAR_OPTION_KEYS
    blocker = (
        "12.1 Catalyst retained-secondary-stat capability proof matrix is incomplete; "
        "catalog policy, Resolver claims, Serializer output, active SimC runtime, real fixture, "
        "frontend explanation, and Manifest capability binding must all be verified"
    )
    return {
        "status": "blocked",
        "simcOption": "redirected_base_stats",
        "optionParseSupported": option_parse_supported,
        "capabilityEnabled": False,
        "serializerAuthority": "backend",
        "frontendMaySynthesize": False,
        "failClosed": True,
        "supportedSimcOptions": sorted(SIMC_GEAR_OPTION_KEYS),
        "blockers": [blocker],
    }
```

- [ ] **Step 2: Run green and regression**

Run the two-test target, then:

```bash
python3 -m unittest tests.news_backend_test
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_catalyst_redirected_base_stats_is_a_controlled_simc_option
```

Expected: Catalyst tests pass, `redirected_base_stats` parsing remains accepted, and season cutover readiness remains blocked.

### Task 7: Close Slice 0B through candidate deployment

- [ ] Update owner-map characterization and the Phase 0B verification profile.
- [ ] Run backend/full profiles, Harness check, JSON parsing, `git diff --check`, and local CR.
- [ ] Commit with `fix: keep catalyst overlay fail closed`.
- [ ] Push the Slice 0B branch and open its PR.
- [ ] Candidate-deploy with async sync startup disabled.
- [ ] Verify `/api/data/health` returns `season_cutover_readiness.details.catalystOverlay.status=blocked`, `capabilityEnabled=false`, parser option recorded, and the proof-matrix blocker; also smoke public gear initial/slot and confirm timers cannot promote this in-memory gate.
- [ ] Record runtime hashes/logs/rollback, merge, fast-forward main, repeat live health smoke, archive evidence, and proceed to Slice 0C.

## Slice 0C: Legacy Stat Endpoint Containment

### Task 8: Open Slice 0C and add the serializer-flavor red test

**Files:**
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/{requirement.json,evidence.json}`
- Modify: `docs/project-state.json`
- Modify: `docs/roadmap.md`
- Modify: `tests/websim_payload_test.py`

**Interfaces:**
- Consumes: `build_websim_profile(payload, conn=None, execution_flavor="standard_profile")` and legacy `/api/websim/gear/stats`.
- Produces: `standard_profile` default unchanged; `stat_snapshot_v1` with `iterations=1`; `run_websim_stat_simcraft(profile)` serialized by one process-global permit.

- [ ] **Step 1: Create and validate the Strict packet**

Use slug `equipment-simulator-phase0c-legacy-stat-containment`, branch `codex/equipment-simulator-phase0c-legacy-stat-containment`, release trigger `backend_api`, fact owner `server/websim_payload.py`, and active artifact `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment`. Non-goals must explicitly exclude the new async endpoint, migrations, jobs, worker, frontend cutover, and legacy endpoint retirement.

- [ ] **Step 2: Extend the existing HTTP stat test to require the lightweight flavor**

In `test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot`, add:

```python
self.assertIn("iterations=1", executed_profile)
self.assertNotIn("iterations=1000", executed_profile)
self.assertIn("calculate_scale_factors=0", executed_profile)
for key in (
    "statStatus",
    "blockers",
    "primary",
    "stamina",
    "secondary",
    "itemLevel",
    "gearReadiness",
    "talentEncoding",
    "gearItems",
    "simcItems",
):
    self.assertIn(key, result)
```

- [ ] **Step 3: Run the serializer red test**

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot
```

Expected: FAIL because the executed profile currently contains `iterations=1000`.

### Task 9: Add execution flavors and use `stat_snapshot_v1`

**Files:**
- Modify: `server/websim_payload.py`

- [ ] **Step 1: Add constants near the current SimC/profile constants**

```python
WEBSIM_EXECUTION_FLAVOR_STANDARD_PROFILE = "standard_profile"
WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1 = "stat_snapshot_v1"
WEBSIM_EXECUTION_FLAVORS = {
    WEBSIM_EXECUTION_FLAVOR_STANDARD_PROFILE,
    WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
}
```

- [ ] **Step 2: Extend the profile builder without changing the default**

Change the signature and iteration selection:

```python
def build_websim_profile(
    payload,
    conn=None,
    execution_flavor=WEBSIM_EXECUTION_FLAVOR_STANDARD_PROFILE,
):
    execution_flavor = str(execution_flavor or "").strip()
    if execution_flavor not in WEBSIM_EXECUTION_FLAVORS:
        execution_flavor = WEBSIM_EXECUTION_FLAVOR_STANDARD_PROFILE
    iterations = (
        1
        if execution_flavor == WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1
        else int_env("WOW_WEBSIM_SIMC_ITERATIONS", 1000)
    )
    # retain the existing actor, talents, gear, preparation, scenario, target, duration,
    # vary_combat_length, and calculate_scale_factors construction
```

Replace only the iterations line in the existing tail with:

```python
f"iterations={iterations}",
```

- [ ] **Step 3: Select the flavor only for the legacy stat path**

In `build_websim_gear_stats_response`, replace its profile call with:

```python
profile = build_websim_profile(
    request_source,
    conn=conn,
    execution_flavor=WEBSIM_EXECUTION_FLAVOR_STAT_SNAPSHOT_V1,
)
```

Leave `build_websim_profile_response` and simulator submission on the default `standard_profile` flavor.

- [ ] **Step 4: Run green and standard-profile regression**

Run:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_simulate_runs_encoded_profile_through_fake_simc
```

Expected: both pass; legacy stats uses 1 iteration and the normal simulation/profile path keeps its existing standard behavior.

### Task 10: Add the global concurrency-one red test and implementation

**Files:**
- Modify: `tests/websim_payload_test.py`
- Modify: `server/websim_payload.py`

**Interfaces:**
- Consumes: `_run_websim_stat_simcraft_unlocked(profile) -> dict`.
- Produces: `run_websim_stat_simcraft(profile) -> dict` protected by `WEBSIM_GEAR_STATS_SIMC_LIMITER`.

- [ ] **Step 1: Add the concurrency red test**

```python
def test_legacy_gear_stats_simc_execution_has_global_concurrency_one(self):
    state_lock = threading.Lock()
    active = 0
    max_active = 0

    def fake_unlocked(profile):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with state_lock:
            active -= 1
        return {"ran": True, "profile": profile}

    with patch.object(
        self.websim_payload,
        "_run_websim_stat_simcraft_unlocked",
        side_effect=fake_unlocked,
    ):
        threads = [
            threading.Thread(
                target=self.websim_payload.run_websim_stat_simcraft,
                args=(f"profile-{index}",),
            )
            for index in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

    self.assertTrue(all(not thread.is_alive() for thread in threads))
    self.assertEqual(max_active, 1)
```

- [ ] **Step 2: Run red**

Run:

```bash
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_legacy_gear_stats_simc_execution_has_global_concurrency_one
```

Expected: FAIL because `_run_websim_stat_simcraft_unlocked` does not exist and the current execution function has no global one-permit wrapper.

- [ ] **Step 3: Add the process-global limiter and wrapper**

Near the module cache locks add:

```python
WEBSIM_GEAR_STATS_SIMC_LIMITER = threading.BoundedSemaphore(1)
```

Rename the current implementation:

```python
def _run_websim_stat_simcraft_unlocked(profile):
    # exact existing run_websim_stat_simcraft body
```

Add the public wrapper immediately after it:

```python
def run_websim_stat_simcraft(profile):
    with WEBSIM_GEAR_STATS_SIMC_LIMITER:
        return _run_websim_stat_simcraft_unlocked(profile)
```

- [ ] **Step 4: Run green and full legacy stat regressions**

Run:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_legacy_gear_stats_simc_execution_has_global_concurrency_one \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_prefers_simc_json_character_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_blocks_when_simc_is_unavailable \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_sanitizes_simc_crashes
```

Expected: all pass and `max_active == 1`.

### Task 11: Close Phase 0 through candidate deployment and documentation

**Files:**
- Modify: `docs/backend-owner-map.json`
- Modify: `docs/project-owner-map.json`
- Modify: `docs/verification-matrix.md`
- Modify: `docs/gear-simulation-full-chain-runbook.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/project-state.json`
- Modify: `docs/plans/README.md`
- Modify: `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/evidence.json`
- Create: `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/manifest.json`

- [ ] **Step 1: Update current contracts**

Record `stat_snapshot_v1`, `iterations=1`, process-global concurrency one, unchanged legacy response compatibility, and the fact that the endpoint remains synchronous until Phase 5. Mark Phase 0 completed only after all three PRs are merged. Register both planning documents in `docs/plans/README.md` and make `docs/project-state.json` point to the final Phase 0C archived release packet while keeping the overall equipment simulator milestone active for Phase 1.

- [ ] **Step 2: Run complete Phase 0 local verification**

```bash
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment --base origin/main
node scripts/verify-project.js --profile frontend --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment --base origin/main
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment --base origin/main
python3 -m py_compile server/websim_payload.py server/news_backend.py tests/websim_payload_test.py tests/news_backend_test.py
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

Expected: all exit 0; warning output is recorded but does not replace exit-code proof.

- [ ] **Step 3: Local CR**

Confirm:

- standard `/profile` and `/simulate` use the unchanged default flavor;
- only gear stat execution is globally serialized;
- no new route/table/worker/frontend call exists;
- legacy response fields remain;
- Catalyst and enhancement guards from 0A/0B remain green;
- public observed-only and PG-only contracts are unchanged;
- no async sync/backfill is started by the diff.

- [ ] **Step 4: Commit and candidate-deploy**

Commit:

```bash
git commit -m "fix: contain legacy gear stat execution"
```

Push the Slice 0C branch, open its PR, and deploy the exact candidate with:

```bash
WOW_DEPLOY_SKIP_BOOTSTRAP=1 \
WOW_DEPLOY_START_ASYNC_SYNCS=0 \
./server/deploy_lighthouse.sh
```

- [ ] **Step 5: Candidate smoke**

Record:

- `/health=200` and current `/api/data/health` truth without upgrading partial components;
- public gear initial/slot remains observed-only and baseline-empty;
- legacy `/api/websim/gear/stats` returns HTTP 200 and the required legacy fields for a current legal observed Intent;
- a live-module probe of the deployed `build_websim_profile(..., execution_flavor="stat_snapshot_v1")` contains `iterations=1` and not `iterations=1000`;
- a live-module two-thread probe of the wrapper records `maxActive=1`;
- backend/systemd service state, existing timers/sync/backfill activity, recent logs, PostgreSQL-only environment, and runtime file hash parity;
- rollback: redeploy the previous main commit; no database restore is required because Phase 0C has no data/schema writes.

- [ ] **Step 6: Merge, post-merge smoke, and Phase 0 evidence closure**

After candidate pass, merge, fast-forward local main, prove local/remote parity, rerun `/health`, `/api/data/health`, Catalyst blocked state, forged enhancement block, legacy stats shape, lightweight flavor probe, and public observed-only gear sweep. Archive the evidence and immediately create the Phase 1 detailed plan using `superpowers:writing-plans`.

## Phase 0 Self-Review Checklist

- [ ] Every approved Phase 0 requirement maps to exactly one slice.
- [ ] No slice adds `/resolve`, an async endpoint, a Worker, a migration, or frontend state changes.
- [ ] The forged enhancement test fails on the original code for the intended reason.
- [ ] The Catalyst test distinguishes parser compatibility from capability verification.
- [ ] The stat test proves both `iterations=1` and compatibility fields.
- [ ] The concurrency test measures overlap, not merely semaphore existence.
- [ ] Each runtime slice has its own candidate identity, smoke, timer/backflow, rollback, merge, and archive evidence.
- [ ] Owner maps and verification profiles are updated with real test names.
- [ ] `.superpowers/` is never staged.
