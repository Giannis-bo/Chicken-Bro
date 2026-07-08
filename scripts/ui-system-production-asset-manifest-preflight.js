#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_MANIFEST_PATH = 'artifacts/ui-system-rebuild/runtime/production-asset-manifest.json'
const ALLOWED_CLASSES = ['panel', 'border', 'texture', 'socket', 'state-base', 'state-atomic', 'decorative']
const SMALL_CLASSES = new Set(['socket', 'state-base', 'state-atomic'])
const MATERIAL_KB_MAX = 350
const SMALL_KB_MAX = 96
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
const ALLOWED_REAL_SOURCE_CLASSES = ['api', 'battlenet', 'websim', 'repo_verified', 'user_provided']
const FORBIDDEN_REAL_SOURCE_CLASSES = [
  'imagegen',
  'target_screenshot_crop',
  'random_cdn_without_mapping',
  'generated_product_glyph',
  'page_private_fallback_art'
]
const REQUIRED_REAL_ENTITY_TYPES = ['class', 'spec', 'hero', 'talent', 'spell', 'item', 'source', 'dungeon', 'raid', 'affix']
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

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(resolvePath(filePath), 'utf8'))
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function isPositiveNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0
}

function readPngDimensions(filePath) {
  const buffer = fs.readFileSync(resolvePath(filePath))
  if (buffer.length < 24 || buffer.toString('ascii', 1, 4) !== 'PNG') {
    return null
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  }
}

function fileSizeKb(filePath) {
  return fs.statSync(resolvePath(filePath)).size / 1024
}

function validateAsset(asset, index, missingRequirements) {
  const prefix = `assets[${index}]`
  if (!hasText(asset.id)) missingRequirements.push(`${prefix}.id`)
  if (!ALLOWED_CLASSES.includes(asset.class)) missingRequirements.push(`${prefix}.class`)
  if (!hasText(asset.owner)) missingRequirements.push(`${prefix}.owner`)
  if (asset.class && asset.owner && !ALLOWED_OWNERS_BY_CLASS[asset.class]?.includes(asset.owner)) {
    missingRequirements.push(`${prefix}.owner_allowed_for_class`)
  }
  if (!hasText(asset.path)) missingRequirements.push(`${prefix}.path`)
  if (!isPositiveNumber(asset.width)) missingRequirements.push(`${prefix}.width`)
  if (!isPositiveNumber(asset.height)) missingRequirements.push(`${prefix}.height`)
  if (!isPositiveNumber(asset.sizeKb)) missingRequirements.push(`${prefix}.sizeKb`)
  if (!ALLOWED_FIT_BY_CLASS[asset.class]?.includes(asset.fit)) missingRequirements.push(`${prefix}.fit_allowed_for_class`)
  if (!Array.isArray(asset.allowedSurfaces) || asset.allowedSurfaces.length === 0) {
    missingRequirements.push(`${prefix}.allowedSurfaces`)
  } else {
    for (const surface of asset.allowedSurfaces) {
      if (!REQUIRED_SURFACES.includes(surface)) missingRequirements.push(`${prefix}.allowedSurface:${surface}`)
    }
  }
  if (asset.sourceType !== 'imagegen_low_semantic' && asset.sourceType !== 'repo_material') {
    missingRequirements.push(`${prefix}.sourceType_low_semantic`)
  }
  for (const field of ['containsText', 'containsFakeChrome', 'containsRealWowObject', 'containsSourceLogo', 'containsBusinessConclusion']) {
    if (asset[field] !== false) missingRequirements.push(`${prefix}.${field}_false`)
  }
  if (asset.path && FORBIDDEN_PATH_PATTERNS.some((pattern) => pattern.test(asset.path))) {
    missingRequirements.push(`${prefix}.path_not_quarantine_or_reference`)
  }
  const budget = SMALL_CLASSES.has(asset.class) ? SMALL_KB_MAX : MATERIAL_KB_MAX
  if (isPositiveNumber(asset.sizeKb) && asset.sizeKb > budget) {
    missingRequirements.push(`${prefix}.size_budget`)
  }
  if (asset.path && exists(asset.path)) {
    const actualSize = fileSizeKb(asset.path)
    if (isPositiveNumber(asset.sizeKb) && Math.abs(actualSize - asset.sizeKb) > 1) {
      missingRequirements.push(`${prefix}.declared_size_matches_file`)
    }
    const dimensions = readPngDimensions(asset.path)
    if (dimensions && (dimensions.width !== asset.width || dimensions.height !== asset.height)) {
      missingRequirements.push(`${prefix}.declared_dimensions_match_file`)
    }
  } else {
    missingRequirements.push(`${prefix}.file_exists`)
  }
}

