#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_SCORECARD_PATH = 'artifacts/ui-system-rebuild/runtime/visual-acceptance-scorecard.json'
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
const REQUIRED_VIEWPORTS = ['compact', 'standard', 'large']
const REQUIRED_SURFACE_PATH_FIELDS = [
  'currentScreenshotPath',
  'targetImagePath',
  'implementationScreenshotPath',
  'comparisonPath',
  'overlayPath',
  'redZonePath'
]
const REQUIRED_COMPONENT_PATH_FIELDS = [
  'currentCropPath',
  'targetCropPath',
  'implementationCropPath',
  'overlayPath',
  'redZonePath'
]
const MIN_SURFACE_SCORE = 90
const MIN_COMPONENT_SCORE = 90
const MAX_GUTTER_DELTA_PX = 2
const MAX_SLOT_DELTA_PX = 2
const MAX_GLYPH_CENTER_DELTA_PX = 1

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

function isFile(filePath) {
  return exists(filePath) && fs.statSync(resolvePath(filePath)).isFile()
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(resolvePath(filePath), 'utf8'))
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

function arrayIncludesAll(source, required) {
  return Array.isArray(source) && required.every((item) => source.includes(item))
}

function validateSurfaceMetrics(surface, index, missingRequirements) {
  const prefix = `surfaces[${index}].metrics`
  const metrics = surface.metrics
  if (!metrics || typeof metrics !== 'object') {
    missingRequirements.push(`${prefix}`)
    return
  }
  const numericLimits = [
    ['gutterDeltaPxMax', MAX_GUTTER_DELTA_PX],
    ['slotDeltaPxMax', MAX_SLOT_DELTA_PX],
    ['glyphCenterDeltaPxMax', MAX_GLYPH_CENTER_DELTA_PX],
    ['textOverflowCount', 0],
    ['horizontalOverflowCount', 0],
    ['fakeChromeCount', 0],
    ['blockingRedZoneCount', 0]
  ]
  for (const [field, max] of numericLimits) {
    if (!isNumber(metrics[field])) {
      missingRequirements.push(`${prefix}.${field}`)
      continue
    }
    if (metrics[field] > max) missingRequirements.push(`${prefix}.${field}_within_${max}`)
  }
}

function validateComponentCrop(crop, surfaceIndex, cropIndex, missingRequirements) {
  const prefix = `surfaces[${surfaceIndex}].componentCrops[${cropIndex}]`
  if (!hasText(crop.component)) missingRequirements.push(`${prefix}.component`)
  if (!hasText(crop.owner)) missingRequirements.push(`${prefix}.owner`)
  if (crop.status !== 'pass') missingRequirements.push(`${prefix}.status_pass`)
  if (!isNumber(crop.score) || crop.score < MIN_COMPONENT_SCORE) {
    missingRequirements.push(`${prefix}.score_gte_${MIN_COMPONENT_SCORE}`)
  }
  for (const field of REQUIRED_COMPONENT_PATH_FIELDS) {
    if (!hasText(crop[field]) || !isFile(crop[field])) missingRequirements.push(`${prefix}.${field}_file_exists`)
  }
  if (!Array.isArray(crop.redZones)) {
    missingRequirements.push(`${prefix}.redZones_array`)
  } else if (crop.redZones.length > 0) {
    missingRequirements.push(`${prefix}.redZones_empty_for_pass`)
  }
}

function validateSurface(surface, index, missingRequirements) {
  const prefix = `surfaces[${index}]`
  if (!hasText(surface.id)) missingRequirements.push(`${prefix}.id`)
  if (surface.id && !REQUIRED_SURFACES.includes(surface.id)) missingRequirements.push(`${prefix}.id_required_surface`)
  if (surface.status !== 'pass') missingRequirements.push(`${prefix}.status_pass`)
  if (!isNumber(surface.score) || surface.score < MIN_SURFACE_SCORE) {
    missingRequirements.push(`${prefix}.score_gte_${MIN_SURFACE_SCORE}`)
  }
  if (!arrayIncludesAll(surface.viewports, REQUIRED_VIEWPORTS)) {
    missingRequirements.push(`${prefix}.viewports_compact_standard_large`)
  }
  for (const field of REQUIRED_SURFACE_PATH_FIELDS) {
    if (!hasText(surface[field]) || !isFile(surface[field])) missingRequirements.push(`${prefix}.${field}_file_exists`)
  }
  if (!Array.isArray(surface.componentCrops) || surface.componentCrops.length === 0) {
    missingRequirements.push(`${prefix}.componentCrops_non_empty`)
  } else {
    surface.componentCrops.forEach((crop, cropIndex) => validateComponentCrop(crop, index, cropIndex, missingRequirements))
  }
  validateSurfaceMetrics(surface, index, missingRequirements)
}

