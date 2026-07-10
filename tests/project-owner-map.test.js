const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const projectOwnerMapPath = 'docs/project-owner-map.json'
const backendOwnerMapPath = 'docs/backend-owner-map.json'
const appConfigPath = 'app.json'

const CRITICAL_DOMAIN_IDS = [
  'app_shell_route_runtime',
  'frontend_api_auth_transport',
  'personal_build_template_assets',
  'news_content_public_api',
  'websim_gear_public_read_model',
  'websim_talent_public_read_model',
  'websim_loot_assets_bootstrap',
  'simc_template_task_pipeline',
  'chickenbro_session_evidence_pipeline',
  'external_source_provenance',
  'postgres_runtime_schema_boundary',
  'cache_sync_state_repository',
  'scheduled_sync_backfill_cleanup',
  'health_admin_observability',
  'deploy_runtime_services',
  'ui_runtime_evidence'
]

const BACKEND_FACT_DOMAINS = new Set([
  'news_content_public_api',
  'websim_gear_public_read_model',
  'websim_talent_public_read_model',
  'websim_loot_assets_bootstrap',
  'simc_template_task_pipeline',
  'chickenbro_session_evidence_pipeline',
  'external_source_provenance',
  'postgres_runtime_schema_boundary',
  'cache_sync_state_repository',
  'scheduled_sync_backfill_cleanup',
  'health_admin_observability'
])

const CHARACTERIZATION_STATUSES = new Set([
  'characterized',
  'gap_closed',
  'health_watch',
  'blocked'
])

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function assertPathExists(relativePath, label = relativePath) {
  assert.ok(fs.existsSync(relativePath), `${label} should exist at ${relativePath}`)
}

function assertPathListExists(paths, label) {
  for (const item of paths || []) {
    if (typeof item === 'string' && item.includes('::')) {
      assertPathExists(item.split('::')[0], label)
    } else {
      assertPathExists(item, label)
    }
  }
}

function readOwnerMap() {
  assertPathExists(projectOwnerMapPath)
  return readJson(projectOwnerMapPath)
}

test('project owner map freezes the 16 critical domains with no unknown or blocked owners', () => {
  const ownerMap = readOwnerMap()
  assert.equal(ownerMap.schemaVersion, 1)
  assert.equal(ownerMap.status, 'project_owner_map_active')
  assert.equal(ownerMap.harnessVersion, 'v0.5')
  assert.equal(ownerMap.unownedCriticalDomains, 0)
  assert.equal(ownerMap.conflictingFactOwners, 0)

  const domains = ownerMap.criticalDomains
  assert.ok(Array.isArray(domains), 'criticalDomains should be an array')
  assert.deepEqual(domains.map((domain) => domain.id), CRITICAL_DOMAIN_IDS)
  assert.equal(new Set(domains.map((domain) => domain.id)).size, CRITICAL_DOMAIN_IDS.length)

  for (const domain of domains) {
    assert.ok(domain.factOwner, `${domain.id} should declare a factOwner`)
    assert.notEqual(domain.factOwner, 'unknown', `${domain.id} factOwner should not be unknown`)
    assert.notEqual(domain.status, 'blocked', `${domain.id} should not remain blocked`)
    assert.ok(Array.isArray(domain.consumers), `${domain.id}.consumers should be an array`)
    assert.ok(Array.isArray(domain.publicContracts), `${domain.id}.publicContracts should be an array`)
    assert.ok(Array.isArray(domain.mustNotChange), `${domain.id}.mustNotChange should be an array`)
    assert.ok(Array.isArray(domain.characterization), `${domain.id}.characterization should be an array`)
    assert.ok(domain.characterization.length > 0, `${domain.id} should point at characterization tests`)
    assert.ok(Array.isArray(domain.runtimeSurfaces), `${domain.id}.runtimeSurfaces should be an array`)
    assert.ok(Array.isArray(domain.runbooks), `${domain.id}.runbooks should be an array`)
    assert.ok(Array.isArray(domain.rollback), `${domain.id}.rollback should be an array`)
    assert.ok(domain.rollback.length > 0, `${domain.id} should declare rollback`)
    assert.ok(Array.isArray(domain.verificationProfiles), `${domain.id}.verificationProfiles should be an array`)
    assert.ok(domain.verificationProfiles.length > 0, `${domain.id} should map to a verification profile`)
    assert.ok(domain.releaseTrigger, `${domain.id} should map to a release trigger`)
  }
})

test('project owner map only points at existing owner, consumer, test and runbook paths', () => {
  const ownerMap = readOwnerMap()
  for (const domain of ownerMap.criticalDomains) {
    assertPathExists(domain.factOwner, `${domain.id}.factOwner`)
    if (domain.writeOwner) {
      assertPathExists(domain.writeOwner, `${domain.id}.writeOwner`)
    }
    assertPathListExists(domain.consumers, `${domain.id}.consumers`)
    assertPathListExists(domain.characterization, `${domain.id}.characterization`)
    assertPathListExists(domain.runtimeSurfaces, `${domain.id}.runtimeSurfaces`)
    assertPathListExists(domain.runbooks, `${domain.id}.runbooks`)
  }
})

