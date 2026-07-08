#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_NOT_READY = 17

const REQUIRED_COMPONENT_EXTENSIONS = ['js', 'json', 'wxml', 'wxss']
const REQUIRED_SURFACES = [
  'news_home',
  'news_list_detail',
  'builds_tab',
  'current_spec_workbench',
  'talent_simulator',
  'gear_detail',
  'simc',
  'chickenbro',
  'tasks',
  'profile_templates'
]

const DEFAULT_REGISTRY = {
  schemaVersion: 1,
  status: 'owner_registry_source_ready',
  foundationOwners: [
    { name: 'AppShell', componentPath: 'components/app-shell/app-shell', boundary: 'app_background_and_tab_safe_floor' },
    { name: 'PageFrame', componentPath: 'components/page-frame/page-frame', boundary: 'route_spacing_scroll_and_safe_area' },
    { name: 'WowPanel', componentPath: 'components/wow-panel/wow-panel', boundary: 'panel_frame_border_and_material_inset' },
    { name: 'MaterialImage', componentPath: 'components/material-image/material-image', boundary: 'low_semantic_imagegen_material_fit' },
    { name: 'GameObjectIcon', componentPath: 'components/game-object-icon/game-object-icon', boundary: 'real_wow_object_icon_and_fallback' },
    { name: 'StatusVisual', componentPath: 'components/status-visual/status-visual', boundary: 'status_base_glyph_label_and_tone' },
    { name: 'ActionButton', componentPath: 'components/action-button/action-button', boundary: 'action_geometry_and_loading_disabled_states' },
    { name: 'ModuleCard', componentPath: 'components/module-card/module-card', boundary: 'workflow_module_card_geometry' },
    { name: 'ChannelDock', componentPath: 'components/channel-dock/channel-dock', boundary: 'news_channel_filter_dock' },
    { name: 'RankedFeed', componentPath: 'components/ranked-feed/ranked-feed', boundary: 'ranked_feed_rows' },
    { name: 'EvidenceLedger', componentPath: 'components/evidence-ledger/evidence-ledger', boundary: 'evidence_rows_blockers_sources_checked_at' },
    { name: 'ChatShell', componentPath: 'components/chat-shell/chat-shell', boundary: 'coach_chat_layout_input_safe_area_and_long_messages' }
  ],
  surfaceOwners: [
    { name: 'NewsHomeSurface', componentPath: 'components/news-home-surface/news-home-surface', surface: 'news_home' },
    { name: 'ArticleListBoard', componentPath: 'components/article-list-board/article-list-board', surface: 'news_list_detail' },
    { name: 'ArticleReader', componentPath: 'components/article-reader/article-reader', surface: 'news_list_detail' },
    { name: 'BuildsTabSurface', componentPath: 'components/builds-tab-surface/builds-tab-surface', surface: 'builds_tab' },
    { name: 'WorkbenchCockpitSurface', componentPath: 'components/workbench-cockpit-surface/workbench-cockpit-surface', surface: 'current_spec_workbench' },
    { name: 'TalentTreeCanvas', componentPath: 'components/talent-tree-canvas/talent-tree-canvas', surface: 'talent_simulator' },
    { name: 'GearLoadoutBoard', componentPath: 'components/gear-loadout-board/gear-loadout-board', surface: 'gear_detail' },
    { name: 'GearConfigSheet', componentPath: 'components/gear-config-sheet/gear-config-sheet', surface: 'gear_detail' },
    { name: 'SimcSubmitSurface', componentPath: 'components/simc-submit-surface/simc-submit-surface', surface: 'simc' },
    { name: 'ChickenbroCoachSurface', componentPath: 'components/chickenbro-coach-surface/chickenbro-coach-surface', surface: 'chickenbro' },
    { name: 'TaskQueueBoard', componentPath: 'components/task-queue-board/task-queue-board', surface: 'tasks' },
    { name: 'TaskResultReport', componentPath: 'components/task-result-report/task-result-report', surface: 'tasks' },
    { name: 'ProfileIdentityPanel', componentPath: 'components/profile-identity-panel/profile-identity-panel', surface: 'profile_templates' },
    { name: 'TemplateLibraryBoard', componentPath: 'components/template-library-board/template-library-board', surface: 'profile_templates' }
  ],
  surfaceCoverage: {
    news_home: ['NewsHomeSurface'],
    news_list_detail: ['ArticleListBoard', 'ArticleReader'],
    builds_tab: ['BuildsTabSurface'],
    current_spec_workbench: ['WorkbenchCockpitSurface'],
    talent_simulator: ['TalentTreeCanvas'],
    gear_detail: ['GearLoadoutBoard', 'GearConfigSheet'],
    simc: ['SimcSubmitSurface'],
    chickenbro: ['ChickenbroCoachSurface'],
    tasks: ['TaskQueueBoard', 'TaskResultReport'],
    profile_templates: ['ProfileIdentityPanel', 'TemplateLibraryBoard']
  },
  boundaryOwners: {
    realObjectIconOwner: 'GameObjectIcon',
    materialOwner: 'MaterialImage',
    statusOwner: 'StatusVisual',
    actionOwner: 'ActionButton',
    evidenceOwner: 'EvidenceLedger',
    chatOwner: 'ChatShell'
  },
  forbiddenOwners: ['StatusBadge', 'status-badge'],
  pageIntegration: false,
  runtimeVerified: false,
  finalAccepted: false
}

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(filePath))
}

