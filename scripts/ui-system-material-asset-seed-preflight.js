#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_SEED_PATH = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
const EXIT_NOT_READY = 19

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

const REQUIRED_CLASSES = [
  'panel',
  'border',
  'texture',
  'socket',
  'state-base',
  'state-atomic',
  'decorative'
]

const SMALL_CLASSES = new Set(['socket', 'state-base', 'state-atomic'])
const MATERIAL_KB_MAX = 350
const SMALL_KB_MAX = 96
const PACKAGE_KB_MAX = 512

const ALLOWED_OWNERS_BY_CLASS = {
  panel: ['WowPanel', 'PageFrame'],
  border: ['WowPanel', 'PageFrame', 'ActionButton'],
  texture: ['MaterialImage', 'WowPanel'],
  socket: ['GameObjectIcon', 'ModuleCard', 'ChannelDock'],
  'state-base': ['StatusVisual'],
  'state-atomic': ['StatusVisual'],
  decorative: ['AppShell', 'PageFrame', 'WowPanel']
}

const ALLOWED_FIT_BY_CLASS = {
  panel: ['nine_slice', 'fixed_aspect_wrapper'],
  border: ['nine_slice', 'scaleToFill'],
  texture: ['aspectFill', 'cover'],
  socket: ['contain'],
  'state-base': ['contain'],
  'state-atomic': ['contain'],
  decorative: ['cover', 'contain']
}

const ALLOWED_SOURCE_TYPES = ['imagegen_low_semantic_seed', 'repo_material_seed']
const FORBIDDEN_PATH_PATTERNS = [
  /pass36/i,
  /pass37/i,
  /source\.(png|jpg|jpeg|webp)$/i,
  /reference\.(png|jpg|jpeg|webp)$/i,
  /atlas\.(png|jpg|jpeg|webp)$/i,
  /ui-redesign\/20260701/i,
  /ui-v2-restoration/i,
  /ui-v3-1/i
]

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

function readText(filePath) {
  return fs.readFileSync(resolvePath(filePath), 'utf8')
}

function readJson(filePath) {
  return JSON.parse(readText(filePath))
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function hasTextArray(value) {
  return Array.isArray(value) && value.length > 0 && value.every(hasText)
}

function isPositiveNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function readPngDimensions(filePath) {
  const buffer = fs.readFileSync(resolvePath(filePath))
  if (buffer.length < 24 || buffer.toString('ascii', 1, 4) !== 'PNG') return null
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  }
}

function fileSizeKb(filePath) {
  return fs.statSync(resolvePath(filePath)).size / 1024
}

function containsForbiddenPath(filePath) {
  return FORBIDDEN_PATH_PATTERNS.some((pattern) => pattern.test(String(filePath || '')))
}

