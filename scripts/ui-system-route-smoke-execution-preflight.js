#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_EXECUTION_MANIFEST_PATH = 'artifacts/ui-system-rebuild/runtime/route-smoke-execution-manifest.json'
const REQUIRED_VIEWPORTS = ['compact', 'standard', 'large']
const REQUIRED_ASSERTIONS = [
  'noFakeChrome',
  'noHorizontalOverflow',
  'noForbiddenStrongClaims',
  'noQuarantineAssets',
  'safeAreaClear',
  'longTextFits',
  'ownerFitRespected'
]
const REQUIRED_ARTIFACT_PATHS = [
  'manifest',
  'devtoolsActionLedger',
  'screenshotsDir',
  'componentCropsDir',
  'comparisonsDir',
  'overlaysDir',
  'redZonesDir',
  'scorecardJson',
  'routeSmokeReport'
]
const DIRECTORY_ARTIFACTS = new Set(['screenshotsDir', 'componentCropsDir', 'comparisonsDir', 'overlaysDir', 'redZonesDir'])
const FORBIDDEN_VISIBLE_CLAIMS = ['DPS', '综合评分', 'S 级', 'S级', 'A 级', 'A级', '提升优先级']
const FORBIDDEN_ROUTE_ACTIONS = [
  'cli open',
  'cli close',
  'forced_restart',
  'clear_cache',
  'switch_project',
  'switch_appid',
  'delete_user_data',
  'replace_user_data',
  'login',
  'logout'
]
const REQUIRED_SCENES = [
  { id: 'news_home_top', surface: 'news_home', routePrefix: '/pages/news/news' },
  { id: 'news_home_scrolled', surface: 'news_home', routePrefix: '/pages/news/news' },
  { id: 'news_channel_official', surface: 'news_list_detail', routePrefix: '/pages/news/list' },
  { id: 'news_detail_first', surface: 'news_list_detail', routePrefix: '/pages/news/detail' },
  { id: 'builds_tab_top', surface: 'builds_tab', routePrefix: '/pages/builds/builds' },
  { id: 'builds_spec_switch', surface: 'builds_tab', routePrefix: '/pages/builds/builds' },
  { id: 'workbench_ready', surface: 'current_spec_workbench', routePrefix: '/pages/builds/workbench' },
  { id: 'workbench_blocked_gear', surface: 'current_spec_workbench', routePrefix: '/pages/builds/workbench' },
  { id: 'workbench_partial_talent', surface: 'current_spec_workbench', routePrefix: '/pages/builds/workbench' },
  { id: 'workbench_stale', surface: 'current_spec_workbench', routePrefix: '/pages/builds/workbench' },
  { id: 'workbench_evidence_expanded', surface: 'current_spec_workbench', routePrefix: '/pages/builds/workbench' },
  { id: 'talent_simulator_load', surface: 'talent_simulator', routePrefix: '/pages/builds/talent-simulator' },
  { id: 'talent_simulator_missing', surface: 'talent_simulator', routePrefix: '/pages/builds/talent-simulator' },
  { id: 'gear_detail_load', surface: 'gear_detail', routePrefix: '/pages/builds/detail' },
  { id: 'gear_missing_slot', surface: 'gear_detail', routePrefix: '/pages/builds/detail' },
  { id: 'simc_from_workbench', surface: 'simc', routePrefix: '/pages/simulator/simc' },
  { id: 'simc_blocked_templates', surface: 'simc', routePrefix: '/pages/simulator/simc' },
  { id: 'smart_analysis_tab', surface: 'simc', routePrefix: '/pages/simulator/simulator' },
  { id: 'chickenbro_empty', surface: 'chickenbro', routePrefix: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_workbench_context', surface: 'chickenbro', routePrefix: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_generating', surface: 'chickenbro', routePrefix: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_done', surface: 'chickenbro', routePrefix: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_failed', surface: 'chickenbro', routePrefix: '/pages/simulator/chickenbro' },
  { id: 'tasks_list', surface: 'tasks', routePrefix: '/pages/simulator/tasks' },
  { id: 'task_detail', surface: 'tasks', routePrefix: '/pages/simulator/task-detail' },
  { id: 'profile_guest', surface: 'profile_templates', routePrefix: '/pages/profile/profile' },
  { id: 'profile_templates', surface: 'profile_templates', routePrefix: '/pages/profile/profile' }
]
const REQUIRED_SCENE_IDS = REQUIRED_SCENES.map((scene) => scene.id)
const SCENE_BY_ID = new Map(REQUIRED_SCENES.map((scene) => [scene.id, scene]))

function optionValue(args, names, fallback) {
  const aliases = Array.isArray(names) ? names : [names]
  for (const name of aliases) {
    const index = args.indexOf(name)
    if (index !== -1) return args[index + 1]
  }
  return fallback
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(filePath))
}

