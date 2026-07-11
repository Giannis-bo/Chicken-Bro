# Project Harness Verification Matrix

This matrix defines the local and CI verification profiles for the Project Harness Engineering Normalization milestone. All profiles resolve a single release packet from either `--release` or `docs/project-state.json.activeReleaseArtifact`.

| Profile | Purpose | Commands are owned by |
| --- | --- | --- |
| `harness` | Docs, schemas, owner maps and Harness tooling | `scripts/verify-project.js` |
| `backend` | Python backend, data and read-model contracts | `scripts/verify-project.js` |
| `frontend` | Mini-program JavaScript contract and syntax | `scripts/verify-project.js` |
| `full` | Milestone and PR closure baseline | `scripts/verify-project.js` |

## Local Usage

```bash
node scripts/verify-project.js --profile harness --release artifacts/releases/2026-07-10-executable-project-harness
node scripts/verify-project.js --profile full --release artifacts/releases/2026-07-10-executable-project-harness
```

Use `--dry-run --json` to inspect the exact command list without executing it.

## CI Contract

`.github/workflows/project-harness.yml` resolves the active release from `docs/project-state.json` and invokes:

```bash
node scripts/verify-project.js --profile harness --release "$ACTIVE_RELEASE" --base origin/main
node scripts/verify-project.js --profile full --release "$ACTIVE_RELEASE" --base origin/main
```

The workflow does not deploy, SSH, install repository dependencies, run migrations, trigger sync jobs, or write production data. Failing tests, invalid JSON, owner-map conflicts, Harness packet failures, syntax failures, or whitespace errors must return nonzero.

## Equipment Simulator Phase 0A Profile

The Strict Slice 0A packet at `artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard` adds a PostgreSQL-only serializer safety profile. Run it before candidate deployment:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_pg_only_structured_enhancement_rejects_client_catalog_forgery \
  tests.websim_payload_test.WebSimPayloadTest.test_merge_enhancements_strips_forged_server_authority_marker \
  tests.websim_payload_test.WebSimPayloadTest.test_enhancement_validator_defaults_to_no_server_authority \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_blocks_uncatalogued_options \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_uses_server_catalog_over_client_options \
  tests.websim_payload_test.WebSimPayloadTest.test_structured_enhancement_snapshot_rejects_catalog_options_without_item_capability
python3 -m unittest tests.websim_payload_test tests.news_backend_test
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard \
  --base origin/main
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0a-pg-enhancement-guard/evidence.json \
  --base origin/main
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

Candidate verification must additionally prove exact PR commit/runtime hash parity, PostgreSQL-only `/api/websim/profile` rejection of a forged client enhancement, unchanged public observed-only gear initial/slot payloads, current timer/backflow state, recent logs, and `code_rollback` to the previous main commit.

## Equipment Simulator Phase 0B Profile

The Strict Slice 0B packet at `artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed` separates SimC parser compatibility from Catalyst capability proof. Run it before candidate deployment:

```bash
python3 -m unittest \
  tests.news_backend_test.NewsBackendTest.test_catalyst_overlay_allowlist_does_not_prove_cutover_capability \
  tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_season_cutover_readiness_control_plane \
  tests.news_backend_test.NewsBackendTest.test_catalyst_redirected_base_stats_is_a_controlled_simc_option
python3 -m unittest tests.news_backend_test
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed \
  --base origin/main
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0b-catalyst-fail-closed/evidence.json \
  --base origin/main
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

Candidate verification must additionally prove final PR-head/runtime hash parity, `WOW_DATABASE_RUNTIME=postgres_only`, live `/api/data/health` Catalyst `status=blocked` with `capabilityEnabled=false`, `optionParseSupported=true` and the proof-matrix blocker, unchanged public observed-only initial/slot payloads, current timer/backflow state, recent logs, and `code_rollback` to the previous main commit.

## Equipment Simulator Phase 0C Profile

The Strict Slice 0C packet at `artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment` contains the synchronous legacy stat endpoint until the Phase 5 Worker cutover. Run the complete Phase 0 verification before candidate deployment:

```bash
python3 -m unittest \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_runs_fake_simc_for_verified_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_simulate_runs_encoded_profile_through_fake_simc \
  tests.websim_payload_test.WebSimPayloadTest.test_legacy_gear_stats_simc_execution_has_global_concurrency_one \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_prefers_simc_json_character_snapshot \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_blocks_when_simc_is_unavailable \
  tests.websim_payload_test.WebSimPayloadTest.test_http_websim_gear_stats_sanitizes_simc_crashes
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/builds-page.test.js tests/frontend-api-client.test.js
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment \
  --base origin/main
node scripts/verify-project.js --profile frontend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment \
  --base origin/main
node scripts/project-harness.js --check \
  --requirement-file artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/requirement.json \
  --evidence-file artifacts/releases/2026-07-10-equipment-simulator-phase0c-legacy-stat-containment/evidence.json \
  --base origin/main
