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
