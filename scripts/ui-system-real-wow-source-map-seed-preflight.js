#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_SEED_PATH = 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json'
const EXIT_NOT_READY = 17

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

const PAYLOAD_SOURCE_CLASSES = new Set(['api', 'battlenet', 'websim'])
const REPO_SOURCE_CLASSES = new Set(['repo_verified', 'user_provided'])

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

function containsForbiddenPath(value) {
  const text = String(value || '')
  return /assets\/generated|pass36|pass37|target|reference|source\.(png|jpg|jpeg|webp)$/i.test(text)
}

function validateEntry(entry, index, missingRequirements) {
  const prefix = `sourceEntries[${index}]`

  if (!hasText(entry.id)) missingRequirements.push(`${prefix}.id`)
  if (!hasText(entry.entityType)) {
    missingRequirements.push(`${prefix}.entityType`)
  } else if (!REQUIRED_ENTITY_TYPES.includes(entry.entityType)) {
    missingRequirements.push(`${prefix}.entityType_allowed`)
  }

  if (!hasText(entry.sourceClass)) {
    missingRequirements.push(`${prefix}.sourceClass`)
  } else {
    if (!ALLOWED_SOURCE_CLASSES.includes(entry.sourceClass)) {
      missingRequirements.push(`${prefix}.sourceClass_allowed`)
    }
    if (FORBIDDEN_SOURCE_CLASSES.includes(entry.sourceClass)) {
      missingRequirements.push(`${prefix}.sourceClass_not_forbidden`)
    }
  }

  if (entry.owner !== 'GameObjectIcon') missingRequirements.push(`${prefix}.owner_GameObjectIcon`)
  if (entry.seedStatus !== 'source_map_seed_ready') missingRequirements.push(`${prefix}.seedStatus_source_map_seed_ready`)
  if (entry.runtimeSourceMapReady !== false) missingRequirements.push(`${prefix}.runtimeSourceMapReady_false`)
  if (entry.generatedByImagegen !== false) missingRequirements.push(`${prefix}.generatedByImagegen_false`)
  if (entry.containsGeneratedObject !== false) missingRequirements.push(`${prefix}.containsGeneratedObject_false`)

  if (!Array.isArray(entry.allowedSurfaces) || entry.allowedSurfaces.length === 0) {
    missingRequirements.push(`${prefix}.allowedSurfaces`)
  } else {
    for (const surface of entry.allowedSurfaces) {
      if (!REQUIRED_SURFACES.includes(surface)) {
        missingRequirements.push(`${prefix}.allowedSurface:${surface}`)
      }
    }
  }

  if (!hasTextArray(entry.sourceFiles)) {
    missingRequirements.push(`${prefix}.sourceFiles`)
  } else {
    for (const filePath of entry.sourceFiles) {
      if (!exists(filePath)) missingRequirements.push(`${prefix}.sourceFile_exists:${filePath}`)
      if (containsForbiddenPath(filePath)) missingRequirements.push(`${prefix}.sourceFile_not_generated_or_reference:${filePath}`)
    }
  }

  if (!hasTextArray(entry.evidenceFields)) missingRequirements.push(`${prefix}.evidenceFields`)
  if (!hasText(entry.fallback)) {
    missingRequirements.push(`${prefix}.fallback`)
  } else if (!ALLOWED_FALLBACKS.includes(entry.fallback)) {
    missingRequirements.push(`${prefix}.fallback_allowed`)
  }

  if (PAYLOAD_SOURCE_CLASSES.has(entry.sourceClass)) {
    if (!hasTextArray(entry.payloadFields)) missingRequirements.push(`${prefix}.payloadFields`)
    if (!hasText(entry.contractReference)) missingRequirements.push(`${prefix}.contractReference`)
  }

  if (REPO_SOURCE_CLASSES.has(entry.sourceClass)) {
    if (!hasText(entry.mappingExport) && !hasText(entry.verifiedBy)) {
      missingRequirements.push(`${prefix}.mappingExport_or_verifiedBy`)
    }
  }

  if (hasText(entry.assetPath)) {
    missingRequirements.push(`${prefix}.seed_must_not_bind_runtime_assetPath`)
  }
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
      if (!new RegExp(pattern).test(source)) {
        missingRequirements.push(`${prefix}.requiredPatterns[${patternIndex}]`)
      }
    })
  })
}