function read(filePath) {
  return fs.readFileSync(resolvePath(filePath), 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function readRegistry(args) {
  const registryFile = optionValue(args, '--registry-file', '')
  if (!registryFile) return DEFAULT_REGISTRY
  return readJson(registryFile)
}

function ownerFiles(componentPath) {
  return REQUIRED_COMPONENT_EXTENSIONS.map((extension) => `${componentPath}.${extension}`)
}

function validateComponent(owner, missingRequirements) {
  if (!owner || typeof owner !== 'object') {
    missingRequirements.push('owner_object')
    return
  }
  if (!owner.name) missingRequirements.push('owner.name')
  if (!owner.componentPath) missingRequirements.push(`owner:${owner.name || 'unknown'}:componentPath`)
  if (!owner.componentPath) return

  for (const filePath of ownerFiles(owner.componentPath)) {
    if (!exists(filePath)) {
      missingRequirements.push(`owner:${owner.name}:file:${filePath}`)
    }
  }

  const jsonPath = `${owner.componentPath}.json`
  if (exists(jsonPath)) {
    try {
      const componentJson = readJson(jsonPath)
      if (componentJson.component !== true) {
        missingRequirements.push(`owner:${owner.name}:json_component_true`)
      }
      const usingComponents = componentJson.usingComponents || {}
      for (const [alias, target] of Object.entries(usingComponents)) {
        if (alias === 'status-badge' || /status-badge/.test(String(target))) {
          missingRequirements.push(`owner:${owner.name}:forbidden_status_badge_dependency`)
        }
      }
    } catch (error) {
      missingRequirements.push(`owner:${owner.name}:json_parse_error`)
    }
  }

  for (const filePath of [`${owner.componentPath}.wxml`, `${owner.componentPath}.wxss`, `${owner.componentPath}.js`]) {
    if (exists(filePath) && /status-badge/.test(read(filePath))) {
      missingRequirements.push(`owner:${owner.name}:forbidden_status_badge_reference`)
    }
  }
}

function validateRegistry(registry) {
  const missingRequirements = []
  if (registry.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  if (registry.status !== 'owner_registry_source_ready') missingRequirements.push('status_owner_registry_source_ready')
  if (registry.pageIntegration !== false) missingRequirements.push('pageIntegration_false')
  if (registry.runtimeVerified !== false) missingRequirements.push('runtimeVerified_false')
  if (registry.finalAccepted !== false) missingRequirements.push('finalAccepted_false')

  const foundationOwners = Array.isArray(registry.foundationOwners) ? registry.foundationOwners : []
  const surfaceOwners = Array.isArray(registry.surfaceOwners) ? registry.surfaceOwners : []
  if (!foundationOwners.length) missingRequirements.push('foundationOwners_non_empty')
  if (!surfaceOwners.length) missingRequirements.push('surfaceOwners_non_empty')

  const allOwners = [...foundationOwners, ...surfaceOwners]
  const ownerNames = new Set()
  for (const owner of allOwners) {
    if (ownerNames.has(owner.name)) missingRequirements.push(`owner:${owner.name}:unique`)
    ownerNames.add(owner.name)
    validateComponent(owner, missingRequirements)
  }

  for (const forbiddenOwner of registry.forbiddenOwners || []) {
    if (ownerNames.has(forbiddenOwner)) {
      missingRequirements.push(`forbiddenOwner:${forbiddenOwner}`)
    }
  }

  const coverage = registry.surfaceCoverage || {}
  for (const surface of REQUIRED_SURFACES) {
    const owners = coverage[surface]
    if (!Array.isArray(owners) || owners.length === 0) {
      missingRequirements.push(`surface:${surface}:owners`)
      continue
    }
    for (const owner of owners) {
      if (!ownerNames.has(owner)) {
        missingRequirements.push(`surface:${surface}:owner:${owner}:registered`)
      }
    }
  }

  for (const owner of surfaceOwners) {
    if (!owner.surface || !REQUIRED_SURFACES.includes(owner.surface)) {
      missingRequirements.push(`surfaceOwner:${owner.name}:surface`)
    }
  }

  const boundaryOwners = registry.boundaryOwners || {}
  for (const [key, ownerName] of Object.entries({
    realObjectIconOwner: 'GameObjectIcon',
    materialOwner: 'MaterialImage',
    statusOwner: 'StatusVisual',
    actionOwner: 'ActionButton',
    evidenceOwner: 'EvidenceLedger',
    chatOwner: 'ChatShell'
  })) {
    if (boundaryOwners[key] !== ownerName) {
      missingRequirements.push(`boundaryOwner:${key}:${ownerName}`)
    }
    if (!ownerNames.has(ownerName)) {
      missingRequirements.push(`boundaryOwner:${key}:${ownerName}:registered`)
    }
  }

  return missingRequirements
}

function buildReport(args) {
  let registry
  try {
    registry = readRegistry(args)
  } catch (error) {
    return {
      status: 'owner_registry_invalid_json',
      ownerRegistryReady: false,
      missingRequirements: ['registry_json_parseable'],
      error: error.message,
      requiredSurfaces: REQUIRED_SURFACES
    }
  }

  const missingRequirements = validateRegistry(registry)
  const foundationOwners = Array.isArray(registry.foundationOwners) ? registry.foundationOwners : []
  const surfaceOwners = Array.isArray(registry.surfaceOwners) ? registry.surfaceOwners : []
  const surfaceCoverage = registry.surfaceCoverage || {}
  const ownerRegistryReady = missingRequirements.length === 0

  return {
    status: ownerRegistryReady ? 'owner_registry_source_ready' : 'owner_registry_incomplete',
    ownerRegistryReady,
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    ownerCount: foundationOwners.length + surfaceOwners.length,
    foundationOwnerCount: foundationOwners.length,
    surfaceOwnerCount: surfaceOwners.length,
    requiredSurfaces: REQUIRED_SURFACES,
    coveredSurfaces: REQUIRED_SURFACES.filter((surface) => Array.isArray(surfaceCoverage[surface]) && surfaceCoverage[surface].length > 0),
    boundaryOwners: registry.boundaryOwners || {},
    missingRequirements,
    nonPromotion: [
      'not_target_locked',
      'not_active_implementation_permit',
      'not_page_integration',
      'not_runtime_verified',
      'not_final_accepted'
    ]
  }
}

function main() {
  const args = process.argv.slice(2)
  const flags = new Set(args)
  const report = buildReport(args)

  if (flags.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`ownerRegistryReady=${report.ownerRegistryReady}\n`)
    process.stdout.write(`ownerCount=${report.ownerCount || 0}\n`)
    if (report.missingRequirements && report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-ready') && !report.ownerRegistryReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
