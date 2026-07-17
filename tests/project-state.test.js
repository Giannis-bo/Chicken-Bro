const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const projectStatePath = 'docs/project-state.json'
const controlPlaneRelease = 'artifacts/releases/2026-07-10-harness-control-plane'
const executableHarnessRelease = 'artifacts/releases/2026-07-10-executable-project-harness'
const characterizationRelease = 'artifacts/releases/2026-07-10-critical-contract-characterization'
const archivedPhase5Release = 'artifacts/releases/2026-07-11-equipment-simulator-phase5c-frontend-cutover'
const activeHarnessSuperpowersRelease = 'artifacts/releases/2026-07-16-harness-superpowers-method-layer'
const archivedTalentLkgRelease = 'artifacts/releases/2026-07-13-talent-link-lkg-sync-guard'
const archivedCommunityEnhancementRelease = 'artifacts/releases/2026-07-14-community-enhancement-editability'

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function assertPathExists(relativePath) {
  assert.ok(fs.existsSync(relativePath), `${relativePath} should exist`)
}

function assertUniqueById(entries, label) {
  const ids = entries.map((entry) => entry.id)
  assert.equal(new Set(ids).size, ids.length, `${label} ids should be unique`)
}

test('project-state is the single machine-readable current truth entry', () => {
  assertPathExists(projectStatePath)
  const state = readJson(projectStatePath)

  assert.equal(state.schemaVersion, 1)
  assert.equal(state.updatedAt, '2026-07-18')
  assert.equal(state.activeMilestone, 'taro_target_first_14_route_rebuild')
  assert.equal(state.featureIteration, 'allowed_under_harness')
  assert.equal(state.activeReleaseArtifact, activeHarnessSuperpowersRelease)
  assert.equal(state.runtimeBaseline.uiRuntimeEvidence.productionRequestDomain.status, 'blocked_external_configuration')
  assert.deepEqual(state.runtimeBaseline.uiRuntimeEvidence.productionRequestDomain.missing, [
    'WOW_BACKEND_API_BASE_URL=https_named_origin',
    'WOW_WECHAT_REQUEST_DOMAIN_APPROVED=yes',
  ])

  assert.ok(Array.isArray(state.activeContracts), 'activeContracts should be an array')
  assert.ok(Array.isArray(state.completedBaselines), 'completedBaselines should be an array')
  assert.ok(Array.isArray(state.historicalContracts), 'historicalContracts should be an array')
  assert.ok(Array.isArray(state.controlPlaneConclusions), 'controlPlaneConclusions should be an array')

  assertUniqueById(state.activeContracts, 'activeContracts')
  assertUniqueById(state.completedBaselines, 'completedBaselines')
  assertUniqueById(state.historicalContracts, 'historicalContracts')

  const activeContractIds = new Set(state.activeContracts.map((entry) => entry.id))
  assert.ok(activeContractIds.has('repo_native_harness_v0_6'))
  assert.ok(activeContractIds.has('taro_target_first_14_route_rebuild'))
  assert.ok(!activeContractIds.has('talent_link_lkg_sync_guard'))
  assert.ok(!activeContractIds.has('community_enhancement_editability'))
  assert.ok(!activeContractIds.has('equipment_simulator_capability_architecture'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase5_async_stat_snapshot_plan'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase3_resolve_profile_workbench_plan'))
  assert.ok(!activeContractIds.has('equipment_simulator_phase1_contracts_plan'))

  const historicalContractIds = new Set(state.historicalContracts.map((entry) => entry.id))
  assert.ok(historicalContractIds.has('talent_link_lkg_sync_guard'))
  assert.ok(historicalContractIds.has('community_enhancement_editability_v2'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase2a_pure_resolver'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase2b_pg_loader_facade_parity'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3a_resolve_profile_api'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3b_structured_transport_state'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase3c_workbench_cutover'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4a_release_contracts'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4b_pg_registry_legacy_import'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4c_release_shadow_readers'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4d_atomic_manifest_cutover'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase4e_scheduled_refresh'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5a_stat_snapshot_store'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5b_stat_snapshot_worker_api'))
  assert.ok(historicalContractIds.has('equipment_simulator_phase5c_frontend_cutover'))
  assert.ok(![...historicalContractIds].some((id) => id.endsWith('_plan') || id.endsWith('_design')))

  for (const entry of state.activeContracts) {
    assert.notEqual(entry.lifecycle, 'historical', `${entry.id} should not be historical and active`)
    assertPathExists(entry.path)
  }
  for (const entry of state.historicalContracts) {
    assert.equal(entry.lifecycle, 'historical', `${entry.id} should be explicitly historical`)
    assertPathExists(entry.path)
  }

  const activePaths = new Set(state.activeContracts.map((entry) => entry.path))
  for (const entry of state.historicalContracts) {
    assert.ok(!activePaths.has(entry.path), `${entry.path} should not be both active and historical`)
  }

  for (const releasePath of [activeHarnessSuperpowersRelease, archivedTalentLkgRelease, archivedCommunityEnhancementRelease, archivedPhase5Release, characterizationRelease, executableHarnessRelease, controlPlaneRelease]) {
    assertPathExists(path.join(releasePath, 'requirement.json'))
    assertPathExists(path.join(releasePath, 'evidence.json'))
    assertPathExists(path.join(releasePath, 'manifest.json'))
  }

  const communityEnhancementEvidence = readJson(path.join(archivedCommunityEnhancementRelease, 'evidence.json'))
  assert.equal(communityEnhancementEvidence.status, 'archived')
  assert.equal(communityEnhancementEvidence.highestEvidenceLevel, 'live_verified')
  const talentLkgEvidence = readJson(path.join(archivedTalentLkgRelease, 'evidence.json'))
  assert.equal(talentLkgEvidence.status, 'archived')
  assert.equal(talentLkgEvidence.highestEvidenceLevel, 'live_verified')

  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'project_harness_normalization_20260710'),
    'Project Harness normalization should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'harness_v06_efficiency_20260715'),
    'Harness v0.6 efficiency contract should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'harness_superpowers_method_layer_20260716'),
    'Harness Superpowers method-layer contract should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase1_20260710'),
    'Equipment simulator Phase 1 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase2a_20260710'),
    'Equipment simulator Phase 2A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase2_20260711'),
    'Equipment simulator Phase 2 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3a_20260711'),
    'Equipment simulator Phase 3A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3b_20260711'),
    'Equipment simulator Phase 3B should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase3_20260711'),
    'Equipment simulator Phase 3 should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4a_20260711'),
    'Equipment simulator Phase 4A should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4b_20260711'),
    'Equipment simulator Phase 4B should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase4c_20260711'),
    'Equipment simulator Phase 4C should be recorded as a completed baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'equipment_simulator_phase5_20260712'),
    'Equipment simulator Phase 0-5 should be recorded as a completed live baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'community_enhancement_editability_20260715'),
    'Community enhancement editability should be recorded as a completed live baseline'
  )
  assert.ok(
    state.completedBaselines.some((entry) => entry.id === 'talent_link_lkg_sync_guard_20260715'),
    'Talent LKG sync guard should be recorded as a completed live baseline'
  )

  const gearStat = state.runtimeBaseline.gearStatSnapshot
  assert.equal(gearStat.status, 'phase5_complete_live_verified')
  assert.equal(gearStat.frontendCutover, true)
  assert.equal(gearStat.verifiedSpecCount, 32)
  assert.equal(gearStat.explicitNonReadySpecCount, 8)

  const gearReleaseTrain = state.runtimeBaseline.gearReleaseTrain
  assert.equal(gearReleaseTrain.pointerGeneration, 16)
  assert.equal(gearReleaseTrain.activeManifestRevision, 'season-manifest:sha256:34325b76e6b12544b0cf511c89852722784675495b757b6dce522d531660e436')
  assert.equal(gearReleaseTrain.rollbackManifestRevision, 'season-manifest:sha256:551810fcc9d8f6b4dd2099cfafa4b67192476dc4f0bfe36bf827b9fa6ef3c07d')
  assert.equal(gearReleaseTrain.activeGearReleaseId, 'gear-release:sha256:cfb1680130402b3c610d5eab3b0dbe50dd7186facc6a0371951eb5c10ed993c5')
  assert.equal(gearReleaseTrain.activeCommunityReleaseId, 'community-release:sha256:35eafdafc9f96802327917b1f45ab406e60bbce10e81aa150e8cfef5d543ace6')
  assert.equal(gearReleaseTrain.evidence, `${archivedCommunityEnhancementRelease}/evidence.json`)

  const phase5Evidence = readJson(path.join(archivedPhase5Release, 'evidence.json'))
  const phase5Closure = readJson(path.join(archivedPhase5Release, 'closure-audit.json'))
  const phase5Requirement = readJson(path.join(archivedPhase5Release, 'requirement.json'))
  const gearRunbook = fs.readFileSync('docs/gear-simulation-full-chain-runbook.md', 'utf8')
  const buildsArchitecture = fs.readFileSync('docs/builds-architecture.md', 'utf8')
  const simulatorContract = fs.readFileSync('docs/simulator-simc-end-to-end.md', 'utf8')
  assert.equal(phase5Evidence.status, 'archived')
  assert.equal(phase5Evidence.highestEvidenceLevel, 'live_verified')
  assert.equal(phase5Closure.status, 'completed_live_verified_archived')
  assert.equal(phase5Closure.phase6Catalyst.status, 'external_dependency_todo_fail_closed')
  assert.deepEqual(phase5Closure.phase5dMatrix.contractDecision, {
    approvedAt: '2026-07-12',
    approvedBy: 'user',
    decision: 'split_profile_readiness_from_stat_execution_outcome',
    profileReadinessScope: 'canonical_resolver_and_profile_serializer_readiness',
    acceptedStatExecutionOutcomes: ['verified_immutable_snapshot', 'explicit_fail_closed_problem_without_snapshot'],
    verifiedSnapshotCount: 32,
    explicitFailClosedCount: 8,
    runtimeScopeExpanded: false
  })
  assert.ok(
    phase5Requirement.decisionLog.some((entry) => entry.decision === 'Phase 5D separates profileReadiness from stat execution outcome and accepts 32 verified snapshots plus 8 explicit fail-closed outcomes as honest closure evidence.'),
    'Phase 5C requirement should record the approved Phase 5D closure decision'
  )
  assert.match(gearRunbook, /Worker 终态只能是 immutable verified snapshot/)
  assert.doesNotMatch(gearRunbook, /`pages\/simulator\/simc\.js`[^\n]*请求 `\/api\/websim\/gear\/stats`/)
  assert.match(buildsArchitecture, /`POST \/api\/websim\/gear\/stat-snapshots`/)
  assert.match(buildsArchitecture, /旧 `POST \/api\/websim\/gear\/stats`[^\n]*兼容/)
  assert.match(simulatorContract, /async stat-snapshot API/)
  assert.match(simulatorContract, /Profile readiness and stat execution outcome are separate contracts/)
})