function validateSeed(manifest) {
  const missingRequirements = []

  if (manifest.status !== 'real_wow_source_map_seed_ready') missingRequirements.push('status_real_wow_source_map_seed_ready')
  if (manifest.schemaVersion !== 1) missingRequirements.push('schemaVersion_1')
  if (manifest.runtimeSourceMapReady !== false) missingRequirements.push('runtimeSourceMapReady_false')
  if (manifest.targetLocked !== false) missingRequirements.push('targetLocked_false')
  if (manifest.activeImplementationPermit !== false) missingRequirements.push('activeImplementationPermit_false')
  if (manifest.pageIntegration !== false) missingRequirements.push('pageIntegration_false')
  if (manifest.runtimeVerified !== false) missingRequirements.push('runtimeVerified_false')
  if (manifest.finalAccepted !== false) missingRequirements.push('finalAccepted_false')
  if (!hasText(manifest.checkedAt)) missingRequirements.push('checkedAt')

  if (!Array.isArray(manifest.sourceEntries) || manifest.sourceEntries.length === 0) {
    missingRequirements.push('sourceEntries_non_empty')
    return missingRequirements
  }

  manifest.sourceEntries.forEach((entry, index) => validateEntry(entry, index, missingRequirements))
  validateContractAssertions(manifest, missingRequirements)

  const coveredEntityTypes = new Set(manifest.sourceEntries.map((entry) => entry.entityType))
  for (const entityType of REQUIRED_ENTITY_TYPES) {
    if (!coveredEntityTypes.has(entityType)) missingRequirements.push(`entityType:${entityType}`)
  }

  const coveredSurfaces = new Set()
  for (const entry of manifest.sourceEntries) {
    for (const surface of entry.allowedSurfaces || []) coveredSurfaces.add(surface)
  }
  for (const surface of REQUIRED_SURFACES) {
    if (!coveredSurfaces.has(surface)) missingRequirements.push(`surface:${surface}`)
  }

  return missingRequirements
}

function buildReport(args) {
  const seedPath = optionValue(args, '--seed-file', DEFAULT_SEED_PATH)
  if (!exists(seedPath)) {
    return {
      status: 'real_wow_source_map_seed_missing',
      seedPath,
      seedExists: false,
      seedReady: false,
      runtimeSourceMapReady: false,
      missingRequirements: ['real_wow_source_map_seed_file'],
      defaultSeedPath: DEFAULT_SEED_PATH,
      requiredEntityTypes: REQUIRED_ENTITY_TYPES,
      requiredSurfaces: REQUIRED_SURFACES
    }
  }

  let manifest
  try {
    manifest = readJson(seedPath)
  } catch (error) {
    return {
      status: 'real_wow_source_map_seed_invalid_json',
      seedPath,
      seedExists: true,
      seedReady: false,
      runtimeSourceMapReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message
    }
  }

  const missingRequirements = validateSeed(manifest)
  const seedReady = missingRequirements.length === 0
  return {
    status: seedReady ? 'real_wow_source_map_seed_ready' : 'real_wow_source_map_seed_invalid',
    seedPath,
    seedExists: true,
    seedReady,
    runtimeSourceMapReady: false,
    sourceEntryCount: Array.isArray(manifest.sourceEntries) ? manifest.sourceEntries.length : 0,
    contractAssertionCount: Array.isArray(manifest.contractAssertions) ? manifest.contractAssertions.length : 0,
    coveredEntityTypes: Array.isArray(manifest.sourceEntries)
      ? Array.from(new Set(manifest.sourceEntries.map((entry) => entry.entityType))).filter(Boolean)
      : [],
    coveredSurfaces: Array.isArray(manifest.sourceEntries)
      ? Array.from(new Set(manifest.sourceEntries.flatMap((entry) => entry.allowedSurfaces || []))).filter(Boolean)
      : [],
    missingRequirements,
    requiredEntityTypes: REQUIRED_ENTITY_TYPES,
    requiredSurfaces: REQUIRED_SURFACES,
    allowedSourceClasses: ALLOWED_SOURCE_CLASSES,
    forbiddenSourceClasses: FORBIDDEN_SOURCE_CLASSES,
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
    process.stdout.write(`seedReady=${report.seedReady}\n`)
    process.stdout.write(`runtimeSourceMapReady=${report.runtimeSourceMapReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-seed') && !report.seedReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
