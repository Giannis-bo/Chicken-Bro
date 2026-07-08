#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_SOURCE_MAP_PATH = 'artifacts/ui-system-rebuild/runtime/real-wow-source-map.json'
const EXIT_NOT_READY = 15

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

const REQUIRED_ENTITY_TYPES = [
  'class',
  'spec',
  'hero',
  'talent',
  'spell',
  'item',
  'source',
  'dungeon',
  'raid',
  'affix'
]

const ALLOWED_SOURCE_CLASSES = [
  'api',
  'battlenet',
  'websim',
  'repo_verified',
  'user_provided'
]

const FORBIDDEN_SOURCE_CLASSES = [
  'imagegen',
  'target_screenshot_crop',
  'random_cdn_without_mapping',
  'generated_product_glyph',
  'page_private_fallback_art'
]

const ALLOWED_FALLBACKS = [
  'text_fallback',
  'localized_initials',
  'source_reference_row',
  'hidden_when_missing'
]

const FILE_BACKED_SOURCE_CLASSES = new Set(['repo_verified', 'user_provided'])
const PAYLOAD_SOURCE_CLASSES = new Set(['api', 'battlenet', 'websim'])

const FORBIDDEN_ASSET_PATH_PATTERNS = [
  /assets\/generated/i,
  /pass36/i,
  /pass37/i,
  /source\.(png|jpg|jpeg|webp)$/i,
  /reference\.(png|jpg|jpeg|webp)$/i,
  /target/i
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

function hasTextArray(value) {
  return Array.isArray(value) && value.length > 0 && value.every(hasText)
}

function validateEntry(entry, index, missingRequirements) {
  const prefix = `sourceMaps[${index}]`
  if (!hasText(entry.id)) missingRequirements.push(`${prefix}.id`)
  if (!hasText(entry.entityType)) missingRequirements.push(`${prefix}.entityType`)
  if (entry.entityType && !REQUIRED_ENTITY_TYPES.includes(entry.entityType)) {
    missingRequirements.push(`${prefix}.entityType_allowed`)
  }
  if (!hasText(entry.sourceClass)) missingRequirements.push(`${prefix}.sourceClass`)
  if (FORBIDDEN_SOURCE_CLASSES.includes(entry.sourceClass)) {
    missingRequirements.push(`${prefix}.sourceClass_not_forbidden`)
  }
  if (entry.sourceClass && !ALLOWED_SOURCE_CLASSES.includes(entry.sourceClass)) {
    missingRequirements.push(`${prefix}.sourceClass_allowed`)
  }
  if (entry.owner !== 'GameObjectIcon') {
    missingRequirements.push(`${prefix}.owner_GameObjectIcon`)
  }
  if (!Array.isArray(entry.allowedSurfaces) || entry.allowedSurfaces.length === 0) {
    missingRequirements.push(`${prefix}.allowedSurfaces`)
  } else {
    for (const surface of entry.allowedSurfaces) {
      if (!REQUIRED_SURFACES.includes(surface)) {
        missingRequirements.push(`${prefix}.allowedSurface:${surface}`)
      }
    }
  }
  if (!hasTextArray(entry.requiredFields)) {
    missingRequirements.push(`${prefix}.requiredFields`)
  }
  if (!hasText(entry.fallback)) {
    missingRequirements.push(`${prefix}.fallback`)
  } else if (!ALLOWED_FALLBACKS.includes(entry.fallback)) {
    missingRequirements.push(`${prefix}.fallback_allowed`)
  }
  if (entry.status !== 'source_map_ready') {
    missingRequirements.push(`${prefix}.status_source_map_ready`)
  }
  if (entry.generatedByImagegen !== false) {
    missingRequirements.push(`${prefix}.generatedByImagegen_false`)
  }
  if (entry.containsGeneratedObject !== false) {
    missingRequirements.push(`${prefix}.containsGeneratedObject_false`)
  }

  if (PAYLOAD_SOURCE_CLASSES.has(entry.sourceClass)) {
    if (!hasText(entry.payloadField)) {
      missingRequirements.push(`${prefix}.payloadField`)
    }
    if (!hasText(entry.contractReference)) {
      missingRequirements.push(`${prefix}.contractReference`)
    }
    if (hasText(entry.assetPath)) {
      missingRequirements.push(`${prefix}.payload_source_must_not_use_assetPath`)
    }
  }

  if (FILE_BACKED_SOURCE_CLASSES.has(entry.sourceClass)) {
    if (!hasText(entry.assetPath)) {
      missingRequirements.push(`${prefix}.assetPath`)
    } else {
      if (FORBIDDEN_ASSET_PATH_PATTERNS.some((pattern) => pattern.test(entry.assetPath))) {
        missingRequirements.push(`${prefix}.assetPath_not_generated_or_reference`)
      }
      if (!exists(entry.assetPath)) {
        missingRequirements.push(`${prefix}.assetPath_exists`)
      }
    }
    if (!hasText(entry.verifiedBy)) {
      missingRequirements.push(`${prefix}.verifiedBy`)
    }
  }
}

function validateSourceMap(manifest) {
  const missingRequirements = []
  if (manifest.status !== 'real_wow_source_map_ready') {
    missingRequirements.push('status_real_wow_source_map_ready')
  }
  if (manifest.schemaVersion !== 1) {
    missingRequirements.push('schemaVersion_1')
  }
  if (!hasText(manifest.targetLockDecision)) {
    missingRequirements.push('targetLockDecision')
  }
  if (!hasText(manifest.activePermit)) {
    missingRequirements.push('activePermit')
  }
  if (!hasText(manifest.checkedAt)) {
    missingRequirements.push('checkedAt')
  }
  if (!Array.isArray(manifest.sourceMaps) || manifest.sourceMaps.length === 0) {
    missingRequirements.push('sourceMaps_non_empty')
    return missingRequirements
  }

  manifest.sourceMaps.forEach((entry, index) => validateEntry(entry, index, missingRequirements))

  const coveredEntityTypes = new Set(manifest.sourceMaps.map((entry) => entry.entityType))
  for (const entityType of REQUIRED_ENTITY_TYPES) {
    if (!coveredEntityTypes.has(entityType)) {
      missingRequirements.push(`entityType:${entityType}`)
    }
  }

  const coveredSurfaces = new Set()
  for (const entry of manifest.sourceMaps) {
    for (const surface of entry.allowedSurfaces || []) {
      coveredSurfaces.add(surface)
    }
  }
  for (const surface of REQUIRED_SURFACES) {
    if (!coveredSurfaces.has(surface)) {
      missingRequirements.push(`surface:${surface}`)
    }
  }

  return missingRequirements
}

function buildReport(args) {
  const sourceMapPath = optionValue(args, '--source-map-file', DEFAULT_SOURCE_MAP_PATH)
  if (!exists(sourceMapPath)) {
    return {
      status: 'real_wow_source_map_missing',
      sourceMapPath,
      sourceMapExists: false,
      sourceMapReady: false,
      missingRequirements: ['real_wow_source_map_file'],
      defaultSourceMapPath: DEFAULT_SOURCE_MAP_PATH,
      requiredEntityTypes: REQUIRED_ENTITY_TYPES,
      requiredSurfaces: REQUIRED_SURFACES,
      allowedSourceClasses: ALLOWED_SOURCE_CLASSES,
      forbiddenSourceClasses: FORBIDDEN_SOURCE_CLASSES
    }
  }

  let manifest
  try {
    manifest = readJson(sourceMapPath)
  } catch (error) {
    return {
      status: 'real_wow_source_map_invalid_json',
      sourceMapPath,
      sourceMapExists: true,
      sourceMapReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateSourceMap(manifest)
  const sourceMapReady = missingRequirements.length === 0
  return {
    status: sourceMapReady ? 'real_wow_source_map_ready' : 'real_wow_source_map_invalid',
    sourceMapPath,
    sourceMapExists: true,
    sourceMapReady,
    sourceMapCount: Array.isArray(manifest.sourceMaps) ? manifest.sourceMaps.length : 0,
    coveredEntityTypes: Array.isArray(manifest.sourceMaps)
      ? Array.from(new Set(manifest.sourceMaps.map((entry) => entry.entityType))).filter(Boolean)
      : [],
    coveredSurfaces: Array.isArray(manifest.sourceMaps)
      ? Array.from(new Set(manifest.sourceMaps.flatMap((entry) => entry.allowedSurfaces || []))).filter(Boolean)
      : [],
    missingRequirements,
    requiredEntityTypes: REQUIRED_ENTITY_TYPES,
    requiredSurfaces: REQUIRED_SURFACES,
    allowedSourceClasses: ALLOWED_SOURCE_CLASSES,
    forbiddenSourceClasses: FORBIDDEN_SOURCE_CLASSES,
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
    process.stdout.write(`sourceMapReady=${report.sourceMapReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-source-map') && !report.sourceMapReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
