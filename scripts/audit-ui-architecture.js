#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const babelParser = require('@babel/parser')
const traverse = require('@babel/traverse').default

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
const evidencePolicy = JSON.parse(read('docs/design/current-ui/active-evidence-policy.json'))
const runtimeReviewStatus = JSON.parse(read('docs/design/current-ui/runtime-review-status.json'))
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
  interactionContract.status === 'active_unverified'
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
const reviewRoutes = runtimeReviewStatus.routes ?? []
const reviewRouteIds = sorted(reviewRoutes.map((review) => review.route))
record(
  'runtime_review_status_covers_all_target_routes',
  runtimeReviewStatus.status === 'active_unverified'
    && JSON.stringify(reviewRouteIds) === JSON.stringify(targetRouteIds),
  `reviews=${reviewRouteIds.length}`,
)
for (const review of reviewRoutes) {
  const target = targetRegistry.canonicalTargets.find((candidate) => candidate.route === review.route)
  const interaction = interactionContract.interactions.find((candidate) => candidate.route === review.route)
  const contractRootExists = typeof review.contractRoot === 'string' && fs.existsSync(path.join(root, review.contractRoot))
  record(
    `runtime_review_boundary:${review.route}`,
    ['PASS', 'FAIL', 'UNVERIFIED'].includes(review.status)
      && review.targetArtifact === target?.path
      && review.path === interaction?.path
      && contractRootExists
      && (review.status !== 'UNVERIFIED' || runtimeReviewStatus.sharedMissingEvidence?.length > 0),
    `status=${review.status}; target=${Boolean(target)}; interaction=${Boolean(interaction)}; contract=${contractRootExists}`,
  )
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
record(
  'shared_route_layout_owners_cover_current_layout_families',
  routeStageConsumers.length === 8 && routeFlowConsumers.length === 3 && routeColumnConsumers.length === 4 && routeGridConsumers.length === 2 && routeRegionConsumers.length === 4,
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
