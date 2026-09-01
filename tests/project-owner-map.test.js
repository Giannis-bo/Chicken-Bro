const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const projectOwnerMapPath = 'docs/project-owner-map.json'
const backendOwnerMapPath = 'docs/backend-owner-map.json'
const appConfigPath = 'app.json'
const taroAppConfigPath = 'apps/mini-taro/src/app.config.ts'
const auxiliaryAuthRoute = 'pages/auth/web-login-confirm'

const CRITICAL_DOMAIN_IDS = [
  'app_shell_route_runtime',
  'frontend_api_auth_transport',
  'platform_v2_foundation',
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
  'ui_runtime_evidence',
  'exact_first_runtime_authority_release_task5c'
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

test('project owner map freezes the 18 critical domains with no unknown or blocked owners', () => {
  const ownerMap = readOwnerMap()
  assert.equal(ownerMap.schemaVersion, 1)
  assert.equal(ownerMap.status, 'project_owner_map_active')
  assert.equal(ownerMap.harnessVersion, 'v0.6.4')
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

test('deploy runtime services maps the manual talent graph recovery unit and its characterization', () => {
  const ownerMap = readOwnerMap()
  const deployDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'deploy_runtime_services')

  assert.ok(deployDomain, 'deploy_runtime_services domain should exist')
  assert.ok(deployDomain.consumers.includes('server/wow-talent-graph-recovery.service'))
  assert.ok(deployDomain.runtimeSurfaces.includes('server/wow-talent-graph-recovery.service'))
  assert.ok(deployDomain.characterization.includes('tests/deploy_lighthouse_test.py'))
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

test('Web login confirmation is registered as auxiliary and excluded from product ownership', () => {
  const ownerMap = readOwnerMap()
  const taroAppConfig = fs.readFileSync(taroAppConfigPath, 'utf8')
  const uiDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'ui_runtime_evidence')

  assert.match(taroAppConfig, new RegExp(`['"]${auxiliaryAuthRoute}['"]`))
  assert.ok(uiDomain, 'ui_runtime_evidence domain should exist')
  assert.deepEqual(uiDomain.auxiliaryRoutes, [{
    route: auxiliaryAuthRoute,
    role: 'auxiliary_auth',
    owner: 'apps/mini-taro/src/pages/auth/web-login-confirm.tsx',
  }])
  assert.ok(!uiDomain.activeRouteOwners.some((entry) => entry.route === auxiliaryAuthRoute))
})

test('Taro and typed packages own the active frontend contract while root routes and pages remain compatibility consumers', () => {
  const ownerMap = readOwnerMap()
  const appConfig = readJson(appConfigPath)
  const appShellDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'app_shell_route_runtime')
  const transportDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'frontend_api_auth_transport')
  const templateDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'personal_build_template_assets')
  const uiDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'ui_runtime_evidence')

  assert.ok(appShellDomain, 'app_shell_route_runtime domain should exist')
  assert.ok(transportDomain, 'frontend_api_auth_transport domain should exist')
  assert.ok(templateDomain, 'personal_build_template_assets domain should exist')
  assert.ok(uiDomain, 'ui_runtime_evidence domain should exist')
  assert.equal(transportDomain.factOwner, 'packages/api-client/src')
  assert.ok(transportDomain.consumers.includes('pages/common/api-client.js'))
  assert.ok(transportDomain.consumers.includes('pages/common/auth-client.js'))
  for (const activeConsumer of [
    'packages/api-client/src/templates.ts',
    'apps/mini-taro/src/pages/profile/profile.tsx',
    'apps/mini-taro/src/pages/builds/detail.tsx',
    'apps/mini-taro/src/pages/builds/talent-simulator.tsx',
    'apps/mini-taro/src/pages/simulator/simc.tsx',
  ]) {
    assert.ok(templateDomain.consumers.includes(activeConsumer), `template domain should include ${activeConsumer}`)
    assert.ok(templateDomain.runtimeSurfaces.includes(activeConsumer), `template runtime should include ${activeConsumer}`)
  }

  assert.deepEqual(uiDomain.activeRouteOwners.map((entry) => entry.route), appConfig.pages)
  assert.equal(uiDomain.activeRouteOwners.length, 14)
  for (const routeOwner of uiDomain.activeRouteOwners) {
    assert.equal(routeOwner.role, 'active_taro_route_owner')
    assert.equal(routeOwner.owner, `apps/mini-taro/src/${routeOwner.route}.tsx`)
    assert.equal(routeOwner.legacyCompatibilityConsumer, `${routeOwner.route}.js`)
    assertPathExists(routeOwner.owner, `${routeOwner.route} active Taro owner`)
    assertPathExists(routeOwner.legacyCompatibilityConsumer, `${routeOwner.route} legacy compatibility consumer`)
  }

  assert.deepEqual(uiDomain.legacyCompatibility, {
    appConfig: 'app.json',
    appConfigRole: 'root_route_compatibility_surface',
    pagesRoot: 'pages',
    pagesRole: 'legacy_route_compatibility_consumers',
    retirement: 'retain_without_new_first_level_ownership',
    deletionRequirement: 'prove_no_active_callers_before_individual_legacy_deletion'
  })
  assert.ok(appShellDomain.consumers.includes('app.json'))
  assert.ok(appShellDomain.consumers.includes('pages'))
  assertPathExists(uiDomain.legacyCompatibility.appConfig)
  assertPathExists(uiDomain.legacyCompatibility.pagesRoot)
})