function validateRealSource(entry, index, missingRequirements) {
  const prefix = `realObjectSourceMap[${index}]`
  if (!hasText(entry.entityType)) missingRequirements.push(`${prefix}.entityType`)
  if (entry.entityType && !REQUIRED_REAL_ENTITY_TYPES.includes(entry.entityType)) {
    missingRequirements.push(`${prefix}.entityType_allowed`)
  }
  if (!hasText(entry.sourceClass)) missingRequirements.push(`${prefix}.sourceClass`)
  if (FORBIDDEN_REAL_SOURCE_CLASSES.includes(entry.sourceClass)) {
    missingRequirements.push(`${prefix}.sourceClass_not_forbidden`)
  }
  if (entry.sourceClass && !ALLOWED_REAL_SOURCE_CLASSES.includes(entry.sourceClass)) {
    missingRequirements.push(`${prefix}.sourceClass_allowed`)
  }
  if (entry.owner !== 'GameObjectIcon') missingRequirements.push(`${prefix}.owner_GameObjectIcon`)
  if (!hasText(entry.requiredFields)) missingRequirements.push(`${prefix}.requiredFields`)
  if (!hasText(entry.fallback)) missingRequirements.push(`${prefix}.fallback`)
  if (!hasText(entry.status)) missingRequirements.push(`${prefix}.status`)
}

function validateQuarantine(entry, index, missingRequirements) {
  const prefix = `quarantine[${index}]`
  if (!hasText(entry.path)) missingRequirements.push(`${prefix}.path`)
  if (!hasText(entry.reason)) missingRequirements.push(`${prefix}.reason`)
  if (!hasText(entry.class)) missingRequirements.push(`${prefix}.class`)
}

function validateManifest(manifest) {
  const missingRequirements = []
  if (manifest.status !== 'production_asset_manifest_ready') missingRequirements.push('status_production_asset_manifest_ready')
  if (manifest.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  if (!hasText(manifest.targetLockDecision)) missingRequirements.push('targetLockDecision')
  if (!hasText(manifest.activePermit)) missingRequirements.push('activePermit')
  if (!hasText(manifest.checkedAt)) missingRequirements.push('checkedAt')
  if (!manifest.packageBudget || typeof manifest.packageBudget !== 'object') {
    missingRequirements.push('packageBudget')
  } else {
    if (!isPositiveNumber(manifest.packageBudget.maxKb)) missingRequirements.push('packageBudget.maxKb')
    if (!isPositiveNumber(manifest.packageBudget.currentKb)) missingRequirements.push('packageBudget.currentKb')
    if (isPositiveNumber(manifest.packageBudget.currentKb) && isPositiveNumber(manifest.packageBudget.maxKb) && manifest.packageBudget.currentKb > manifest.packageBudget.maxKb) {
      missingRequirements.push('packageBudget.current_within_max')
    }
  }
  if (!Array.isArray(manifest.assets) || manifest.assets.length === 0) {
    missingRequirements.push('assets_non_empty')
  } else {
    manifest.assets.forEach((asset, index) => validateAsset(asset, index, missingRequirements))
  }
  if (!Array.isArray(manifest.realObjectSourceMap) || manifest.realObjectSourceMap.length === 0) {
    missingRequirements.push('realObjectSourceMap_non_empty')
  } else {
    manifest.realObjectSourceMap.forEach((entry, index) => validateRealSource(entry, index, missingRequirements))
  }
  if (!Array.isArray(manifest.quarantine) || manifest.quarantine.length === 0) {
    missingRequirements.push('quarantine_non_empty')
  } else {
    manifest.quarantine.forEach((entry, index) => validateQuarantine(entry, index, missingRequirements))
  }
  return missingRequirements
}

function buildReport(args) {
  const manifestPath = optionValue(args, '--manifest-file', DEFAULT_MANIFEST_PATH)
  if (!exists(manifestPath)) {
    return {
      status: 'production_asset_manifest_missing',
      manifestPath,
      manifestExists: false,
      productionManifestReady: false,
      missingRequirements: ['production_asset_manifest_file'],
      defaultManifestPath: DEFAULT_MANIFEST_PATH,
      allowedClasses: ALLOWED_CLASSES,
      requiredSurfaces: REQUIRED_SURFACES
    }
  }

  let manifest
  try {
    manifest = readJson(manifestPath)
  } catch (error) {
    return {
      status: 'production_asset_manifest_invalid_json',
      manifestPath,
      manifestExists: true,
      productionManifestReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateManifest(manifest)
  const productionManifestReady = missingRequirements.length === 0
  return {
    status: productionManifestReady ? 'production_asset_manifest_ready' : 'production_asset_manifest_invalid',
    manifestPath,
    manifestExists: true,
    productionManifestReady,
    assetCount: Array.isArray(manifest.assets) ? manifest.assets.length : 0,
    realSourceCount: Array.isArray(manifest.realObjectSourceMap) ? manifest.realObjectSourceMap.length : 0,
    quarantineCount: Array.isArray(manifest.quarantine) ? manifest.quarantine.length : 0,
    missingRequirements,
    allowedClasses: ALLOWED_CLASSES,
    allowedRealSourceClasses: ALLOWED_REAL_SOURCE_CLASSES,
    forbiddenRealSourceClasses: FORBIDDEN_REAL_SOURCE_CLASSES,
    nonPromotion: [
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
    process.stdout.write(`manifestPath=${report.manifestPath}\n`)
    process.stdout.write(`productionManifestReady=${report.productionManifestReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-production-manifest') && !report.productionManifestReady) {
    process.exitCode = 10
  }
}

main()
