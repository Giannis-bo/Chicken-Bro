#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const babelParser = require('@babel/parser')
const traverse = require('@babel/traverse').default
const {
  expectedInteractionOverallStatus,
  expectedReviewOverallStatus,
  isCompletePassRecord,
  sharedEvidenceMatchesStatus,
} = require('./runtime-review-validation')

const root = path.resolve(__dirname, '..')
const findings = []
const checks = []

const expectedAppRoutes = [
  'pages/news/news',
  'pages/news/list',
  'pages/news/detail',
  'pages/builds/builds',
  'pages/builds/workbench',
  'pages/builds/intel',
  'pages/builds/talent-simulator',
  'pages/builds/detail',
  'pages/simulator/simulator',
  'pages/simulator/simc',
  'pages/simulator/chickenbro',
  'pages/simulator/tasks',
  'pages/simulator/task-detail',
  'pages/profile/profile',
]
const expectedContractRoutes = [
  'build-intel',
  'builds-home',
  'chickenbro-chat',
  'gear-detail',
  'news-detail',
  'news-home',
  'news-list',
  'profile-templates',
  'simc-submit',
  'simulator-home',
  'talent-simulator',
  'task-detail',
  'tasks-list',
  'workbench',
]
const expectedBaselineRoutes = ['news_home', 'simulator_home', 'news_detail']
const requiredContractFiles = [
  'asset-contract.json',
  'component-contract.json',
  'target-geometry.json',
  'target-inventory.json',
  'truth-adaptation.json',
]

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function walk(relativeDir, extensions) {
  const base = path.join(root, relativeDir)
  const files = []
  for (const entry of fs.readdirSync(base, { withFileTypes: true })) {
    const relativePath = path.join(relativeDir, entry.name)
    if (entry.isDirectory()) files.push(...walk(relativePath, extensions))
    else if (extensions.some((extension) => entry.name.endsWith(extension))) files.push(relativePath)
  }
  return files
}

function record(id, pass, detail) {
  checks.push({ id, pass, detail })
  if (!pass) findings.push(`${id}: ${detail}`)
}

function sorted(values) {
  return [...values].sort((a, b) => a.localeCompare(b))
}

const routeSources = walk('apps/mini-taro/src/pages', ['.ts', '.tsx', '.scss'])
const routeStyles = routeSources.filter((file) => file.endsWith('.scss'))
const routeComponents = routeSources.filter((file) => file.endsWith('.tsx'))

const sharedRouteStylePath = 'apps/mini-taro/src/pages/_shared/routes.module.scss'
const sharedRouteStyles = read(sharedRouteStylePath)
const sharedRouteConsumers = [
  'apps/mini-taro/src/pages/_shared/AssistantRoute.tsx',
  'apps/mini-taro/src/pages/_shared/route-runtime.tsx',
].map(read).join('\n')
const sharedRouteClassNames = [...new Set(
  [...sharedRouteStyles.matchAll(/\.([A-Za-z_][\w-]*)/gu)].map((match) => match[1]),
)]
const unusedSharedRouteClasses = sharedRouteClassNames.filter((className) => (
  !sharedRouteConsumers.includes(`styles['${className}']`)
  && !sharedRouteConsumers.includes(`styles.${className}`)
))
record(
  'shared_route_styles_have_live_consumers',
  unusedSharedRouteClasses.length === 0,
  unusedSharedRouteClasses.join(', ') || 'none',
)

const fallbackJargonSources = routeSources.filter((file) => /回退/u.test(read(file)))
record(
  'routes_do_not_expose_fallback_implementation_jargon',
  fallbackJargonSources.length === 0,
  fallbackJargonSources.join(', ') || 'none',
)

const appConfig = read('apps/mini-taro/src/app.config.ts')
const pagesBlock = appConfig.match(/pages:\s*\[([\s\S]*?)\],\s*window:/)?.[1] ?? ''
const configuredRoutes = [...pagesBlock.matchAll(/'([^']+)'/g)].map((match) => match[1])
record(
  'app_route_manifest_is_exactly_14_routes',
  JSON.stringify(configuredRoutes) === JSON.stringify(expectedAppRoutes),
  `configured=${configuredRoutes.length}`,
)

const targetRegistry = JSON.parse(read('docs/design/current-ui/target-registry.json'))
const interactionContract = JSON.parse(read('docs/design/current-ui/core-interaction-contract.json'))
const selectedControlContract = JSON.parse(read('docs/design/current-ui/selected-control-contract.json'))
const routeGeometryContract = JSON.parse(read('docs/design/current-ui/route-geometry-contract.json'))
const runtimeRegionMappingContract = JSON.parse(read('docs/design/current-ui/runtime-region-mapping-contract.json'))
const runtimeAssetSlotMappingContract = JSON.parse(read('docs/design/current-ui/runtime-asset-slot-mapping-contract.json'))
const evidencePolicy = JSON.parse(read('docs/design/current-ui/active-evidence-policy.json'))
const runtimeReviewContract = JSON.parse(read('docs/design/current-ui/runtime-review-contract.json'))
const runtimeReviewStatus = JSON.parse(read('docs/design/current-ui/runtime-review-status.json'))
const projectState = JSON.parse(read('docs/project-state.json'))
const expectedInteractionStatus = expectedInteractionOverallStatus(interactionContract.interactions ?? [])
const expectedInteractionAcceptance = expectedInteractionStatus === 'verified'
  ? 'verified_real_wechat_core_interaction_matrix'
  : expectedInteractionStatus === 'active_failed'
    ? 'failed_real_wechat_core_interaction_matrix'
    : 'pending_real_wechat_core_interaction_matrix'