test('current truth has one conclusion for UI, PG read-model, Harness normalization and equipment simulator Phase 0-5', () => {
  const state = readJson(projectStatePath)
  const conclusions = state.controlPlaneConclusions
  const domains = conclusions.map((entry) => entry.domain)

  assert.equal(new Set(domains).size, domains.length, 'control-plane conclusion domains should be unique')

  const byDomain = new Map(conclusions.map((entry) => [entry.domain, entry]))
  assert.equal(byDomain.get('ui_delivery').status, 'active_unverified')
  assert.equal(byDomain.get('pg_read_model_phase4').status, 'completed')
  assert.equal(byDomain.get('project_harness_normalization').status, 'completed')
  assert.equal(byDomain.get('equipment_simulator_phase0_5').status, 'completed_live_verified')

  assert.equal(byDomain.get('ui_delivery').activeContract, 'docs/plans/ui-reconstruction.md')
  assert.equal(byDomain.get('pg_read_model_phase4').activeContract, null)
  assert.equal(byDomain.get('project_harness_normalization').activeContract, null)
  assert.equal(byDomain.get('equipment_simulator_phase0_5').activeContract, null)
})

test('roadmap stays a concise current control plane without PR-level execution history', () => {
  const roadmap = fs.readFileSync('docs/roadmap.md', 'utf8')
  assert.match(roadmap, /主干架构接合/)
  assert.match(roadmap, /canonical resolver/)
  assert.doesNotMatch(roadmap, /Phase 4 第[一二三四五六七八九十]+刀/)
  assert.ok(roadmap.split('\n').length <= 150)
})

