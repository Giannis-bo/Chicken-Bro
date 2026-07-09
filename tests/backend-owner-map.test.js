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

  assert.equal(ownerMap.status, 'phase4_pg_selector_callers_routed')
  assert.equal(ownerMap.harnessVersion, 'v0.4')
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
    gearPublicContract.directCallers.includes('server/postgres_cache_store.py PG gear selectors'),
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
  assert.equal(gearTemplateSelectors.status, 'contract_module_callers_routed')
  assert.equal(gearTemplateSelectors.usesModule, 'server/gear_public_contract.py')
  assert.ok(pgOwners.has('sync_state_repository'))
})