python3 -m py_compile server/websim_payload.py server/news_backend.py tests/websim_payload_test.py tests/news_backend_test.py
python3 -m json.tool docs/backend-owner-map.json >/dev/null
python3 -m json.tool docs/project-owner-map.json >/dev/null
python3 -m json.tool docs/project-state.json >/dev/null
git diff --check
```

Candidate verification must additionally prove final PR-head/runtime hash parity, `WOW_DATABASE_RUNTIME=postgres_only`, legacy HTTP response fields, live-module `stat_snapshot_v1` `iterations=1`, two-thread `maxActive=1`, unchanged standard profile behavior, Phase 0A forged-enhancement and Phase 0B Catalyst guards, unchanged public observed-only initial/slot payloads, current timer/backflow state, recent logs, and `code_rollback` to the previous main commit.

## Equipment Simulator Phase 1 Contract Profile

The Strict Phase 1 packet at `artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority` defines a dormant resolver boundary. Run it before candidate deployment:

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase1-contracts-rule-authority \
  --base origin/main
python3 -m py_compile \
  server/gear_contracts.py \
  server/gear_result_envelope.py \
  server/gear_rule_matrix.py
```

Phase 1 is contract-only and has no active runtime consumer. Selection Intent rejects client-authored final facts; selection, resolved-gear and profile signatures each declare a different dependency subset; the Result Envelope HTTP mapping stays dormant until Phase 3; and the ordered pure Rule Matrix reports legality without producing a Resolved Snapshot. The current facade, frontend, PostgreSQL selectors and observed-only public read model remain active.

Candidate verification must prove the new modules import on the deployed runtime tree while the current gear/profile/health surfaces and the Phase 0A–0C guards remain unchanged. Deployment does not activate a route, selector, Worker, sync job, database write, or Catalyst capability.

## Equipment Simulator Phase 2A Pure Resolver Profile

The Strict Slice 2A packet at `artifacts/releases/2026-07-10-equipment-simulator-phase2a-pure-resolver` adds a pure canonical Resolver and five-group Evidence Ledger without activating a runtime consumer. Run it before candidate deployment:

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test \
  tests.gear_evidence_ledger_test \
  tests.gear_resolver_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase2a-pure-resolver \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase2a-pure-resolver \
  --base origin/main
python3 -m py_compile \
  server/gear_contracts.py \
  server/gear_result_envelope.py \
  server/gear_rule_matrix.py \
  server/gear_evidence_ledger.py \
  server/gear_resolver.py
```

Slice 2A fixes the slot pipeline at base item → verified variant → verified overlay → effective capabilities → legal enhancements. It returns structured static facts, canonical set state, ordered legality, readiness, constraints, serializer input and immutable Evidence Claim IDs; it never produces a profile string or DPS. Missing authority, evidence, resolved stats or overlay identity fails closed, and dynamic effects never become static attributes.

Candidate verification must prove exact PR-head hashes and pure fixture outputs on the remote runtime tree while `/resolve` remains 404 and the current facade, PostgreSQL selectors, public observed-only payload, Phase 0A–0C guards, Phase 1 contracts, Catalyst blocker, timers and logs remain unchanged. Deployment does not activate a loader, facade, route, frontend consumer, Worker, write, migration, sync or cleanup.

## Equipment Simulator Phase 2B PG Loader and Dormant Facade Profile

The Strict Slice 2B packet at `artifacts/releases/2026-07-10-equipment-simulator-phase2b-pg-loader-facade-parity` adds the PostgreSQL-only Authority Context loader, bounded cache, one dormant store method, server-owned runtime-authority projection and resolved-snapshot serializer parity facade. Run it before candidate deployment:

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test \
  tests.gear_evidence_ledger_test \
  tests.gear_resolver_test \
  tests.pg_gear_authority_loader_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase2b-pg-loader-facade-parity \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-10-equipment-simulator-phase2b-pg-loader-facade-parity \
  --base origin/main
python3 -m py_compile \
  server/gear_evidence_ledger.py \
  server/gear_resolver.py \
  server/pg_gear_authority_loader.py \
  server/postgres_cache_store.py \
  server/websim_payload.py
```

Cold reads execute exactly three static domain queries for one or sixteen slots; a warm hit executes only the revision query. The item/variant query must accept both an exact PG variant key and the existing `normalize_option_value` public alias, bind aliases to the requested item, block collisions, deduplicate reused pairs, project Battle.net structured armor/weapon/handedness and equivalent-slot facts through existing helpers, aggregate canonical trusted tier set IDs with conflict blocking, and cap source evidence at one latest row per type/eight rows per item. The cache is bounded by both entry count and canonical serialized bytes, keys bind the complete dependency vector and selection signature, and incomplete/transient authority is never cached. Loader output identifies `compatibility-pg-live-v1` as a compatibility view with `formalActiveManifest=false`; Phase 4 remains the formal Active Season Manifest owner.