function validateAssetSeed(asset, index, missingRequirements) {
  const prefix = `assetSeeds[${index}]`

  if (!hasText(asset.id)) missingRequirements.push(`${prefix}.id`)
  if (!REQUIRED_CLASSES.includes(asset.class)) missingRequirements.push(`${prefix}.class`)
  if (!hasText(asset.owner)) {
    missingRequirements.push(`${prefix}.owner`)
  } else if (asset.class && !ALLOWED_OWNERS_BY_CLASS[asset.class]?.includes(asset.owner)) {
    missingRequirements.push(`${prefix}.owner_allowed_for_class`)
  }

  if (!hasText(asset.path)) {
    missingRequirements.push(`${prefix}.path`)
  } else {
    if (!exists(asset.path)) missingRequirements.push(`${prefix}.file_exists`)
    if (containsForbiddenPath(asset.path)) missingRequirements.push(`${prefix}.path_not_quarantine_or_reference`)
  }

  if (!isPositiveNumber(asset.width)) missingRequirements.push(`${prefix}.width`)
  if (!isPositiveNumber(asset.height)) missingRequirements.push(`${prefix}.height`)
  if (!isPositiveNumber(asset.sizeKb)) missingRequirements.push(`${prefix}.sizeKb`)
  if (!ALLOWED_FIT_BY_CLASS[asset.class]?.includes(asset.fit)) missingRequirements.push(`${prefix}.fit_allowed_for_class`)
  if (!ALLOWED_SOURCE_TYPES.includes(asset.sourceType)) missingRequirements.push(`${prefix}.sourceType_seed`)
  if (asset.seedStatus !== 'candidate_low_semantic_seed') missingRequirements.push(`${prefix}.seedStatus_candidate_low_semantic_seed`)

  if (!Array.isArray(asset.allowedSurfaces) || asset.allowedSurfaces.length === 0) {
    missingRequirements.push(`${prefix}.allowedSurfaces`)
  } else {
    for (const surface of asset.allowedSurfaces) {
      if (!REQUIRED_SURFACES.includes(surface)) missingRequirements.push(`${prefix}.allowedSurface:${surface}`)
    }
  }

  if (!hasTextArray(asset.sourceEvidence)) {
    missingRequirements.push(`${prefix}.sourceEvidence`)
  } else {
    for (const evidencePath of asset.sourceEvidence) {
      if (!exists(evidencePath)) missingRequirements.push(`${prefix}.sourceEvidence_exists:${evidencePath}`)
    }
  }

  for (const field of [
    'containsText',
    'containsFakeChrome',
    'containsRealWowObject',
    'containsSourceLogo',
    'containsBusinessConclusion',
    'containsGeneratedObjectIcon'
  ]) {
    if (asset[field] !== false) missingRequirements.push(`${prefix}.${field}_false`)
  }

  if (asset.pageDirectUseAllowed !== false) missingRequirements.push(`${prefix}.pageDirectUseAllowed_false`)
  if (asset.productionUseAllowed !== false) missingRequirements.push(`${prefix}.productionUseAllowed_false`)
  if (asset.requiresRecutBeforeProduction !== true) missingRequirements.push(`${prefix}.requiresRecutBeforeProduction_true`)

  const budget = SMALL_CLASSES.has(asset.class) ? SMALL_KB_MAX : MATERIAL_KB_MAX
  if (isPositiveNumber(asset.sizeKb) && asset.sizeKb > budget) missingRequirements.push(`${prefix}.size_budget`)

  if (asset.path && exists(asset.path)) {
    const actualSize = fileSizeKb(asset.path)
    if (isPositiveNumber(asset.sizeKb) && Math.abs(actualSize - asset.sizeKb) > 1) {
      missingRequirements.push(`${prefix}.declared_size_matches_file`)
    }
    const dimensions = readPngDimensions(asset.path)
    if (!dimensions) {
      missingRequirements.push(`${prefix}.png_dimensions_readable`)
    } else {
      if (dimensions.width !== asset.width || dimensions.height !== asset.height) {
        missingRequirements.push(`${prefix}.declared_dimensions_match_file`)
      }
    }
  }
}

function validateQuarantine(entry, index, missingRequirements) {
  const prefix = `quarantine[${index}]`
  if (!hasText(entry.path)) missingRequirements.push(`${prefix}.path`)
  if (!hasText(entry.class)) missingRequirements.push(`${prefix}.class`)
  if (!hasText(entry.reason)) missingRequirements.push(`${prefix}.reason`)
}

function validateContractAssertions(manifest, missingRequirements) {
  if (!Array.isArray(manifest.contractAssertions) || manifest.contractAssertions.length === 0) {
    missingRequirements.push('contractAssertions')
    return
  }

  manifest.contractAssertions.forEach((assertion, index) => {
    const prefix = `contractAssertions[${index}]`
    if (!hasText(assertion.id)) missingRequirements.push(`${prefix}.id`)
    if (!hasText(assertion.file)) {
      missingRequirements.push(`${prefix}.file`)
      return
    }
    if (!exists(assertion.file)) {
      missingRequirements.push(`${prefix}.file_exists:${assertion.file}`)
      return
    }
    if (!hasTextArray(assertion.requiredPatterns)) {
      missingRequirements.push(`${prefix}.requiredPatterns`)
      return
    }

    const source = readText(assertion.file)
    assertion.requiredPatterns.forEach((pattern, patternIndex) => {
      if (!new RegExp(pattern).test(source)) missingRequirements.push(`${prefix}.requiredPatterns[${patternIndex}]`)
    })
  })
}