test('v2 platform foundation separates composition from business facts and protects legacy surfaces', () => {
  const ownerMap = readOwnerMap()
  const domain = ownerMap.criticalDomains.find((entry) => entry.id === 'platform_v2_foundation')

  assert.ok(domain, 'platform_v2_foundation should exist')
  assert.equal(domain.ownerRole, 'consumer_orchestrator')
  assert.equal(domain.factOwner, 'server/app/main.py')
  assert.equal(domain.writeOwner, 'server/app/worker/leases.py')
  assert.ok(domain.consumers.includes('server/app/identity'))
  assert.ok(domain.consumers.includes('server/app/chickenbro'))
  assert.ok(domain.consumers.includes('server/app/simulation'))
  assert.ok(domain.consumers.includes('packages/api-client/src/platform-v2.ts'))
  assert.ok(domain.mustNotChange.some((entry) => entry.includes('server/news_backend.py')))
  assert.ok(domain.mustNotChange.some((entry) => entry.includes('Active Manifest')))
  assert.ok(domain.changedPathPatterns.includes('server/app/**'))
  assert.ok(domain.characterization.includes('tests/app_api_test.py'))
  assert.ok(domain.characterization.includes('packages/api-client/src/platform-v2.test.ts'))
})

test('compatibility retirement requires caller proof for legacy routes dormant products and backend seams', () => {
  const ownerMap = readOwnerMap()
  assert.equal(ownerMap.compatibilityRetirementContract, 'docs/compatibility-retirement.json')
  const retirement = readJson(ownerMap.compatibilityRetirementContract)
  assert.equal(retirement.status, 'active_fail_closed')
  assert.equal(retirement.safeToDeleteGroupCount, 0)

  const groups = new Map(retirement.groups.map((group) => [group.id, group]))
  for (const id of [
    'root_mini_program_route_clients',
    'pve_dormant_product',
    'wcl_dormant_product',
    'legacy_gear_stats_endpoint',
    'legacy_simc_template_context',
    'legacy_transport_fallbacks',
  ]) {
    const group = groups.get(id)
    assert.ok(group, `${id} should have a retirement contract`)
    assert.ok(['retain_pending_caller_proof', 'dormant_product_decision'].includes(group.status))
    assert.ok(group.owners.active.length > 0)
    assert.ok(group.owners.compatibility.length > 0)
    assert.ok(group.knownCallers.length > 0)
    assert.ok(group.tests.length > 0)
    assert.ok(group.deletionRequirements.length > 0)
    assert.notEqual(group.retirementDecision, 'safe_to_delete')
    assertPathListExists(group.owners.active, `${id}.owners.active`)
    assertPathListExists(group.owners.compatibility, `${id}.owners.compatibility`)
    assertPathListExists(group.knownCallers, `${id}.knownCallers`)
    assertPathListExists(group.tests, `${id}.tests`)
  }

  const uiDomain = ownerMap.criticalDomains.find((domain) => domain.id === 'ui_runtime_evidence')
  assert.deepEqual(
    groups.get('root_mini_program_route_clients').owners.compatibility,
    uiDomain.activeRouteOwners.map((entry) => entry.legacyCompatibilityConsumer),
  )
  assert.ok(groups.get('pve_dormant_product').knownCallers.includes('tests/pve-page.test.js'))
  assert.ok(groups.get('wcl_dormant_product').knownCallers.includes('tests/simulator-page.test.js'))
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

test('canonical gear domain records the pure socket fact owner and verification', () => {
  const ownerMap = readOwnerMap()
  const gearDomain = ownerMap.criticalDomains.find(
    (domain) => domain.id === 'websim_gear_public_read_model'
  )
  assert.ok(gearDomain, 'websim gear domain should exist')
  assert.equal(gearDomain.socketFactAuthority.factOwner, 'server/gear_socket_authority.py')
  assert.equal(gearDomain.socketFactAuthority.status, 'pure_contract_only_unconsumed')
  assert.deepEqual(gearDomain.socketFactAuthority.runtimeConsumers, [])
  assert.ok(gearDomain.socketFactAuthority.tests.includes('tests/gear_socket_authority_test.py'))
  assert.ok(gearDomain.releaseTrainFoundations.modules.includes('server/gear_socket_authority.py'))
  assert.ok(gearDomain.releaseTrainFoundations.tests.includes('tests/gear_socket_authority_test.py'))
  assert.ok(gearDomain.characterization.includes('tests/gear_socket_authority_test.py'))
  assert.ok(gearDomain.criticalContract.coverage.includes('tests/gear_socket_authority_test.py'))
  assert.ok(gearDomain.changedPathPatterns.includes('server/gear_socket_authority.py'))
  assert.ok(gearDomain.changedPathPatterns.includes('tests/gear_socket_authority_test.py'))
  assertPathExists(gearDomain.socketFactAuthority.factOwner)
  assertPathListExists(gearDomain.socketFactAuthority.tests)
})

test('canonical gear domain rejects an unowned community import projector path', () => {
  const ownerMap = readOwnerMap()
  const gearDomain = ownerMap.criticalDomains.find(
    (domain) => domain.id === 'websim_gear_public_read_model'
  )
  const projector = 'server/community_template_import.py'
  const projectorTest = 'tests/community_template_import_test.py'

  assert.ok(gearDomain.contractFoundations.modules.includes(projector))
  assert.ok(gearDomain.contractFoundations.tests.includes(projectorTest))
  assert.ok(gearDomain.characterization.includes(projectorTest))
  assert.ok(gearDomain.runtimeSurfaces.includes(projector))
  assert.ok(gearDomain.changedPathPatterns.includes(projector))
  assert.ok(gearDomain.changedPathPatterns.includes(projectorTest))
  assert.ok(gearDomain.criticalContract.coverage.includes(projectorTest))
  assertPathExists(projector)
  assertPathExists(projectorTest)
})