test('write-capable critical domains declare write owners and role boundaries', () => {
  const ownerMap = readOwnerMap()
  const writeCapable = ownerMap.criticalDomains.filter((domain) => domain.writeBehavior === true)
  assert.ok(writeCapable.length > 0, 'at least one domain should record write behavior')
  for (const domain of writeCapable) {
    assert.ok(domain.writeOwner, `${domain.id} writes state and must declare writeOwner`)
    assertPathExists(domain.writeOwner, `${domain.id}.writeOwner`)
  }

  for (const domain of ownerMap.criticalDomains) {
    if (BACKEND_FACT_DOMAINS.has(domain.id)) {
      assert.ok(!domain.factOwner.startsWith('pages/'), `${domain.id} backend facts cannot be owned by frontend pages`)
    }
    if (domain.id === 'health_admin_observability') {
      assert.equal(domain.ownerRole, 'consumer_orchestrator')
      assert.notEqual(domain.factOwner, 'server/news_backend.py')
    }
    if (domain.id === 'deploy_runtime_services') {
      assert.equal(domain.ownerRole, 'consumer_orchestrator')
      assert.notEqual(domain.factOwner, 'server/deploy_lighthouse.sh')
    }
  }
})

test('project owner map covers changed paths, profiles and release triggers for every critical domain', () => {
  const ownerMap = readOwnerMap()
  const requiredProfiles = new Set(['harness', 'backend', 'frontend', 'full'])
  const allowedReleaseTriggers = new Set([
    'docs_tooling_only',
    'frontend_user_visible',
    'backend_api',
    'pg_read_model',
    'public_payload',
    'health_admin',
    'scheduled_jobs',
    'deploy_scripts',
    'user_visible_runtime'
  ])

  for (const domain of ownerMap.criticalDomains) {
    assert.ok(Array.isArray(domain.changedPathPatterns), `${domain.id} should map changed paths`)
    assert.ok(domain.changedPathPatterns.length > 0, `${domain.id} should have changed path patterns`)
    for (const profile of domain.verificationProfiles) {
      assert.ok(requiredProfiles.has(profile), `${domain.id} uses unknown verification profile ${profile}`)
    }
    assert.ok(allowedReleaseTriggers.has(domain.releaseTrigger), `${domain.id} uses unknown release trigger ${domain.releaseTrigger}`)
  }
})

test('ui runtime evidence domain explicitly covers every app.json route', () => {
  const ownerMap = readOwnerMap()
  const appConfig = readJson(appConfigPath)
  const uiDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'ui_runtime_evidence')
  assert.ok(uiDomain, 'ui_runtime_evidence domain should exist')
  assert.deepEqual(uiDomain.appRoutes, appConfig.pages)
  assert.equal(uiDomain.appRoutes.length, 14)
})

test('project owner map and backend owner map do not conflict on backend hotspot fact owners', () => {
  const ownerMap = readOwnerMap()
  const backendOwnerMap = readJson(backendOwnerMapPath)
  const projectBackendRefs = new Map(
    ownerMap.criticalDomains
      .filter((domain) => domain.backendOwnerMapRef)
      .map((domain) => [domain.id, domain])
  )

  for (const domain of projectBackendRefs.values()) {
    const hotspot = backendOwnerMap.hotspotFiles.find((entry) => entry.path === domain.backendOwnerMapRef.hotspotFile)
    assert.ok(hotspot, `${domain.id} should reference an existing backend hotspot`)
    const owner = hotspot.owners.find((entry) => entry.id === domain.backendOwnerMapRef.ownerId)
    assert.ok(owner, `${domain.id} should reference an existing backend hotspot owner`)
    assert.ok(
      domain.factOwner === domain.backendOwnerMapRef.factOwner || domain.factOwner === hotspot.path,
      `${domain.id} project factOwner should not conflict with backend owner map`
    )
  }
})

test('critical contract characterization has no unknown or blocked domains', () => {
  const ownerMap = readOwnerMap()
  assert.equal(ownerMap.criticalContractUnknown, 0)
  assert.equal(ownerMap.criticalContractBlocked, 0)

  for (const domain of ownerMap.criticalDomains) {
    assert.ok(domain.criticalContract, `${domain.id} should record a critical contract conclusion`)
    assert.ok(
      CHARACTERIZATION_STATUSES.has(domain.criticalContract.status),
      `${domain.id} has invalid critical contract status ${domain.criticalContract.status}`
    )
    assert.notEqual(domain.criticalContract.status, 'blocked', `${domain.id} must not block milestone closure`)
    assert.notEqual(domain.criticalContract.status, 'unknown', `${domain.id} must not stay unknown`)
    assert.ok(domain.criticalContract.summary, `${domain.id} should summarize the characterization conclusion`)
    assert.ok(Array.isArray(domain.criticalContract.coverage), `${domain.id}.criticalContract.coverage should be an array`)
    assert.ok(domain.criticalContract.coverage.length > 0, `${domain.id} should list characterization coverage`)
    assertPathListExists(domain.criticalContract.coverage, `${domain.id}.criticalContract.coverage`)
    if (domain.criticalContract.status === 'health_watch') {
      assert.ok(domain.healthWatchTrigger, `${domain.id} health_watch should record its trigger`)
    }
  }
})