test('real WeChat interaction verification cannot wait forever inside one route', () => {
  const verifier = fs.readFileSync('scripts/verify-ui-interactions.js', 'utf8')
  assert.match(verifier, /const caseTimeoutMs = 20000/)
  assert.match(verifier, /process\.env\.INTERACTION_ROUTES/)
  assert.match(verifier, /unknown INTERACTION_ROUTES/)
  assert.match(verifier, /interaction precondition unavailable/)
  assert.match(verifier, /timeout\(action\(\), caseTimeoutMs, `interaction \$\{route\}`\)/)
  assert.match(verifier, /\[interaction:start\]/)
  assert.match(verifier, /\[interaction:end\]/)
})

test('visual review capture stays explicit, cached and out of the main session', () => {
  const capture = fs.readFileSync('scripts/capture-ui-review-cache.js', 'utf8')
  assert.match(capture, /UI_REVIEW_ROUTES is required/)
  assert.match(capture, /wow-mini-ui-review-cache/)
  assert.match(capture, /sha256/)
  assert.match(capture, /manifest\.json/)
  assert.match(capture, /connectMiniProgram/)
  assert.doesNotMatch(capture, /WECHAT_AUTOMATOR_LAUNCH/)
})

test('cached visual review requires explicit immutable promotion', () => {
  const promotion = fs.readFileSync('scripts/promote-ui-review-cache.js', 'utf8')
  assert.match(promotion, /required\(process\.env\.UI_REVIEW_MANIFEST, 'UI_REVIEW_MANIFEST'\)/)
  assert.match(promotion, /UI_REVIEW_ROUTES/)
  assert.match(promotion, /cache artifact no longer matches manifest/)
  assert.match(promotion, /artifacts.*ui-runtime-reviews/s)
  assert.match(promotion, /COPYFILE_EXCL/)
  assert.match(promotion, /receipts/)
  assert.doesNotMatch(promotion, /connectMiniProgram|WECHAT_AUTOMATOR_LAUNCH/)
})