Candidate verification must execute the loader against the live PostgreSQL schema inside one read-only transaction, prove the cold/warm query budget, import the dormant facade, and reproduce the checked-in parity fixture. It must also prove no current route, serializer call site, Worker, frontend, sync job or public payload consumes either adapter: `/resolve` remains 404, the current `/profile` behavior stays unchanged, Catalyst remains fail-closed, and Phase 0–2A/public/timer/log guards remain green.

## Equipment Simulator Phase 3A Resolve/Profile API Profile

The Strict Slice 3A packet at `artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api` activates the Phase 2 boundary through a backend runtime orchestrator. Before candidate deployment run:

```bash
python3 -m unittest \
  tests.gear_contracts_test \
  tests.gear_result_envelope_test \
  tests.gear_rule_matrix_test \
  tests.gear_evidence_ledger_test \
  tests.gear_resolver_test \
  tests.pg_gear_authority_loader_test \
  tests.gear_runtime_test
python3 -m unittest tests.websim_payload_test tests.postgres_cache_store_test tests.news_backend_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase3a-resolve-profile-api \
  --base origin/main
python3 -m py_compile \
  server/gear_runtime.py \
  server/pg_gear_authority_loader.py \
  server/postgres_cache_store.py \
  server/news_backend.py
```

Slice 3A must add `resolverContext` from the same live revision authority as the loader, keep `formalActiveManifest=false`, map `/gear/resolve` through exact 200/400/409/503 Result Envelope semantics, and make only profile bodies containing `selectionIntent` enter canonical re-resolve mode. Legacy profile bodies and `/gear/stats` remain compatible. Candidate evidence requires 40/40 public observed Intent resolution, representative canonical profile output, malformed/stale/illegal/missing-authority probes, fixed query and latency budgets, public observed-only/baseline-empty parity, PostgreSQL-only runtime, no deploy-driven async work, truthful SimC updater state, logs and code-only rollback.

## Equipment Simulator Phase 4A Pure Release Contracts Profile

The Strict Slice 4A packet at `artifacts/releases/2026-07-11-equipment-simulator-phase4a-release-contracts` adds only a dependency-free release policy domain. Before candidate deployment run:

```bash
python3 -m unittest \
  tests.gear_release_test \
  tests.gear_contracts_test \
  tests.gear_resolver_test \
  tests.gear_evidence_ledger_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase4a-release-contracts \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase4a-release-contracts \
  --base origin/main
python3 -m py_compile server/gear_release.py
git diff --check
```

Slice 4A must prove canonical hash-addressed Gear/Community Releases, exact manifest binding, deterministic observed winner/standby election, rejection of illegal/stale/source-invalid/mixed-release candidates, strict 40-spec shadow classification, risk-classified promotion decisions and pointer compare-and-swap command shapes. `server/gear_release.py` has no SQL, store, route, environment, filesystem, network, clock or process-execution owner and calls current Resolver behavior only through an injected callable. Candidate deployment proves import/hash/pure fixture parity and unchanged live gear/Profile/health/Catalyst behavior; no schema, write, release row, shadow reader, formal pointer, timer or public cutover may be claimed.

## Equipment Simulator Phase 4B PG Registry And Legacy Import Profile

The Strict Slice 4B packet at `artifacts/releases/2026-07-11-equipment-simulator-phase4b-pg-registry-legacy-import` adds one append-only PostgreSQL release registry/repository and one explicit inactive import tool. Before candidate deployment run:

```bash
python3 -m unittest \
  tests.gear_release_tool_test \
  tests.gear_release_store_test \
  tests.gear_release_test \
  tests.pg_gear_authority_loader_test \
  tests.gear_resolver_test \
  tests.postgres_schema_test
node --test tests/project-harness.test.js tests/backend-owner-map.test.js tests/project-owner-map.test.js tests/project-state.test.js
node scripts/verify-project.js --profile backend \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase4b-pg-registry-legacy-import \
  --base origin/main
node scripts/verify-project.js --profile full \
  --release artifacts/releases/2026-07-11-equipment-simulator-phase4b-pg-registry-legacy-import \
  --base origin/main
python3 -m py_compile \
  server/gear_release.py \
  server/gear_release_store.py \
  server/gear_release_tool.py \
  server/pg_gear_authority_loader.py
git diff --check
```

Slice 4B must prove an additive immutable schema, exact-descriptor idempotency, repeatable-read legacy snapshots, inactive Gear/Community `legacy-import-r0` construction, exact candidate Gear Release authority binding, current Resolver revalidation, strict pointer CAS validation and zero pointer mutation. Candidate deployment requires a pre-migration PostgreSQL backup, exact implementation identity, migration/grant/trigger inspection, inactive release row/count/hash evidence, zero active pointer rows, unchanged 40/40 observed-only public selection with zero baseline/formal manifest activation, Resolve/Profile/health/Catalyst parity, timer/backflow state and an explicit rollback path. No public/shadow reader, pointer promotion, scheduled refresh, Catalyst capability enablement or public cutover may be claimed.