function isDirectory(filePath) {
  return exists(filePath) && fs.statSync(resolvePath(filePath)).isDirectory()
}

function isFile(filePath) {
  return exists(filePath) && fs.statSync(resolvePath(filePath)).isFile()
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(resolvePath(filePath), 'utf8'))
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function arrayIncludesAll(source, required) {
  return Array.isArray(source) && required.every((item) => source.includes(item))
}

function validateArtifactPaths(manifest, missingRequirements) {
  if (!manifest.artifactPaths || typeof manifest.artifactPaths !== 'object') {
    missingRequirements.push('artifactPaths')
    return
  }
  for (const field of REQUIRED_ARTIFACT_PATHS) {
    const artifactPath = manifest.artifactPaths[field]
    if (!hasText(artifactPath)) {
      missingRequirements.push(`artifactPaths.${field}`)
      continue
    }
    if (DIRECTORY_ARTIFACTS.has(field)) {
      if (!isDirectory(artifactPath)) missingRequirements.push(`artifactPaths.${field}_directory_exists`)
    } else if (!isFile(artifactPath)) {
      missingRequirements.push(`artifactPaths.${field}_file_exists`)
    }
  }
}

function validateScene(scene, index, missingRequirements) {
  const prefix = `sceneResults[${index}]`
  const expectedScene = SCENE_BY_ID.get(scene.id)
  if (!hasText(scene.id)) missingRequirements.push(`${prefix}.id`)
  if (scene.id && !expectedScene) missingRequirements.push(`${prefix}.id_required_scene`)
  if (expectedScene) {
    if (scene.surface !== expectedScene.surface) missingRequirements.push(`${prefix}.surface_${expectedScene.surface}`)
    if (!hasText(scene.route) || !scene.route.startsWith(expectedScene.routePrefix)) {
      missingRequirements.push(`${prefix}.route_${expectedScene.routePrefix}`)
    }
  }
  if (scene.status !== 'pass') missingRequirements.push(`${prefix}.status_pass`)
  if (!arrayIncludesAll(scene.viewports, REQUIRED_VIEWPORTS)) {
    missingRequirements.push(`${prefix}.viewports_compact_standard_large`)
  }
  if (!scene.assertions || typeof scene.assertions !== 'object') {
    missingRequirements.push(`${prefix}.assertions`)
  } else {
    for (const assertion of REQUIRED_ASSERTIONS) {
      if (scene.assertions[assertion] !== true) missingRequirements.push(`${prefix}.assertions.${assertion}_true`)
    }
  }
  if (!hasText(scene.screenshotPath) || !isFile(scene.screenshotPath)) {
    missingRequirements.push(`${prefix}.screenshotPath_file_exists`)
  }
  if (!Array.isArray(scene.componentCropPaths) || scene.componentCropPaths.length === 0) {
    missingRequirements.push(`${prefix}.componentCropPaths_non_empty`)
  } else {
    scene.componentCropPaths.forEach((cropPath, cropIndex) => {
      if (!isFile(cropPath)) missingRequirements.push(`${prefix}.componentCropPaths[${cropIndex}]_file_exists`)
    })
  }
  for (const field of ['comparisonPath', 'overlayPath', 'redZonePath']) {
    if (!hasText(scene[field]) || !isFile(scene[field])) missingRequirements.push(`${prefix}.${field}_file_exists`)
  }
  if (!Array.isArray(scene.routeActions) || scene.routeActions.length === 0) {
    missingRequirements.push(`${prefix}.routeActions_non_empty`)
  } else {
    const forbidden = scene.routeActions
      .map((action) => action.action)
      .filter((action) => FORBIDDEN_ROUTE_ACTIONS.includes(action))
    if (forbidden.length) missingRequirements.push(`${prefix}.routeActions_no_forbidden_actions`)
  }
  if (!Array.isArray(scene.visibleStrongClaims)) {
    missingRequirements.push(`${prefix}.visibleStrongClaims_empty_array`)
  } else if (scene.visibleStrongClaims.length > 0) {
    missingRequirements.push(`${prefix}.visibleStrongClaims_empty`)
    for (const claim of scene.visibleStrongClaims) {
      if (FORBIDDEN_VISIBLE_CLAIMS.includes(claim)) missingRequirements.push(`${prefix}.visibleStrongClaims_no_forbidden_claims`)
    }
  }
  if (!Array.isArray(scene.quarantineAssetReferences)) {
    missingRequirements.push(`${prefix}.quarantineAssetReferences_empty_array`)
  } else if (scene.quarantineAssetReferences.length > 0) {
    missingRequirements.push(`${prefix}.quarantineAssetReferences_empty`)
  }
}