function validateSeed(manifest) {
  const missingRequirements = []

  if (manifest.status !== 'material_asset_seed_ready') missingRequirements.push('status_material_asset_seed_ready')
  if (manifest.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  if (manifest.materialAssetSeedReady !== true) missingRequirements.push('materialAssetSeedReady_true')
  if (manifest.productionManifest !== false) missingRequirements.push('productionManifest_false')
  if (manifest.targetLocked !== false) missingRequirements.push('targetLocked_false')
  if (manifest.activeImplementationPermit !== false) missingRequirements.push('activeImplementationPermit_false')
  if (manifest.pageIntegration !== false) missingRequirements.push('pageIntegration_false')
  if (manifest.runtimeVerified !== false) missingRequirements.push('runtimeVerified_false')
  if (manifest.finalAccepted !== false) missingRequirements.push('finalAccepted_false')
  if (manifest.devtoolsTouched !== false) missingRequirements.push('devtoolsTouched_false')
  if (!hasText(manifest.checkedAt)) missingRequirements.push('checkedAt')

  if (!manifest.packageBudget || typeof manifest.packageBudget !== 'object') {
    missingRequirements.push('packageBudget')
  } else {
    if (!isPositiveNumber(manifest.packageBudget.currentKb)) missingRequirements.push('packageBudget.currentKb')
    if (!isPositiveNumber(manifest.packageBudget.maxKb)) missingRequirements.push('packageBudget.maxKb')
    if (isPositiveNumber(manifest.packageBudget.maxKb) && manifest.packageBudget.maxKb > PACKAGE_KB_MAX) {
      missingRequirements.push('packageBudget.max_within_seed_budget')
    }
    if (
      isPositiveNumber(manifest.packageBudget.currentKb) &&
      isPositiveNumber(manifest.packageBudget.maxKb) &&
      manifest.packageBudget.currentKb > manifest.packageBudget.maxKb
    ) {
      missingRequirements.push('packageBudget.current_within_max')
    }
  }

  if (!Array.isArray(manifest.assetSeeds) || manifest.assetSeeds.length === 0) {
    missingRequirements.push('assetSeeds_non_empty')
  } else {
    manifest.assetSeeds.forEach((asset, index) => validateAssetSeed(asset, index, missingRequirements))
    const ids = new Set()
    manifest.assetSeeds.forEach((asset, index) => {
      if (ids.has(asset.id)) missingRequirements.push(`assetSeeds[${index}].id_unique`)
      ids.add(asset.id)
    })

    const coveredClasses = new Set(manifest.assetSeeds.map((asset) => asset.class))
    for (const assetClass of REQUIRED_CLASSES) {
      if (!coveredClasses.has(assetClass)) missingRequirements.push(`class:${assetClass}`)
    }

    const coveredSurfaces = new Set()
    for (const asset of manifest.assetSeeds) {
      for (const surface of asset.allowedSurfaces || []) coveredSurfaces.add(surface)
    }
    for (const surface of REQUIRED_SURFACES) {
      if (!coveredSurfaces.has(surface)) missingRequirements.push(`surface:${surface}`)
    }
  }

  if (!Array.isArray(manifest.quarantine) || manifest.quarantine.length === 0) {
    missingRequirements.push('quarantine_non_empty')
  } else {
    manifest.quarantine.forEach((entry, index) => validateQuarantine(entry, index, missingRequirements))
  }

  validateContractAssertions(manifest, missingRequirements)

  return missingRequirements
}

function buildReport(args) {
  const seedPath = optionValue(args, '--seed-file', DEFAULT_SEED_PATH)
  if (!exists(seedPath)) {
    return {
      status: 'material_asset_seed_missing',
      seedPath,
      seedExists: false,
      materialAssetSeedReady: false,
      productionManifest: false,
      missingRequirements: ['material_asset_seed_file'],
      defaultSeedPath: DEFAULT_SEED_PATH,
      requiredClasses: REQUIRED_CLASSES,
      requiredSurfaces: REQUIRED_SURFACES
    }
  }

  let manifest
  try {
    manifest = readJson(seedPath)
  } catch (error) {
    return {
      status: 'material_asset_seed_invalid_json',
      seedPath,
      seedExists: true,
      materialAssetSeedReady: false,
      productionManifest: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateSeed(manifest)
  const materialAssetSeedReady = missingRequirements.length === 0
  return {
    status: materialAssetSeedReady ? 'material_asset_seed_ready' : 'material_asset_seed_invalid',
    seedPath,
    seedExists: true,
    materialAssetSeedReady,
    productionManifest: false,
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    assetSeedCount: Array.isArray(manifest.assetSeeds) ? manifest.assetSeeds.length : 0,
    quarantineCount: Array.isArray(manifest.quarantine) ? manifest.quarantine.length : 0,
    contractAssertionCount: Array.isArray(manifest.contractAssertions) ? manifest.contractAssertions.length : 0,
    coveredClasses: Array.isArray(manifest.assetSeeds)
      ? Array.from(new Set(manifest.assetSeeds.map((asset) => asset.class))).filter(Boolean)
      : [],
    coveredSurfaces: Array.isArray(manifest.assetSeeds)
      ? Array.from(new Set(manifest.assetSeeds.flatMap((asset) => asset.allowedSurfaces || []))).filter(Boolean)
      : [],
    packageBudget: manifest.packageBudget || null,
    missingRequirements,
    nonPromotion: [
      'not production_asset_manifest',
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
    process.stdout.write(`materialAssetSeedReady=${report.materialAssetSeedReady}\n`)
    process.stdout.write(`productionManifest=${report.productionManifest}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-seed') && !report.materialAssetSeedReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

if (require.main === module) {
  main()
}

module.exports = {
  buildReport,
  validateSeed,
  REQUIRED_CLASSES,
  REQUIRED_SURFACES,
  EXIT_NOT_READY
}