test('selected control verification is bounded and cannot launch DevTools', () => {
  const verifier = fs.readFileSync('scripts/verify-ui-selected-states.js', 'utf8')
  const contract = readJson('docs/design/current-ui/selected-control-contract.json')
  assert.ok(contract.groups.length >= 10)
  assert.ok(contract.groups.every((group) => group.maximumActive === 1))
  assert.match(verifier, /SELECTED_STATE_ROUTES/)
  assert.match(verifier, /unknown SELECTED_STATE_ROUTES/)
  assert.match(verifier, /connectMiniProgram/)
  assert.doesNotMatch(verifier, /WECHAT_AUTOMATOR_LAUNCH/)
})

test('route geometry verification covers all routes without launching DevTools', () => {
  const verifier = fs.readFileSync('scripts/verify-ui-route-geometry.js', 'utf8')
  const contract = readJson('docs/design/current-ui/route-geometry-contract.json')
  assert.equal(contract.routes.length, 14)
  assert.ok(contract.tolerancePx <= 1)
  assert.match(verifier, /GEOMETRY_ROUTES/)
  assert.match(verifier, /region-horizontal/)
  assert.match(verifier, /region-vertical/)
  assert.match(verifier, /anonymous-region-id/)
  assert.match(verifier, /native-button-horizontal/)
  assert.match(verifier, /violations\.slice\(0, 10\)/)
  assert.match(verifier, /connectMiniProgram/)
  assert.doesNotMatch(verifier, /WECHAT_AUTOMATOR_LAUNCH/)
})