function validateManifest(manifest) {
  const missingRequirements = []
  if (manifest.status !== 'route_smoke_execution_ready') missingRequirements.push('status_route_smoke_execution_ready')
  if (manifest.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  for (const field of ['targetLockDecision', 'activePermit', 'devtoolsActionLedgerPath', 'productionAssetManifestPath', 'checkedAt']) {
    if (!hasText(manifest[field])) missingRequirements.push(field)
  }
  for (const field of ['targetLockDecision', 'activePermit', 'devtoolsActionLedgerPath', 'productionAssetManifestPath']) {
    if (hasText(manifest[field]) && !exists(manifest[field])) missingRequirements.push(`${field}_exists`)
  }
  if (manifest.captureSafe !== true) missingRequirements.push('captureSafe_true')
  if (!arrayIncludesAll(manifest.viewportMatrix, REQUIRED_VIEWPORTS)) {
    missingRequirements.push('viewportMatrix_compact_standard_large')
  }
  validateArtifactPaths(manifest, missingRequirements)
  if (!manifest.scorecard || typeof manifest.scorecard !== 'object') {
    missingRequirements.push('scorecard')
  } else {
    if (manifest.scorecard.status !== 'pass') missingRequirements.push('scorecard.status_pass')
    if (manifest.scorecard.sceneCount !== REQUIRED_SCENE_IDS.length) missingRequirements.push('scorecard.sceneCount_required')
    if (!Array.isArray(manifest.scorecard.failedScenes) || manifest.scorecard.failedScenes.length !== 0) {
      missingRequirements.push('scorecard.failedScenes_empty')
    }
  }
  if (!Array.isArray(manifest.sceneResults) || manifest.sceneResults.length === 0) {
    missingRequirements.push('sceneResults_non_empty')
  } else {
    const sceneIds = manifest.sceneResults.map((scene) => scene.id)
    for (const sceneId of REQUIRED_SCENE_IDS) {
      if (!sceneIds.includes(sceneId)) missingRequirements.push(`sceneResults_missing:${sceneId}`)
    }
    manifest.sceneResults.forEach((scene, index) => validateScene(scene, index, missingRequirements))
  }
  return missingRequirements
}

function buildReport(args) {
  const executionManifestPath = optionValue(
    args,
    ['--execution-file', '--manifest-file'],
    DEFAULT_EXECUTION_MANIFEST_PATH
  )
  if (!exists(executionManifestPath)) {
    return {
      status: 'route_smoke_execution_missing',
      executionManifestPath,
      executionManifestExists: false,
      routeSmokeExecutionReady: false,
      missingRequirements: ['route_smoke_execution_manifest_file'],
      defaultExecutionManifestPath: DEFAULT_EXECUTION_MANIFEST_PATH,
      requiredSceneIds: REQUIRED_SCENE_IDS,
      requiredViewports: REQUIRED_VIEWPORTS,
      requiredArtifacts: REQUIRED_ARTIFACT_PATHS
    }
  }

  let manifest
  try {
    manifest = readJson(executionManifestPath)
  } catch (error) {
    return {
      status: 'route_smoke_execution_invalid_json',
      executionManifestPath,
      executionManifestExists: true,
      routeSmokeExecutionReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateManifest(manifest)
  const routeSmokeExecutionReady = missingRequirements.length === 0
  return {
    status: routeSmokeExecutionReady ? 'route_smoke_execution_ready' : 'route_smoke_execution_invalid',
    executionManifestPath,
    executionManifestExists: true,
    routeSmokeExecutionReady,
    sceneCount: Array.isArray(manifest.sceneResults) ? manifest.sceneResults.length : 0,
    viewportMatrix: Array.isArray(manifest.viewportMatrix) ? manifest.viewportMatrix : [],
    captureSafe: manifest.captureSafe === true,
    missingRequirements,
    requiredSceneIds: REQUIRED_SCENE_IDS,
    requiredViewports: REQUIRED_VIEWPORTS,
    requiredAssertions: REQUIRED_ASSERTIONS,
    requiredArtifacts: REQUIRED_ARTIFACT_PATHS,
    forbiddenVisibleClaims: FORBIDDEN_VISIBLE_CLAIMS,
    nonPromotion: [
      'not target_locked',
      'not active_implementation_permit',
      'not page_integration',
      'not runtime_verified',
      'not final_accepted'
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
    process.stdout.write(`executionManifestPath=${report.executionManifestPath}\n`)
    process.stdout.write(`routeSmokeExecutionReady=${report.routeSmokeExecutionReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-execution') && !report.routeSmokeExecutionReady) {
    process.exitCode = 11
  }
}

main()
