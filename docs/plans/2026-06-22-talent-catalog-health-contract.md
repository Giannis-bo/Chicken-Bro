# Talent Catalog Health Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a read-only `talent_catalog` data-health component and a shared catalog health contract shape for Season Data Cache catalogs.

**Architecture:** Keep SQLite as the current Season Data Cache. Derive talent health from existing `websim_talents`, `websim_spell_details`, `websim_profile_presets`, `websim_community_talent_templates`, and sync-state rows. Do not add external sync, network fetches, or new primary business tables in this slice.

**Tech Stack:** Python backend, SQLite, `unittest`, existing `server/websim_payload.py` and `server/news_backend.py` health helpers.

## Scope

- Add a shared catalog contract helper with stable fields: `status`, `checkedAt`, `schemaRevision`, `revision`, `sourceStatus`, `coverage`, `topBlockers`, `lastError`, and `staleAfter`.
- Preserve existing `gear_catalog.details.*` fields while adding `gear_catalog.details.catalogContract`.
- Add `talent_catalog` to `/api/data/health`, backed only by local SQLite reads.
- Report talent coverage, spell-detail coverage, profile preset coverage, community template coverage, source state, and blockers.
- Keep trust boundaries: no generated truth claims, no Battle.net official verification without credentials, and no network side effects from health.

## Tasks

### Task 1: Define Contract Tests

Files:

- Modify: `tests/news_backend_test.py`
- Modify: `tests/websim_payload_test.py`

Steps:

1. Add a health test proving both `gear_catalog` and `talent_catalog` expose `details.catalogContract`.
2. Add a health test proving `/api/data/health` includes `talent_catalog` and does not call sync functions.
3. Add a payload test proving empty talent data is `blocked` with deterministic blockers.

### Task 2: Implement Read-Only Helpers

Files:

- Modify: `server/websim_payload.py`
- Modify: `server/news_backend.py`

Steps:

1. Add `catalog_health_contract(...)` helper.
2. Add `talent_catalog_counts(...)`, `talent_catalog_revision_from_counts(...)`, and `talent_catalog_health_payload(...)`.
3. Insert `talent_catalog` into `build_data_health_payload()`.
4. Add `catalogContract` to existing gear catalog health details.

### Task 3: Verify and Commit

Commands:

```bash
python3 -m unittest tests.news_backend_test.NewsBackendTest.test_data_health_payload_includes_talent_catalog_component_without_syncing tests.news_backend_test.NewsBackendTest.test_data_health_payload_exposes_catalog_contract_for_core_catalogs -v
python3 -m unittest tests.websim_payload_test.WebSimPayloadTest.test_talent_catalog_health_blocks_missing_local_talent_data -v
python3 -m unittest discover -s tests -p '*_test.py'
node --test tests/*.test.js
python3 server/simulator_e2e_smoke.py
git diff --check
```
