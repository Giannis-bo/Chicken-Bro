const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const ownerMapPath = 'docs/backend-owner-map.json'

function readOwnerMap() {
  return JSON.parse(fs.readFileSync(ownerMapPath, 'utf8'))
}

test('backend owner map defines the backend hotspot ownership contract', () => {
  assert.ok(fs.existsSync(ownerMapPath), 'docs/backend-owner-map.json should exist before backend hotspot splitting')
  const ownerMap = readOwnerMap()

  assert.equal(ownerMap.status, 'phase4_season_catalog_candidate_selector_extracted')
  assert.equal(ownerMap.harnessVersion, 'v0.5')
  assert.equal(ownerMap.defaultEvidenceLevel, 'local_verified')
  assert.ok(ownerMap.rules.mustHaveCharacterizationBeforeExtraction)

  const files = new Map(ownerMap.hotspotFiles.map((entry) => [entry.path, entry]))
  for (const filePath of [
    'server/websim_payload.py',
    'server/news_backend.py',
    'server/postgres_cache_store.py'
  ]) {
    assert.ok(files.has(filePath), `${filePath} should be listed as a backend hotspot`)
    assert.ok(files.get(filePath).owners.length >= 3, `${filePath} should have at least three owner entries`)
  }

  const websimOwners = new Map(files.get('server/websim_payload.py').owners.map((owner) => [owner.id, owner]))
  const gearPublicContract = websimOwners.get('gear_public_contract')
  assert.ok(gearPublicContract, 'websim_payload should name gear_public_contract as an owner')
  assert.equal(gearPublicContract.status, 'extracted_adapter')
  assert.equal(gearPublicContract.extractedModule, 'server/gear_public_contract.py')
  assert.ok(
    gearPublicContract.directCallers.includes('server/pg_gear_template_selectors.py PG selector helper'),
    'gear public contract should record PG selector direct callers'
  )
  assert.deepEqual(gearPublicContract.publicEntryPolicy.allowedCommunitySourceKeys, ['raiderio_observed_profile'])
  assert.deepEqual(gearPublicContract.publicEntryPolicy.blockedPublicSourceKeys, [
    'recommended_bis',
    'season_recommendation',
    'default_template',
    'simc_preset',
    'baseline_blocked'
  ])
  assert.ok(
    gearPublicContract.characterization.some((entry) => entry.includes('test_real_player_public_policy_applies_to_all_specs')),
    'gear public contract should point at the observed-only characterization test'
  )
  assert.ok(
    gearPublicContract.characterization.some((entry) => entry.includes('tests/gear_public_contract_test.py')),
    'gear public contract should point at the adapter module boundary test'
  )

  const newsOwners = new Map(files.get('server/news_backend.py').owners.map((owner) => [owner.id, owner]))
  assert.ok(newsOwners.has('runtime_api_wiring'))
  assert.ok(newsOwners.has('health_admin_summary'))

  const pgOwners = new Map(files.get('server/postgres_cache_store.py').owners.map((owner) => [owner.id, owner]))
  const gearTemplateSelectors = pgOwners.get('gear_template_selectors')
  assert.ok(gearTemplateSelectors)
  assert.equal(gearTemplateSelectors.status, 'read_model_adapter_extracted')
  assert.equal(gearTemplateSelectors.extractedModule, 'server/pg_gear_template_selectors.py')
  assert.equal(gearTemplateSelectors.usesModule, 'server/gear_public_contract.py')
  assert.ok(
    gearTemplateSelectors.characterization.some((entry) => entry.includes('tests/pg_gear_template_selectors_test.py')),
    'gear template selectors should point at the helper module characterization test'
  )
  const gearCatalogReadModelSelectors = pgOwners.get('gear_catalog_read_model_selectors')
  assert.ok(gearCatalogReadModelSelectors)
  assert.equal(gearCatalogReadModelSelectors.status, 'extracted_selector')
  assert.equal(gearCatalogReadModelSelectors.extractedModule, 'server/pg_gear_read_model_selectors.py')
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('tests/pg_gear_read_model_selectors_test.py')),
    'gear catalog read-model selectors should point at the helper module characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('catalog state health and coverage envelope fragments'),
    'gear catalog read-model selectors should own the catalog state envelope after the Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('initial gear baseline and equipped read-model fragments'),
    'gear catalog read-model selectors should own initial baseline/equipped fragments after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('common gear payload read-model fragments'),
    'gear catalog read-model selectors should own common gear payload fragments after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('catalog output mode read-model fragments'),
    'gear catalog read-model selectors should own catalog output mode fragments after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('gear source row read-model grouping'),
    'gear catalog read-model selectors should own gear source row grouping after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('gear variant row read-model grouping'),
    'gear catalog read-model selectors should own gear variant row grouping after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('gear mod option row read-model grouping'),
    'gear catalog read-model selectors should own gear mod option row grouping after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('gear catalog item row read-model assembly'),
    'gear catalog read-model selectors should own gear catalog item row assembly after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('gear mod option type read-model grouping'),
    'gear catalog read-model selectors should own gear mod option type grouping after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.owns.includes('season recommended catalog candidate slot grouping'),
    'gear catalog read-model selectors should own season recommended catalog candidate grouping after this Phase 4 split'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_catalog_state_read_model_fragment_exposes_health_and_coverage_envelope')),
    'gear catalog read-model selectors should point at the catalog state envelope characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_initial_gear_read_model_fragment_compacts_baseline_template')),
    'gear catalog read-model selectors should point at the initial gear fragment characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_common_gear_read_model_fragment_blocks_stat_snapshot')),
    'gear catalog read-model selectors should point at the common gear payload fragment characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_catalog_output_read_model_fragment_keeps_full_debug_fields_out_of_compact_payload')),
    'gear catalog read-model selectors should point at the catalog output fragment characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_gear_sources_by_item_read_model_groups_source_rows')),
    'gear catalog read-model selectors should point at the gear source row grouping characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_gear_variants_by_item_read_model_groups_variant_rows')),
    'gear catalog read-model selectors should point at the gear variant row grouping characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_gear_mod_options_by_slot_read_model_groups_option_rows')),
    'gear catalog read-model selectors should point at the gear mod option row grouping characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_gear_catalog_items_read_model_enriches_item_rows')),
    'gear catalog read-model selectors should point at the gear catalog item row assembly characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_gear_mod_options_by_type_read_model_groups_option_types')),
    'gear catalog read-model selectors should point at the gear mod option type grouping characterization test'
  )
  assert.ok(
    gearCatalogReadModelSelectors.characterization.some((entry) => entry.includes('test_build_season_recommended_catalog_candidates_by_slot_read_model_filters_and_limits_candidates')),
    'gear catalog read-model selectors should point at the season recommended catalog candidate grouping characterization test'
  )
  assert.ok(pgOwners.has('sync_state_repository'))
})