function validateScorecard(scorecard) {
  const missingRequirements = []
  if (scorecard.status !== 'visual_acceptance_scorecard_ready') missingRequirements.push('status_visual_acceptance_scorecard_ready')
  if (scorecard.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  for (const field of ['targetLockDecision', 'activePermit', 'routeSmokeExecutionManifest', 'productionAssetManifestPath', 'checkedAt']) {
    if (!hasText(scorecard[field])) missingRequirements.push(field)
  }
  for (const field of ['targetLockDecision', 'activePermit', 'routeSmokeExecutionManifest', 'productionAssetManifestPath']) {
    if (hasText(scorecard[field]) && !exists(scorecard[field])) missingRequirements.push(`${field}_exists`)
  }
  if (scorecard.source !== 'real_miniprogram_runtime') missingRequirements.push('source_real_miniprogram_runtime')
  if (scorecard.captureSafe !== true) missingRequirements.push('captureSafe_true')
  if (scorecard.minSurfaceScore !== MIN_SURFACE_SCORE) missingRequirements.push(`minSurfaceScore_${MIN_SURFACE_SCORE}`)
  if (scorecard.minComponentScore !== MIN_COMPONENT_SCORE) missingRequirements.push(`minComponentScore_${MIN_COMPONENT_SCORE}`)
  if (!arrayIncludesAll(scorecard.requiredViewports, REQUIRED_VIEWPORTS)) {
    missingRequirements.push('requiredViewports_compact_standard_large')
  }
  if (!Array.isArray(scorecard.failedSurfaces) || scorecard.failedSurfaces.length !== 0) {
    missingRequirements.push('failedSurfaces_empty')
  }
  if (!Array.isArray(scorecard.blockingRedZones) || scorecard.blockingRedZones.length !== 0) {
    missingRequirements.push('blockingRedZones_empty')
  }
  if (!Array.isArray(scorecard.surfaces) || scorecard.surfaces.length === 0) {
    missingRequirements.push('surfaces_non_empty')
  } else {
    const surfaceIds = scorecard.surfaces.map((surface) => surface.id)
    for (const surface of REQUIRED_SURFACES) {
      if (!surfaceIds.includes(surface)) missingRequirements.push(`surfaces_missing:${surface}`)
    }
    scorecard.surfaces.forEach((surface, index) => validateSurface(surface, index, missingRequirements))
  }
  return missingRequirements
}

function buildReport(args) {
  const scorecardPath = optionValue(args, ['--scorecard-file', '--manifest-file'], DEFAULT_SCORECARD_PATH)
  if (!exists(scorecardPath)) {
    return {
      status: 'visual_acceptance_scorecard_missing',
      scorecardPath,
      scorecardExists: false,
      visualAcceptanceReady: false,
      missingRequirements: ['visual_acceptance_scorecard_file'],
      defaultScorecardPath: DEFAULT_SCORECARD_PATH,
      requiredSurfaces: REQUIRED_SURFACES,
      requiredViewports: REQUIRED_VIEWPORTS,
      minSurfaceScore: MIN_SURFACE_SCORE,
      minComponentScore: MIN_COMPONENT_SCORE
    }
  }

  let scorecard
  try {
    scorecard = readJson(scorecardPath)
  } catch (error) {
    return {
      status: 'visual_acceptance_scorecard_invalid_json',
      scorecardPath,
      scorecardExists: true,
      visualAcceptanceReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateScorecard(scorecard)
  const visualAcceptanceReady = missingRequirements.length === 0
  return {
    status: visualAcceptanceReady ? 'visual_acceptance_scorecard_ready' : 'visual_acceptance_scorecard_invalid',
    scorecardPath,
    scorecardExists: true,
    visualAcceptanceReady,
    surfaceCount: Array.isArray(scorecard.surfaces) ? scorecard.surfaces.length : 0,
    missingRequirements,
    requiredSurfaces: REQUIRED_SURFACES,
    requiredViewports: REQUIRED_VIEWPORTS,
    minSurfaceScore: MIN_SURFACE_SCORE,
    minComponentScore: MIN_COMPONENT_SCORE,
    maxDeltas: {
      gutterDeltaPxMax: MAX_GUTTER_DELTA_PX,
      slotDeltaPxMax: MAX_SLOT_DELTA_PX,
      glyphCenterDeltaPxMax: MAX_GLYPH_CENTER_DELTA_PX
    },
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
    process.stdout.write(`scorecardPath=${report.scorecardPath}\n`)
    process.stdout.write(`visualAcceptanceReady=${report.visualAcceptanceReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-scorecard') && !report.visualAcceptanceReady) {
    process.exitCode = 13
  }
}

main()