test('runtime review regions cannot fall back to positional identities', () => {
  const routeFlow = fs.readFileSync('packages/design-system/src/components/RouteFlow.tsx', 'utf8')
  const audit = fs.readFileSync('scripts/audit-ui-architecture.js', 'utf8')
  assert.match(routeFlow, /'data-region': string/)
  assert.match(audit, /route_regions_have_stable_semantic_ids/)
  assert.match(audit, /unnamedRouteRegions/)
})

test('target/runtime region comparison is semantic, bounded and image-free', () => {
  const comparison = fs.readFileSync('scripts/compare-ui-runtime-regions.js', 'utf8')
  const contract = readJson('docs/design/current-ui/runtime-region-mapping-contract.json')
  assert.equal(contract.routes.length, 4)
  assert.ok(contract.tolerance.positionPx <= 8)
  assert.ok(contract.tolerance.sizePx <= 4)
  assert.ok(contract.routes.every((route) => Object.keys(route.regions).length >= 6))
  assert.match(comparison, /GEOMETRY_DETAIL_PATH is required/)
  assert.match(comparison, /REGION_COMPARISON_OUTPUT/)
  assert.doesNotMatch(comparison, /png|screenshot|sharp|canvas/i)
})

test('passing region comparisons require explicit immutable promotion', () => {
  const promotion = fs.readFileSync('scripts/promote-ui-region-comparison.js', 'utf8')
  assert.match(promotion, /REGION_COMPARISON_PATH is required/)
  assert.match(promotion, /only complete passing region comparisons may be promoted/)
  assert.match(promotion, /ui-runtime-reviews/)
  assert.match(promotion, /COPYFILE_EXCL/)
  assert.match(promotion, /sha256/)
})

test('runtime asset-slot review is contract-mapped and bounded', () => {
  const verifier = fs.readFileSync('scripts/verify-ui-asset-slots.js', 'utf8')
  const contract = readJson('docs/design/current-ui/runtime-asset-slot-mapping-contract.json')
  assert.equal(contract.routes.length, 14)
  assert.match(verifier, /ASSET_SLOT_ROUTES/)
  assert.match(verifier, /ASSET_SLOT_DETAIL_PATH/)
  assert.match(verifier, /unregistered runtime slot/)
  assert.match(verifier, /wx-data-asset-missing-true/)
  assert.match(verifier, /routeFailures\.slice\(0, 10\)/)
  assert.doesNotMatch(verifier, /WECHAT_AUTOMATOR_LAUNCH/)
})

test('optional shell assets cannot leak undefined runtime slot identities', () => {
  const appShell = fs.readFileSync('packages/design-system/src/components/AppShell.tsx', 'utf8')
  const feed = fs.readFileSync('packages/design-system/src/components/RankedFeed.tsx', 'utf8')
  assert.doesNotMatch(appShell, /data-slot-id=\{surfaceSlotId\}/)
  assert.match(appShell, /surfaceSlotId \? \{ 'data-slot-id': surfaceSlotId/)
  assert.doesNotMatch(feed, /slot-feed-thumb-placeholder/)
})