record(
  'runtime_review_records_are_authoritative_inputs',
  ['docs/design/current-ui/runtime-review-contract.json', 'docs/design/current-ui/runtime-review-status.json', 'docs/design/current-ui/selected-control-contract.json', 'docs/design/current-ui/route-geometry-contract.json', 'docs/design/current-ui/runtime-region-mapping-contract.json', 'docs/design/current-ui/runtime-asset-slot-mapping-contract.json']
    .every((file) => evidencePolicy.authoritativeInputs?.includes(file)),
  `schemaVersion=${evidencePolicy.schemaVersion}`,
)
const uiDeliveryConclusion = projectState.controlPlaneConclusions?.find((item) => item.domain === 'ui_delivery')
record(
  'project_state_points_to_runtime_review_status',
  uiDeliveryConclusion?.status === runtimeReviewStatus.status
    && uiDeliveryConclusion?.evidence === 'docs/design/current-ui/runtime-review-status.json'
    && projectState.runtimeBaseline?.uiRuntimeEvidence?.statusLedger === 'docs/design/current-ui/runtime-review-status.json'
    && projectState.runtimeBaseline?.uiRuntimeEvidence?.status === runtimeReviewStatus.status
    && projectState.runtimeBaseline?.uiRuntimeEvidence?.interactionAcceptance === expectedInteractionAcceptance,
  `status=${uiDeliveryConclusion?.status}; evidence=${uiDeliveryConclusion?.evidence}`,
)
record(
  'target_registry_is_active_and_complete',
  targetRegistry.status === 'active' && targetRegistry.canonicalTargets?.length === 14,
  `status=${targetRegistry.status}; targets=${targetRegistry.canonicalTargets?.length ?? 0}`,
)
record(
  'target_registry_matches_runtime_baseline_contract',
  JSON.stringify(targetRegistry.baselineRoutes) === JSON.stringify(expectedBaselineRoutes),
  `baselines=${(targetRegistry.baselineRoutes ?? []).join(',')}`,
)
const targetRouteIds = sorted(targetRegistry.canonicalTargets.map((target) => target.route))
const interactionRouteIds = sorted((interactionContract.interactions ?? []).map((interaction) => interaction.route))
record(
  'core_interaction_contract_covers_all_target_routes',
  interactionContract.status === expectedInteractionStatus
    && JSON.stringify(interactionRouteIds) === JSON.stringify(targetRouteIds),
  `interactions=${interactionRouteIds.length}`,
)
for (const interaction of interactionContract.interactions ?? []) {
  const sourceExists = typeof interaction.source === 'string' && fs.existsSync(path.join(root, interaction.source))
  const marker = `${interaction.selectorAttribute}="${interaction.selectorValue}"`
  record(
    `interaction_selector:${interaction.route}`,
    sourceExists && read(interaction.source).includes(marker),
    sourceExists ? marker : `missing source ${interaction.source}`,
  )
}
const interactionExecutor = read('scripts/verify-ui-interactions.js')
record(
  'interaction_executor_consumes_authoritative_contract',
  interactionExecutor.includes("require('../docs/design/current-ui/core-interaction-contract.json')")
    && interactionExecutor.includes('contractDefinition(')
    && interactionExecutor.includes('contractPath(')
    && interactionExecutor.includes('contractSelector(')
    && interactionExecutor.includes('coverageMatches')
    && !/output:\s*\{\s*route:/u.test(interactionExecutor)
    && !/open\(miniProgram,\s*['"]\/pages/u.test(interactionExecutor),
  'executor metadata, paths and coverage must come from the core interaction contract',
)
const reviewRoutes = runtimeReviewStatus.routes ?? []
const reviewRouteIds = sorted(reviewRoutes.map((review) => review.route))
const requiredSharedReviewEvidence = [
  'wechat_runtime_artifact',
  'target_runtime_region_comparison',
  'real_wechat_core_interaction',
  'human_visual_confirmation',
]
const expectedOverallStatus = expectedReviewOverallStatus(reviewRoutes)
const sharedMissingEvidence = runtimeReviewStatus.sharedMissingEvidence ?? []
const reviewEvidenceStateValid = sharedEvidenceMatchesStatus(
  expectedOverallStatus,
  sharedMissingEvidence,
  requiredSharedReviewEvidence,
)
record(
  'runtime_review_status_covers_all_target_routes',
  runtimeReviewStatus.status === expectedOverallStatus
    && JSON.stringify(reviewRouteIds) === JSON.stringify(targetRouteIds)
    && reviewEvidenceStateValid,
  `reviews=${reviewRouteIds.length}; status=${runtimeReviewStatus.status}; expected=${expectedOverallStatus}`,
)
for (const observed of runtimeReviewStatus.observedRegionComparisons ?? []) {
  const comparisonPath = path.join(root, observed.path ?? '')
  const exists = fs.existsSync(comparisonPath)
  const actualSha = exists ? crypto.createHash('sha256').update(fs.readFileSync(comparisonPath)).digest('hex') : null
  const comparison = exists ? JSON.parse(fs.readFileSync(comparisonPath, 'utf8')) : null
  const comparisonRoutes = comparison?.routes?.map((route) => route.route) ?? []
  record(
    `observed_region_comparison_is_content_addressed:${observed.commit}`,
    exists
      && observed.path.includes(observed.sha256)
      && actualSha === observed.sha256
      && comparison?.commit === observed.commit
      && comparison?.schemaVersion === 'target-runtime-region-comparison-v1'
      && comparison?.routes?.every((route) => route.status === 'PASS' && route.regions.every((region) => region.status === 'PASS'))
      && comparison.routes.reduce((sum, route) => sum + route.regions.length, 0) === observed.regionCount
      && JSON.stringify(comparisonRoutes) === JSON.stringify(observed.routes),
    `artifact=${exists}; sha=${actualSha === observed.sha256}; routes=${comparisonRoutes.length}`,
  )
}
for (const observed of runtimeReviewStatus.observedAssetSlotReviews ?? []) {
  const evidencePath = path.join(root, observed.path ?? '')
  const exists = fs.existsSync(evidencePath)
  const actualSha = exists ? crypto.createHash('sha256').update(fs.readFileSync(evidencePath)).digest('hex') : null
  const evidence = exists ? JSON.parse(fs.readFileSync(evidencePath, 'utf8')) : null
  const routeNames = evidence?.routes?.map((route) => route.route) ?? []
  record(
    `observed_asset_slot_review_is_content_addressed:${observed.commit}`,
    exists
      && observed.path.includes(observed.sha256)
      && actualSha === observed.sha256
      && evidence?.schemaVersion === 'wechat-runtime-asset-slot-evidence-v1'
      && evidence?.commit === observed.commit
      && evidence?.routes?.length === observed.routeCount
      && evidence.routes.every((route) => route.status === 'pass' && route.missingAssetElements === 0 && route.failures.length === 0 && route.semanticMappings.length === route.slotCount)
      && evidence.routes.reduce((sum, route) => sum + route.elementCount, 0) === observed.visibleElements
      && evidence.routes.reduce((sum, route) => sum + route.slotCount, 0) === observed.visibleSlots
      && JSON.stringify(routeNames) === JSON.stringify(runtimeAssetSlotMappingContract.routes.map((route) => route.route)),
    `artifact=${exists}; sha=${actualSha === observed.sha256}; routes=${routeNames.length}`,
  )
}
for (const review of reviewRoutes) {
  const target = targetRegistry.canonicalTargets.find((candidate) => candidate.route === review.route)
  const interaction = interactionContract.interactions.find((candidate) => candidate.route === review.route)
  const contractRootExists = typeof review.contractRoot === 'string' && fs.existsSync(path.join(root, review.contractRoot))
  const passRecordComplete = review.status !== 'PASS' || isCompletePassRecord(review, runtimeReviewContract)
  record(
    `runtime_review_boundary:${review.route}`,
    ['PASS', 'FAIL', 'UNVERIFIED'].includes(review.status)
      && review.targetArtifact === target?.path
      && review.path === interaction?.path
      && (review.status !== 'PASS' || interaction?.status === 'PASS')
      && contractRootExists
      && passRecordComplete
      && (review.status !== 'UNVERIFIED' || runtimeReviewStatus.sharedMissingEvidence?.length > 0),
    `status=${review.status}; target=${Boolean(target)}; interaction=${Boolean(interaction)}; contract=${contractRootExists}; passRecord=${passRecordComplete}`,
  )
  if (review.observedRuntimeArtifact) {
    const artifact = review.observedRuntimeArtifact
    const artifactPath = path.join(root, artifact.path ?? '')
    const receiptPath = path.join(root, artifact.receipt ?? '')
    const artifactExists = fs.existsSync(artifactPath)
    const receiptExists = fs.existsSync(receiptPath)
    const actualSha = artifactExists ? crypto.createHash('sha256').update(fs.readFileSync(artifactPath)).digest('hex') : null
    const receipt = receiptExists ? JSON.parse(fs.readFileSync(receiptPath, 'utf8')) : null
    const receiptEntry = receipt?.promoted?.find((entry) => entry.route === review.route)
    record(
      `observed_runtime_artifact_is_content_addressed:${review.route}`,
      artifactExists
        && receiptExists
        && runtimeReviewContract.fieldContract.runtimeArtifact.every((field) => Object.hasOwn(artifact, field))
        && artifact.path.includes(artifact.sha256)
        && actualSha === artifact.sha256
        && fs.statSync(artifactPath).size === artifact.bytes
        && receiptEntry?.runtimeArtifact?.path === artifact.path
        && receiptEntry?.runtimeArtifact?.sha256 === artifact.sha256,
      `artifact=${artifactExists}; receipt=${receiptExists}; sha=${actualSha === artifact.sha256}`,
    )
  }
}

const currentPlanFiles = sorted(fs.readdirSync(path.join(root, 'docs/plans')).filter((name) => fs.statSync(path.join(root, 'docs/plans', name)).isFile()))
record(
  'current_plan_set_matches_evidence_policy',
  JSON.stringify(currentPlanFiles) === JSON.stringify(sorted(evidencePolicy.allowedPlanFiles ?? [])),
  `plans=${currentPlanFiles.join(',')}`,
)
const presentForbiddenPaths = (evidencePolicy.requiredAbsentPaths ?? []).filter((relativePath) => fs.existsSync(path.join(root, relativePath)))
record(
  'superseded_ui_control_paths_are_absent',
  presentForbiddenPaths.length === 0,
  presentForbiddenPaths.join(', ') || 'none',
)
const currentUiArtifactRoots = sorted(fs.readdirSync(path.join(root, 'artifacts'), { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name !== 'releases')
  .map((entry) => entry.name))
record(
  'current_ui_artifact_roots_match_evidence_policy',
  JSON.stringify(currentUiArtifactRoots) === JSON.stringify(sorted(evidencePolicy.allowedArtifactRoots ?? [])),
  `artifactRoots=${currentUiArtifactRoots.join(',')}`,
)

const contractsRoot = path.join(root, 'docs/design/current-ui/routes')
const contractRoutes = sorted(fs.readdirSync(contractsRoot).filter((name) => fs.statSync(path.join(contractsRoot, name)).isDirectory()))
record(
  'route_contract_set_matches_delivery_routes',
  JSON.stringify(contractRoutes) === JSON.stringify(expectedContractRoutes),
  `contracts=${contractRoutes.length}`,
)
for (const route of expectedContractRoutes) {
  for (const file of requiredContractFiles) {
    const relativePath = `docs/design/current-ui/routes/${route}/${file}`
    const exists = fs.existsSync(path.join(root, relativePath))
    let validJson = false
    if (exists) {
      try {
        JSON.parse(read(relativePath))
        validJson = true
      } catch {}
    }
    record(`contract:${route}:${file}`, exists && validJson, exists ? 'invalid_json' : 'missing')
  }
}

const requiredAuthorities = [
  'docs/roadmap.md',
  'docs/plans/ui-reconstruction.md',
  'DESIGN.md',
  'docs/design/current-ui/README.md',
]
for (const authority of requiredAuthorities) {
  record(`authority:${authority}`, fs.existsSync(path.join(root, authority)), 'missing')
}

const deadShellRules = routeStyles.filter((file) => /^\s*\.shell(?:\b|,)/m.test(read(file)))
record('route_styles_do_not_own_app_shell', deadShellRules.length === 0, deadShellRules.join(', ') || 'none')

const routeSafeAreaOwners = routeSources.filter((file) => /--(?:safe-top|safe-bottom|capsule-safe-right)\b/.test(read(file)))
record('route_styles_do_not_recompute_safe_area', routeSafeAreaOwners.length === 0, routeSafeAreaOwners.join(', ') || 'none')

const routeHeaderGeometryOwners = routeStyles.filter((file) => /\[data-region=['"]top_bar['"]\]/u.test(read(file)))
record('route_styles_do_not_own_page_frame_geometry', routeHeaderGeometryOwners.length === 0, routeHeaderGeometryOwners.join(', ') || 'none')

const directRouteStateOwners = routeComponents.filter((file) => (
  !file.includes('/_shared/') && /data-(?:route-state|target-region-count)=/u.test(read(file))
))
record(
  'route_components_use_shared_state_boundaries',
  directRouteStateOwners.length === 0,
  directRouteStateOwners.join(', ') || 'none',
)

const routeStageConsumers = routeComponents.filter((file) => /<RouteStage\b/u.test(read(file)))
const routeFlowConsumers = routeComponents.filter((file) => /<RouteFlow\b/u.test(read(file)))
const routeColumnConsumers = routeComponents.filter((file) => /<RouteColumn\b/u.test(read(file)))
const routeGridConsumers = routeComponents.filter((file) => /<RouteGrid\b/u.test(read(file)))
const routeRegionConsumers = routeComponents.filter((file) => /<RouteRegion\b/u.test(read(file)))
const directNamedRegionOwners = []
const unnamedRouteRegions = []
for (const file of routeComponents.filter((candidate) => !candidate.includes('/_shared/'))) {
  const source = read(file)
  const ast = babelParser.parse(source, { sourceType: 'module', plugins: ['jsx', 'typescript'] })
  traverse(ast, {
    JSXOpeningElement(elementPath) {
      const name = elementPath.node.name
      if (name.type === 'JSXIdentifier' && name.name === 'RouteRegion') {
        const regionAttribute = elementPath.node.attributes.find((attribute) => (
          attribute.type === 'JSXAttribute'
          && attribute.name.type === 'JSXIdentifier'
          && attribute.name.name === 'data-region'
        ))
        if (!regionAttribute?.value) unnamedRouteRegions.push(`${file}:${elementPath.node.loc?.start.line ?? 0}`)
      }
      if (name.type !== 'JSXIdentifier' || name.name !== 'View') return
      const className = elementPath.node.attributes.find((attribute) => (
        attribute.type === 'JSXAttribute'
        && attribute.name.type === 'JSXIdentifier'
        && attribute.name.name === 'className'
      ))
      if (!className || className.value?.type !== 'JSXExpressionContainer') return
      const expressionSource = source.slice(className.value.expression.start, className.value.expression.end)
      if (/styles\[['"][^'"]*Region['"]\]/u.test(expressionSource)) {
        directNamedRegionOwners.push(`${file}:${elementPath.node.loc?.start.line ?? 0}`)
      }
    },
  })
}
record(
  'named_route_regions_use_shared_layout_owner',
  directNamedRegionOwners.length === 0,
  directNamedRegionOwners.join(', ') || 'none',
)
record(
  'route_regions_have_stable_semantic_ids',
  unnamedRouteRegions.length === 0
    && /'data-region': string/u.test(read('packages/design-system/src/components/RouteFlow.tsx')),
  unnamedRouteRegions.join(', ') || 'all RouteRegion instances are named and the prop is type-required',
)
record(
  'shared_route_layout_owners_cover_current_layout_families',
  routeStageConsumers.length === 8 && routeFlowConsumers.length === 3 && routeColumnConsumers.length >= 4 && routeGridConsumers.length >= 2 && routeRegionConsumers.length >= 4,
  `stage=${routeStageConsumers.length}; flow=${routeFlowConsumers.length}; column=${routeColumnConsumers.length}; grid=${routeGridConsumers.length}; region=${routeRegionConsumers.length}`,
)

const privateStageFoundationOwners = routeStyles.filter((file) => {
  const pageFrameRule = read(file).match(/\.pageFrame\s*\{([\s\S]*?)\}/u)?.[1] ?? ''
  return /\b(?:position|overflow|border|border-radius|box-shadow)\s*:/u.test(pageFrameRule)
})
record(
  'route_styles_do_not_reimplement_stage_foundations',
  privateStageFoundationOwners.length === 0,
  privateStageFoundationOwners.join(', ') || 'none',
)

const privateColumnOwners = routeStyles.filter((file) => {
  const surfaceRule = read(file).match(/\.surface\s*\{([\s\S]*?)\}/u)?.[1] ?? ''
  return /display\s*:\s*flex/u.test(surfaceRule) && /flex-direction\s*:\s*column/u.test(surfaceRule)
})
record(
  'route_styles_do_not_reimplement_shared_column_composition',
  privateColumnOwners.length === 0,
  privateColumnOwners.join(', ') || 'none',
)

const privateGridOwners = routeStyles.filter((file) => {
  const surfaceRule = read(file).match(/\.surface\s*\{([\s\S]*?)\}/u)?.[1] ?? ''
  return /display\s*:\s*grid/u.test(surfaceRule) && /(?:min-width\s*:\s*0|margin\s*:\s*[^;]*auto)/u.test(surfaceRule)
})
record(
  'route_styles_do_not_reimplement_shared_grid_composition',
  privateGridOwners.length === 0,
  privateGridOwners.join(', ') || 'none',
)

const privateRegionFillOwners = routeStyles.filter((file) => (
  /(?:\.region|\.cardSlot|\.disclaimer)\s*>\s*view\s*\{[^}]*width\s*:\s*100%;[^}]*height\s*:\s*100%;/su.test(read(file))
))
record(
  'route_styles_do_not_reimplement_region_child_fill',
  privateRegionFillOwners.length === 0,
  privateRegionFillOwners.join(', ') || 'none',
)

const sharedActionContentConsumers = [
  'packages/design-system/src/components/BuildWorkspaceEntry.tsx',
  'packages/design-system/src/components/NewsListComponents.tsx',
  'packages/design-system/src/components/NewsDetailComponents.tsx',
]
record(
  'repeated_icon_label_actions_use_shared_content_layout',
  fs.existsSync(path.join(root, 'packages/design-system/src/components/ActionContent.tsx'))
    && sharedActionContentConsumers.every((file) => /<ActionContent\b/u.test(read(file))),
  sharedActionContentConsumers.filter((file) => !/<ActionContent\b/u.test(read(file))).join(', ') || 'none',
)

const taskListStyles = read('packages/design-system/src/components/TaskListComponents.module.scss')
const reconstructionStyles = read('packages/design-system/src/components/reconstruction.module.scss')
const buildIntelStyles = read('packages/design-system/src/components/BuildIntelComponents.module.scss')
const taskRouteStyles = read('apps/mini-taro/src/pages/simulator/tasks.module.scss')
const selectedStateOwners = [
  ['packages/design-system/src/components/TabBar.tsx', 'product-tab-item'],
  ['packages/design-system/src/components/ChannelDock.tsx', 'news-list-category'],
  ['packages/design-system/src/components/ChannelDock.tsx', 'channel-segment'],
  ['packages/design-system/src/components/NewsDetailComponents.tsx', 'news-detail-translation-segment'],
  ['packages/design-system/src/components/NewsListComponents.tsx', 'news-list-category'],
  ['packages/design-system/src/components/GearDetailComponents.tsx', 'gear-profession-option'],
  ['packages/design-system/src/components/GearDetailComponents.tsx', 'gear-slot-row'],
  ['packages/design-system/src/components/GearDetailComponents.tsx', 'gear-enhancement-option'],
  ['packages/design-system/src/components/TalentSimulatorComponents.tsx', 'talent-tree-tab'],
  ['packages/design-system/src/components/TaskListComponents.tsx', 'task-status-filter'],
  ['packages/design-system/src/components/SimcSubmitComponents.tsx', 'simc-specialization-option'],
  ['packages/design-system/src/components/SimcSubmitComponents.tsx', 'simc-scenario-option'],
]
const selectedGroupKeys = selectedControlContract.groups?.map((group) => `${group.route}:${group.role}`) ?? []
record(
  'selected_control_contract_has_unique_bounded_groups',
  selectedControlContract.status === 'active'
    && selectedGroupKeys.length >= 10
    && new Set(selectedGroupKeys).size === selectedGroupKeys.length
    && selectedControlContract.groups.every((group) => (
      ['selected', 'active'].includes(group.state)
      && Number.isInteger(group.minimumControls) && group.minimumControls >= 0
      && Number.isInteger(group.minimumActive) && group.minimumActive >= 0
      && Number.isInteger(group.maximumActive) && group.maximumActive === 1
      && group.minimumActive <= group.maximumActive
      && interactionContract.interactions.some((interaction) => interaction.route === group.route && interaction.path === group.path)
    )),
  `groups=${selectedGroupKeys.length}`,
)
record(
  'selected_controls_have_stable_group_roles',
  selectedStateOwners.every(([file, role]) => read(file).includes(`data-role="${role}"`))
    && selectedControlContract.groups.every((group) => selectedStateOwners.some(([, role]) => role === group.role)),
  'selected-state runtime review must group controls by stable role rather than generated CSS classes',
)
record(
  'selected_state_verifier_reuses_existing_devtools_only',
  fs.existsSync(path.join(root, 'scripts/verify-ui-selected-states.js'))
    && /connectMiniProgram/u.test(read('scripts/verify-ui-selected-states.js'))
    && !/WECHAT_AUTOMATOR_LAUNCH/u.test(read('scripts/verify-ui-selected-states.js')),
  'selected-state verification must never launch or reload DevTools',
)
const geometryRouteKeys = routeGeometryContract.routes?.map((route) => route.route) ?? []
record(
  'runtime_geometry_contract_covers_delivery_routes',
  routeGeometryContract.status === 'active'
    && routeGeometryContract.tolerancePx <= 1
    && geometryRouteKeys.length === 14
    && new Set(geometryRouteKeys).size === 14
    && routeGeometryContract.routes.every((route) => interactionContract.interactions.some((interaction) => interaction.route === route.route && interaction.path === route.path)),
  `routes=${geometryRouteKeys.length}; tolerance=${routeGeometryContract.tolerancePx}`,
)
record(
  'runtime_geometry_verifier_reuses_existing_devtools_only',
  fs.existsSync(path.join(root, 'scripts/verify-ui-route-geometry.js'))
    && /connectMiniProgram/u.test(read('scripts/verify-ui-route-geometry.js'))
    && /native-button-horizontal/u.test(read('scripts/verify-ui-route-geometry.js'))
    && !/WECHAT_AUTOMATOR_LAUNCH/u.test(read('scripts/verify-ui-route-geometry.js')),
  '14-route geometry verification must remain bounded and never launch or reload DevTools',
)
record(
  'runtime_region_mapping_is_semantic_and_bounded',
  runtimeRegionMappingContract.status === 'active'
    && runtimeRegionMappingContract.routes?.length === 4
    && runtimeRegionMappingContract.tolerance?.positionPx <= 8
    && runtimeRegionMappingContract.tolerance?.sizePx <= 4
    && runtimeRegionMappingContract.routes.every((route) => (
      fs.existsSync(path.join(root, route.targetGeometry))
      && Object.keys(route.regions ?? {}).length >= 6
      && Object.hasOwn(route.regions, route.anchorTop)
      && Object.hasOwn(route.regions, route.anchorBottom)
    )),
  `routes=${runtimeRegionMappingContract.routes?.length ?? 0}`,
)
record(
  'runtime_region_comparison_stays_structured_and_image_free',
  fs.existsSync(path.join(root, 'scripts/compare-ui-runtime-regions.js'))
    && /GEOMETRY_DETAIL_PATH is required/u.test(read('scripts/compare-ui-runtime-regions.js'))
    && /target-runtime-region-comparison-v1/u.test(read('scripts/compare-ui-runtime-regions.js'))
    && !/(?:png|screenshot|sharp|canvas)/iu.test(read('scripts/compare-ui-runtime-regions.js')),
  'target/runtime comparison must consume structured geometry without loading screenshot pixels',
)
record(
  'runtime_region_comparison_has_immutable_promotion',
  fs.existsSync(path.join(root, 'scripts/promote-ui-region-comparison.js'))
    && /REGION_COMPARISON_PATH is required/u.test(read('scripts/promote-ui-region-comparison.js'))
    && /COPYFILE_EXCL/u.test(read('scripts/promote-ui-region-comparison.js'))
    && /ui-runtime-reviews/u.test(read('scripts/promote-ui-region-comparison.js')),
  'passing structured comparisons must be content-addressed before becoming review evidence',
)
record(
  'runtime_asset_slots_map_to_route_or_shared_contracts',
  runtimeAssetSlotMappingContract.status === 'active'
    && runtimeAssetSlotMappingContract.routes?.length === 14
    && runtimeAssetSlotMappingContract.routes.every((route) => (
      fs.existsSync(path.join(root, route.assetContract))
      && Object.keys(route.runtimeSlots ?? {}).length >= 7
      && Object.entries(route.runtimeSlots).every(([runtimeSlot, contractSlot]) => runtimeSlot.startsWith('asset_slot.') && typeof contractSlot === 'string')
    )),
  `routes=${runtimeAssetSlotMappingContract.routes?.length ?? 0}`,
)
record(
  'runtime_asset_slot_verifier_reuses_existing_devtools_only',
  fs.existsSync(path.join(root, 'scripts/verify-ui-asset-slots.js'))
    && /connectMiniProgram/u.test(read('scripts/verify-ui-asset-slots.js'))
    && /wx-data-asset-missing-true/u.test(read('scripts/verify-ui-asset-slots.js'))
    && !/WECHAT_AUTOMATOR_LAUNCH/u.test(read('scripts/verify-ui-asset-slots.js')),
  'runtime asset-slot review must be bounded and never launch or reload DevTools',
)
const appShellSource = read('packages/design-system/src/components/AppShell.tsx')
record(
  'optional_shell_assets_do_not_emit_undefined_slot_selectors',
  !/data-slot-id=\{surfaceSlotId\}/u.test(appShellSource)
    && /surfaceSlotId \? \{ 'data-slot-id': surfaceSlotId/u.test(appShellSource)
    && !/slot-feed-thumb-placeholder/u.test(read('packages/design-system/src/components/RankedFeed.tsx')),
  'optional shell metadata must be omitted and legacy feed slots must use the registered asset_slot namespace',
)
record(
  'runtime_asset_slot_review_has_exact_immutable_promotion',
  fs.existsSync(path.join(root, 'scripts/promote-ui-asset-slot-review.js'))
    && /ASSET_SLOT_DETAIL_PATHS is required/u.test(read('scripts/promote-ui-asset-slot-review.js'))
    && /exact 14-route contract/u.test(read('scripts/promote-ui-asset-slot-review.js'))
    && /flag: 'wx'/u.test(read('scripts/promote-ui-asset-slot-review.js')),
  'split runtime reviews must share commit and viewport before content-addressed promotion',
)
record(
  'shared_native_buttons_cannot_exceed_their_layout_cell',
  /\.routeSurface button\s*\{[^}]*max-width:\s*100%;/su.test(reconstructionStyles),
  'every native WeChat button must be clamped by its immediate layout cell',
)
record(
  'news_translation_has_one_state_material_owner',
  /\.newsDetailTranslationLabel\s*\{[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/su.test(reconstructionStyles)
    && /\.newsDetailTranslationSegments\s*\{[^}]*border:\s*0;[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/su.test(reconstructionStyles)
    && /\.newsDetailTranslationSegment\s*\{[^}]*background:\s*transparent;[^}]*box-shadow:\s*none;/su.test(reconstructionStyles)
    && /\.newsDetailTranslationSegment\[data-selected='true'\]/u.test(reconstructionStyles),
  'inactive translation segments must stay flat and only the selected segment may own active material',
)
record(
  'build_intel_disclaimer_stays_inside_the_wechat_viewport',
  /\.cardViewport\s*\{[^}]*height:\s*498\.75px;/su.test(read('apps/mini-taro/src/pages/builds/build-intel.module.scss')),
  'build intel card viewport must reserve enough height for the terminal disclaimer',
)
const viewportFitStyles = {
  newsDetail: read('apps/mini-taro/src/pages/news/news-detail.module.scss'),
  gearDetail: read('apps/mini-taro/src/pages/builds/gear-detail.module.scss'),
  simcSubmit: read('apps/mini-taro/src/pages/simulator/simc-submit.module.scss'),
  taskDetail: read('apps/mini-taro/src/pages/simulator/task-detail.module.scss'),
  profile: read('apps/mini-taro/src/pages/profile/profile.module.scss'),
}
record(
  'single_screen_route_terminals_reserve_wechat_viewport_space',
  /\.body\s*\{[^}]*height:\s*256\.6px;/su.test(viewportFitStyles.newsDetail)
    && /\.workbenchRegion\s*\{[^}]*height:\s*319px;/su.test(viewportFitStyles.gearDetail)
    && /\.statusRegion\s*\{[^}]*top:\s*654px;/su.test(viewportFitStyles.gearDetail)
    && /\.footerRegion\s*\{[^}]*top:\s*763px;/su.test(viewportFitStyles.simcSubmit)
    && /\.pageFrame\s*\{[^}]*height:\s*813px;/su.test(viewportFitStyles.taskDetail)
    && /\.pageFrame\s*\{[^}]*height:\s*825px;/su.test(viewportFitStyles.profile),
  'single-screen terminal regions must not extend below the real WeChat viewport',
)
record(
  'build_intel_actions_override_native_button_width',
  /button\.primaryAction,[\s\S]*button\.secondaryAction\s*\{[^}]*width:\s*100%;[^}]*max-width:\s*100%;[^}]*margin-right:\s*0;[^}]*margin-left:\s*0;/u.test(buildIntelStyles),
  'build intel action buttons must remain inside the narrow action column',
)
record(
  'task_bottom_actions_stay_inside_the_route_region',
  /\.pageFrame\s*\{[^}]*height:\s*100%;/su.test(taskRouteStyles)
    && /\.actionsRegion\s*\{[^}]*width:\s*93\.5035%;/su.test(taskRouteStyles)
    && /\.bottomActions button\s*\{[^}]*width:\s*100%;[^}]*max-width:\s*100%;/su.test(taskListStyles),
  'task bottom actions must stay inside the safe viewport and measured route region',
)
record(
  'task_scroll_rows_fill_the_native_scroll_view',
  /\.recordRows\s*\{[^}]*box-sizing:\s*border-box;[^}]*width:\s*100%;/su.test(taskListStyles),
  'task record rows must not shrink to their content width inside the WeChat ScrollView',
)
record(
  'task_rows_override_native_button_width',
  /button\.recordRow\s*\{[^}]*width:\s*100%;[^}]*margin-right:\s*0;[^}]*margin-left:\s*0;/su.test(taskListStyles),
  'native WeChat button styles must not collapse task rows to half width',
)
const newsListRoute = read('apps/mini-taro/src/pages/news/list.tsx')
const newsListComponents = read('packages/design-system/src/components/NewsListComponents.tsx')
record(
  'news_list_sparse_truth_does_not_reserve_empty_target_lanes',
  /const listHeight = listRowCount \* 70\.64/u.test(newsListRoute)
    && /Math\.max\(rows\.length, loading \? loadingRows : 0, 1\)/u.test(newsListComponents),
  'completed news feeds must size lanes from returned truth rather than the six-row loading target',
)

const deprecatedAppShellProps = []
const unownedRouteInteractions = []
for (const file of routeComponents) {
  const ast = babelParser.parse(read(file), { sourceType: 'module', plugins: ['jsx', 'typescript'] })
  traverse(ast, {
    JSXOpeningElement(elementPath) {
      const name = elementPath.node.name
      const attributes = elementPath.node.attributes
      if (!file.includes('/_shared/') && name.type === 'JSXIdentifier' && (name.name === 'View' || name.name === 'Text')) {
        const hasOnClick = attributes.some((attribute) => (
          attribute.type === 'JSXAttribute' && attribute.name.name === 'onClick'
        ))
        if (hasOnClick) {
          const ownerAttribute = attributes.find((attribute) => (
            attribute.type === 'JSXAttribute' && attribute.name.name === 'data-owner'
          ))
          const owner = ownerAttribute?.type === 'JSXAttribute' && ownerAttribute.value?.type === 'StringLiteral'
            ? ownerAttribute.value.value
            : ''
          if (owner !== 'gear-candidate-page-dismiss') unownedRouteInteractions.push(`${file}:${owner || 'unowned'}`)
        }
      }
      if (name.type !== 'JSXIdentifier' || name.name !== 'AppShell') return
      const names = elementPath.node.attributes.flatMap((attribute) => (
        attribute.type === 'JSXAttribute' && attribute.name.type === 'JSXIdentifier'
          ? [attribute.name.name]
          : []
      ))
      const deprecated = ['className', 'chrome', 'chromeVariant', 'contentOrigin'].filter((prop) => names.includes(prop))
      if (deprecated.length) deprecatedAppShellProps.push(`${file}:${deprecated.join('|')}`)
    },
  })
}
record(
  'route_pages_do_not_build_unowned_view_interactions',
  unownedRouteInteractions.length === 0,
  unownedRouteInteractions.join(', ') || 'none',
)
record('routes_use_only_current_app_shell_api', deprecatedAppShellProps.length === 0, deprecatedAppShellProps.join(', ') || 'none')

const componentSources = walk('packages/design-system/src', ['.ts', '.tsx'])
const rawButtonOwners = componentSources.filter((file) => file !== 'packages/design-system/src/components/ControlButton.tsx' && /<Button\b/.test(read(file)))
record('native_button_has_one_shared_owner', rawButtonOwners.length === 0, rawButtonOwners.join(', ') || 'ControlButton only')

const currentUiRecords = [
  ...walk('docs/design/current-ui', ['.json', '.md']),
  ...walk('packages/design-system/assets', ['.json', '.md']),
]
const fallbackJargonRecords = currentUiRecords.filter((file) => /回退/u.test(read(file)))
record(
  'current_ui_contracts_do_not_prescribe_fallback_implementation_jargon',
  fallbackJargonRecords.length === 0,
  fallbackJargonRecords.join(', ') || 'none',
)
const nonPortableCurrentUiRecords = currentUiRecords.filter((file) => /(?:\/Users\/|[A-Z]:\\Users\\)/u.test(read(file)))
record(
  'current_ui_records_use_portable_paths',
  nonPortableCurrentUiRecords.length === 0,
  nonPortableCurrentUiRecords.join(', ') || 'none',
)

const requestDomainAudit = read('scripts/audit-taro-request-domain.js')
record(
  'request_domain_audit_is_report_only_by_default',
  !requestDomainAudit.includes('writeFileSync') && !requestDomainAudit.includes('artifacts/current-ui'),
  'runtime audits must not create unregistered repository artifacts',
)

const wechatAutomator = read('scripts/wechat-automator.js')
const reuseConnectTimeoutMs = Number(wechatAutomator.match(/const reuseConnectTimeoutMs = (\d+)/u)?.[1])
record(
  'wechat_automation_reuse_probe_is_bounded_and_launch_is_opt_in',
  reuseConnectTimeoutMs > 0
    && reuseConnectTimeoutMs <= 3000
    && wechatAutomator.includes("process.env.WECHAT_AUTOMATOR_LAUNCH !== '1'")
    && wechatAutomator.includes('refusing to relaunch DevTools'),
  `reuseConnectTimeoutMs=${reuseConnectTimeoutMs || 'missing'}`,
)

const reconstructionPath = 'packages/design-system/src/components/reconstruction.module.scss'
const reconstruction = read(reconstructionPath)
const legacyChromeSelector = /\.(?:pageFrame|pageHeader|pageCenteredTitle|pageHeaderLeading|pageHeaderAction|pageHeaderFlexSpacer|pageRootContext|sharedBack|pushedBack|titleRail|newsPushedTitleRail)\b/
record('reconstruction_css_has_no_page_frame_geometry', !legacyChromeSelector.test(reconstruction), 'legacy selector present')
const importantCount = (reconstruction.match(/!important/g) ?? []).length
record('reconstruction_override_budget_is_bounded', importantCount <= 20, `important=${importantCount}; max=20`)

const pageFrame = read('packages/design-system/src/components/PageFrame.tsx')
const pageChrome = read('packages/design-system/src/components/PageFrame.chrome.ts')
const ownerStyles = read('packages/design-system/src/components/owners.module.scss')
const newsHomePage = read('apps/mini-taro/src/pages/news/news.tsx')
record(
  'page_frame_uses_owner_geometry_only',
  pageFrame.includes("ownerStyle('pageFrameHeader')") && !/reconstructionStyle\('(?:pageFrame|pageHeader|sharedBack|titleRail)/.test(pageFrame),
  'PageFrame owner boundary',
)
record(
  'four_primary_tabs_share_root_chrome_contract',
  ['news-home', 'builds-home', 'simulator-home', 'profile'].every((variant) => pageChrome.includes(`'${variant}'`))
    && ownerStyles.includes('.pageFrame-root .pageFrameHeader'),
  'root variants or root owner missing',
)
const newsCarouselInvocation = /<FeaturedCarousel[\s\S]*?\/>/u.exec(newsHomePage)?.[0] ?? ''
record(
  'news_home_carousel_keeps_autoplay_behavior',
  /\bautoplay\b/u.test(newsCarouselInvocation),
  'the root news carousel must opt into timed rotation explicitly',
)

const designTokenStyles = read('packages/design-system/src/tokens.scss')
const designTokenSource = read('packages/design-system/src/tokens.ts')
const tabBarStyles = read('packages/design-system/src/components/TabBar.module.scss')
const buildsComponentContract = JSON.parse(read('docs/design/current-ui/routes/builds-home/component-contract.json'))
const buildIntelRasterManifest = JSON.parse(read('packages/design-system/assets/raster/build-intel-v1/manifest.json'))
const assetsManifestSource = read('packages/assets-manifest/src/index.ts')
const sharedTabBarHeight = Number(designTokenStyles.match(/--tabbar-height:\s*([\d.]+)px/)?.[1])
const isolatedTabBarHeight = Number(tabBarStyles.match(/--route-tabbar-control-height:\s*([\d.]+)px/)?.[1])
const typedTabBarHeight = Number(designTokenSource.match(/tabBarHeight:\s*([\d.]+)/)?.[1])
const sharedTabBarIcon = Number(designTokenStyles.match(/--tabbar-icon:\s*([\d.]+)px/)?.[1])
const isolatedTabBarIcon = Number(tabBarStyles.match(/--tabbar-icon:\s*([\d.]+)px/)?.[1])
const typedTabBarIcon = Number(designTokenSource.match(/tabBarIcon:\s*([\d.]+)/)?.[1])
const targetTabBarHeight = Number(buildsComponentContract.layoutContract?.regionHeightsCssPx?.product_tab_bar_target_scaled)
const contractTabBarHeight = Number(buildsComponentContract.layoutContract?.regionHeightsCssPx?.product_tab_bar_shared)
record(
  'product_tab_bar_uses_one_target_sized_metric',
  [isolatedTabBarHeight, typedTabBarHeight, contractTabBarHeight].every((value) => value === sharedTabBarHeight)
    && [isolatedTabBarIcon, typedTabBarIcon].every((value) => value === sharedTabBarIcon)
    && Math.abs(sharedTabBarHeight - targetTabBarHeight) <= 0.5,
  `height=${sharedTabBarHeight}/${isolatedTabBarHeight}/${typedTabBarHeight}/${contractTabBarHeight}; target=${targetTabBarHeight}; icon=${sharedTabBarIcon}/${isolatedTabBarIcon}/${typedTabBarIcon}`,
)

const buildsOverview = read('packages/design-system/src/components/BuildSpecializationOverview.tsx')
const buildsOverviewStyles = read('packages/design-system/src/components/BuildsHomeComponents.module.scss')
const buildsAssetContract = JSON.parse(read('docs/design/current-ui/routes/builds-home/asset-contract.json'))
const specializationObjectSlot = buildsAssetContract.slots?.find((slot) => slot.slotId === 'asset_slot.builds-specialization-object')
const specializationRuntimeCrop = specializationObjectSlot?.runtimeCrop
record(
  'builds_specialization_icon_honors_fill_contract',
  specializationObjectSlot?.targetAspect.includes('aspectFill')
    && specializationRuntimeCrop?.fit === 'aspectFill'
    && specializationRuntimeCrop?.scale >= 1
    && buildsOverview.includes('mode="aspectFill"')
    && /\.specializationImage\s*\{[^}]*object-fit:\s*cover;/s.test(buildsOverviewStyles)
    && /\.specializationImage\s*\{[^}]*inset:\s*0;[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*height:\s*100%;/s.test(buildsOverviewStyles)
    && !/\.specializationImage\s*\{[^}]*(?:border-radius|overflow|transform):/s.test(buildsOverviewStyles),
  'specialization object must fill the parent-owned circular viewport without a second native-image crop layer',
)
record(
  'build_intel_asset_registry_preserves_runtime_review_status',
  buildIntelRasterManifest.status === 'candidate_pending_runtime_review'
    && buildIntelRasterManifest.assets.every((asset) => asset.status === buildIntelRasterManifest.status)
    && assetsManifestSource.includes('reviewStatus: asset.status as CandidateReviewStatus')
    && assetsManifestSource.includes('reviewStatus: buildIntelRasterManifest.status as CandidateReviewStatus'),
  `manifest=${buildIntelRasterManifest.status}; assets=${buildIntelRasterManifest.assets.length}`,
)
record(
  'asset_registry_does_not_hardcode_review_promotions',
  !/reviewStatus:\s*'/u.test(assetsManifestSource)
    && assetsManifestSource.includes('asset.reviewStatus as ProductionReviewStatus')
    && assetsManifestSource.includes('newsHomeRasterManifest.status as ProductionReviewStatus'),
  'candidate and production review states must flow from their source manifests',
)

const gameObjectIcon = read('packages/design-system/src/components/GameObjectIcon.tsx')
const workbenchComponents = read('packages/design-system/src/components/WorkbenchComponents.tsx')
const workbenchStyles = read('packages/design-system/src/components/WorkbenchComponents.module.scss')
const workbenchComponentContract = JSON.parse(read('docs/design/current-ui/routes/workbench/component-contract.json'))
const workbenchSpecSummaryContract = workbenchComponentContract.components?.find((component) => component.owner === 'WorkbenchSpecSummary')?.contract
record(
  'game_object_icon_owns_a_nonzero_fill_box',
  gameObjectIcon.includes('mode="aspectFill"')
    && /\.objectIcon\s*\{[^}]*place-items:\s*center;/s.test(ownerStyles)
    && /\.objectImage\s*\{[^}]*position:\s*absolute;[^}]*inset:\s*0;[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*object-fit:\s*cover;/s.test(ownerStyles),
  'trusted runtime object images must fill their owner instead of collapsing to a zero-sized grid item',
)
record(
  'workbench_picker_affordances_have_distinct_visual_owners',
  workbenchComponents.includes("data-role=\"workbench-scenario-picker\"")
    && workbenchComponents.includes("data-role=\"workbench-specialization-picker\"")
    && /\.scenarioControl\s*\{[^}]*width:\s*max-content;[^}]*max-width:\s*100%;[^}]*justify-self:\s*start;/s.test(workbenchStyles)
    && workbenchSpecSummaryContract?.interactions?.some((interaction) => interaction.includes('single trailing right chevron'))
    && workbenchSpecSummaryContract?.interactions?.some((interaction) => interaction.includes('down chevron adjacent')),
  'scenario disclosure stays beside scenario copy; only specialization selection owns the trailing card chevron',
)

const sharedPageFrame = read('packages/design-system/src/components/PageFrame.tsx')
const pageFrameStyles = read('packages/design-system/src/components/owners.module.scss')
record(
  'pushed_action_header_preserves_back_and_title_geometry',
  sharedPageFrame.includes("labeledBack && ownerStyle('pageFrameBackControlLabeled')")
    && sharedPageFrame.includes("labeledBack && ownerStyle('pageFrameBackButtonLabeled')")
    && pageFrameStyles.includes('.pageFrame-pushed-action .pageFrameHeaderTitle { display: block; }')
    && pageFrameStyles.includes('.pageFrame-pushed-action .pageFrameTitleRail { display: none; }')
    && !pageFrameStyles.includes('.pageFrame-pushed-action .pageFrameBackControl { width: 68px; }'),
  'pushed action headers must not offset an icon-only back glyph or truncate the centered title with ornament rails',
)

const gearDetailPage = read('apps/mini-taro/src/pages/builds/detail.tsx')
const gearDetailModel = read('apps/mini-taro/src/pages/builds/gear-detail-model.ts')
const gearDetailComponents = read('packages/design-system/src/components/GearDetailComponents.tsx')
const gearTruthContract = JSON.parse(read('docs/design/current-ui/routes/gear-detail/truth-adaptation.json'))
const gearCandidateSelection = /const chooseCandidate[\s\S]*?const chooseEnhancement/u.exec(gearDetailPage)?.[0] ?? ''
record(
  'gear_detail_consumes_current_backend_contracts',
  ['gearResolve(', 'communityTemplateImport(', 'gearStatSnapshot('].every((call) => gearDetailPage.includes(call))
    && ['websim.gearResolve', 'websim.gearCommunityImport', 'websim.gearStatSnapshots'].every((endpoint) => gearTruthContract.runtimeFacts?.endpoints?.includes(endpoint)),
  'Taro gear detail or truth contract is missing a resolver/import/snapshot consumer',
)
record(
  'gear_detail_consumes_backend_owned_display_facts',
  gearDetailModel.includes("item['primaryStatKey']")
    && gearDetailModel.includes("item['equipmentBadges']")
    && gearDetailModel.includes('weaponTypeLabels')
    && gearDetailModel.includes('candidateBadgeLabels')
    && !gearDetailModel.includes('primaryStatKeyForSpec')
    && !gearDetailModel.includes("item['uniqueEquipped']")
    && gearDetailComponents.includes('gear-candidate-badges'),
  'Taro must localize backend display facts without recreating specialization or equipment rules',
)
record(
  'gear_candidate_selection_closes_before_resolution',
  gearCandidateSelection.includes('setCandidateOpen(false)')
    && gearCandidateSelection.includes('setEquipped(nextEquipped)')
    && gearCandidateSelection.includes('await resolveSelection(nextEquipped, nextEnhancements)')
    && gearCandidateSelection.indexOf('setCandidateOpen(false)') < gearCandidateSelection.indexOf('await resolveSelection(nextEquipped, nextEnhancements)')
    && gearCandidateSelection.indexOf('setEquipped(nextEquipped)') < gearCandidateSelection.indexOf('await resolveSelection(nextEquipped, nextEnhancements)'),
  'candidate clicks must close the panel and persist the local draft before asynchronous backend verification',
)

const babelConfig = read('apps/mini-taro/babel.config.cjs')
const markerPlugin = read('apps/mini-taro/config/babel-data-selector-markers.cjs')
record(
  'data_selector_css_has_runtime_markers',
  babelConfig.includes('babel-data-selector-markers.cjs')
    && markerPlugin.includes("name.startsWith('data-')")
    && markerPlugin.includes("@wow-mini/design-system/components/selector-markers"),
  'compiler marker plugin missing',
)

const summary = {
  status: findings.length ? 'fail' : 'pass',
  checkedRoutes: configuredRoutes.length,
  checkedContracts: contractRoutes.length,
  checks: checks.length,
  reconstructionImportantCount: importantCount,
  findings,
}
console.log(JSON.stringify(summary, null, 2))
if (findings.length) process.exitCode = 1
