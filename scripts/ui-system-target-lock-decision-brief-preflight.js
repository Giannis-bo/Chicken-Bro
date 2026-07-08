#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_INVALID = 17

const DEFAULT_PATHS = {
  brief: 'docs/design/2026-07-07-wow-ui-system-target-lock-decision-brief.md',
  manifest: 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json',
  readinessReview: 'artifacts/ui-system-rebuild/20260707-target-lock-readiness-review/manifest.json',
  decisionRequest: 'artifacts/ui-system-rebuild/20260707-target-lock-decision-request/manifest.json',
  activationPacket: 'artifacts/ui-system-rebuild/20260707-target-lock-decision-and-news-list-detail-activation-packet/manifest.json',
  materialSeed: 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json',
  sourceMapSeed: 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-seed/manifest.json',
  productionAssetTemplate: 'artifacts/ui-system-rebuild/20260707-production-asset-manifest-template/manifest.json',
  realSourceMapTemplate: 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-template/manifest.json',
  activePermitTemplate: 'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit-template/manifest.json'
}

const REQUIRED_SECTIONS = [
  'Codex Goal Context',
  'Recommended Target',
  'Decision Options',
  'First Surface',
  'Material Asset Boundary',
  'Production Asset Manifest Gate',
  'Real WoW Source Map Gate',
  'Page Integration Gate',
  'Runtime Evidence Gate',
  'Non-Promotion Boundary',
  'Next Required Evidence'
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

const REQUIRED_MATERIAL_CLASSES = [
  'panel',
  'border',
  'texture',
  'socket',
  'state-base',
  'state-atomic',
  'decorative'
]

const REQUIRED_BRIEF_PATTERNS = [
  { id: 'status_brief', pattern: /^Status: `target_lock_decision_brief`$/m },
  { id: 'recommended_target', pattern: /A-Cockpit \+ B-Ledger \+ C-Captain/ },
  { id: 'decision_option_confirm', pattern: /Confirm recommended target/ },
  { id: 'decision_option_modify', pattern: /Confirm with modifications/ },
  { id: 'decision_option_reject', pattern: /Reject or revise target/ },
  { id: 'first_surface_news_list_detail', pattern: /Recommended first active surface after target lock: `news_list_detail`/ },
  { id: 'material_seed_path', pattern: /artifacts\/ui-system-rebuild\/20260707-material-asset-seed\/manifest\.json/ },
  { id: 'material_seed_ready', pattern: /material_asset_seed_ready/ },
  { id: 'material_seed_flags', pattern: /productionManifest=false[\s\S]*pageDirectUseAllowed=false[\s\S]*productionUseAllowed=false/ },
  { id: 'production_asset_manifest_preflight', pattern: /ui-system-production-asset-manifest-preflight\.js --require-production-manifest --json/ },
  { id: 'real_wow_source_map_preflight', pattern: /ui-system-real-wow-source-map-preflight\.js --require-source-map --json/ },
  { id: 'page_adoption_preflight', pattern: /page adoption preflight/ },
  { id: 'runtime_evidence', pattern: /real WeChat mini-program screenshots[\s\S]*route smoke[\s\S]*DevTools action ledger/ },
  { id: 'non_promotion_target_lock', pattern: /cannot prove:[\s\S]*`target_locked`/ },
  { id: 'explicit_user_decision', pattern: /explicit user target-lock confirmation or written modification/ },
  { id: 'continuation_insufficient', pattern: /continuation turn/ }
]

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return fs.existsSync(resolvePath(filePath))
}

function read(filePath) {
  return fs.readFileSync(resolvePath(filePath), 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function includesAll(actual, expected) {
  const actualSet = new Set(actual || [])
  return expected.filter((item) => !actualSet.has(item))
}

function addCheck(checks, id, pass, detail = {}) {
  checks.push({ id, status: pass ? 'pass' : 'fail', ...detail })
}

function safeJson(checks, id, filePath) {
  if (!exists(filePath)) {
    addCheck(checks, `${id}_exists`, false, { path: filePath })
    return null
  }
  try {
    const data = readJson(filePath)
    addCheck(checks, `${id}_json_parse`, true, { path: filePath })
    return data
  } catch (error) {
    addCheck(checks, `${id}_json_parse`, false, { path: filePath, error: error.message })
    return null
  }
}

function falseOrMissing(value) {
  return value === false || value === undefined
}

function validateNonPromotion(checks, id, manifest) {
  if (!manifest) return
  const fields = [
    'targetLocked',
    'activePermit',
    'activeImplementationPermit',
    'pageIntegration',
    'pageIntegrationAllowed',
    'runtimeVerified',
    'finalAccepted',
    'implementationAllowed',
    'devtoolsTouched'
  ]
  const promoted = fields.filter((field) => !falseOrMissing(manifest[field]))
  addCheck(checks, `${id}_non_promotion`, promoted.length === 0, { promoted })
}

function validateBrief(checks, source) {
  for (const section of REQUIRED_SECTIONS) {
    addCheck(checks, `brief_section:${section}`, source.includes(`## ${section}`))
  }
  for (const requirement of REQUIRED_BRIEF_PATTERNS) {
    addCheck(checks, `brief_pattern:${requirement.id}`, requirement.pattern.test(source))
  }
  for (const materialClass of REQUIRED_MATERIAL_CLASSES) {
    addCheck(checks, `brief_material_class:${materialClass}`, source.includes(`\`${materialClass}\``))
  }
  for (const entityType of REQUIRED_ENTITY_TYPES) {
    addCheck(checks, `brief_entity_type:${entityType}`, source.includes(entityType))
  }
}

function validateMaterialSeed(checks, materialSeed) {
  if (!materialSeed) return
  const seeds = materialSeed.assetSeeds || []
  const materialClasses = Array.from(new Set(seeds.map((seed) => seed.class).filter(Boolean)))
  const missingClasses = includesAll(materialClasses, REQUIRED_MATERIAL_CLASSES)
  const unsafeSeeds = seeds.filter((seed) => (
    seed.containsText !== false ||
    seed.containsFakeChrome !== false ||
    seed.containsRealWowObject !== false ||
    seed.containsSourceLogo !== false ||
    seed.containsBusinessConclusion !== false ||
    seed.containsGeneratedObjectIcon !== false ||
    seed.pageDirectUseAllowed !== false ||
    seed.productionUseAllowed !== false ||
    seed.requiresRecutBeforeProduction !== true
  ))
  const budget = materialSeed.packageBudget || {}

  addCheck(checks, 'material_seed_status', materialSeed.status === 'material_asset_seed_ready', { actual: materialSeed.status })
  addCheck(checks, 'material_seed_ready', materialSeed.materialAssetSeedReady === true, { actual: materialSeed.materialAssetSeedReady })
  addCheck(checks, 'material_seed_not_production_manifest', materialSeed.productionManifest === false, { actual: materialSeed.productionManifest })
  addCheck(checks, 'material_seed_class_coverage', missingClasses.length === 0, { missingClasses })
  addCheck(checks, 'material_seed_semantic_safety', unsafeSeeds.length === 0, {
    unsafeSeedIds: unsafeSeeds.map((seed) => seed.id || 'unknown')
  })
  addCheck(checks, 'material_seed_package_budget', budget.currentKb <= budget.maxKb && budget.maxKb <= 512, { budget })
}

function validateSourceMapSeed(checks, sourceMapSeed) {
  if (!sourceMapSeed) return
  const entries = sourceMapSeed.sourceEntries || []
  const entityTypes = Array.from(new Set(entries.map((entry) => entry.entityType).filter(Boolean)))
  const missingEntityTypes = includesAll(entityTypes, REQUIRED_ENTITY_TYPES)
  const generatedEntries = entries.filter((entry) => (
    entry.generatedByImagegen !== false ||
    entry.containsGeneratedObject !== false ||
    entry.sourceClass === 'imagegen'
  ))

  addCheck(checks, 'source_map_seed_status', sourceMapSeed.status === 'real_wow_source_map_seed_ready', { actual: sourceMapSeed.status })
  addCheck(checks, 'source_map_seed_not_runtime', sourceMapSeed.runtimeSourceMapReady === false, {
    actual: sourceMapSeed.runtimeSourceMapReady
  })
  addCheck(checks, 'source_map_seed_entity_coverage', missingEntityTypes.length === 0, { missingEntityTypes })
  addCheck(checks, 'source_map_seed_no_imagegen_objects', generatedEntries.length === 0, {
    generatedEntryIds: generatedEntries.map((entry) => entry.id || 'unknown')
  })
}

function buildReport(args) {
  const paths = {
    ...DEFAULT_PATHS,
    brief: optionValue(args, '--brief-file', DEFAULT_PATHS.brief),
    manifest: optionValue(args, '--manifest-file', DEFAULT_PATHS.manifest),
    materialSeed: optionValue(args, '--material-asset-seed', DEFAULT_PATHS.materialSeed),
    sourceMapSeed: optionValue(args, '--source-map-seed', DEFAULT_PATHS.sourceMapSeed)
  }

  const checks = []
  for (const [id, filePath] of Object.entries(paths)) {
    addCheck(checks, `file:${id}`, exists(filePath), { path: filePath })
  }

  const briefSource = exists(paths.brief) ? read(paths.brief) : ''
  if (briefSource) validateBrief(checks, briefSource)

  const manifest = safeJson(checks, 'brief_manifest', paths.manifest)
  const readinessReview = safeJson(checks, 'readiness_review', paths.readinessReview)
  const decisionRequest = safeJson(checks, 'decision_request', paths.decisionRequest)
  const activationPacket = safeJson(checks, 'activation_packet', paths.activationPacket)
  const materialSeed = safeJson(checks, 'material_seed', paths.materialSeed)
  const sourceMapSeed = safeJson(checks, 'source_map_seed', paths.sourceMapSeed)
  const productionAssetTemplate = safeJson(checks, 'production_asset_template', paths.productionAssetTemplate)
  const realSourceMapTemplate = safeJson(checks, 'real_source_map_template', paths.realSourceMapTemplate)
  const activePermitTemplate = safeJson(checks, 'active_permit_template', paths.activePermitTemplate)

  for (const [id, data] of Object.entries({
    manifest,
    readinessReview,
    decisionRequest,
    activationPacket,
    materialSeed,
    sourceMapSeed,
    productionAssetTemplate,
    realSourceMapTemplate,
    activePermitTemplate
  })) {
    validateNonPromotion(checks, id, data)
  }

  if (manifest) {
    addCheck(checks, 'manifest_status', manifest.status === 'target_lock_decision_brief', { actual: manifest.status })
    addCheck(checks, 'manifest_recommended_target', manifest.recommendedTargetName === 'A-Cockpit + B-Ledger + C-Captain', {
      actual: manifest.recommendedTargetName
    })
    addCheck(checks, 'manifest_first_surface', manifest.recommendedFirstSurface === 'news_list_detail', {
      actual: manifest.recommendedFirstSurface
    })
    addCheck(checks, 'manifest_runtime_gates', includesAll(manifest.requiredRuntimeGates, [
      'production_asset_manifest_preflight',
      'real_wow_source_map_preflight',
      'page_adoption_preflight',
      'visual_acceptance_preflight',
      'route_smoke_execution_preflight',
      'devtools_action_ledger_preflight'
    ]).length === 0, {
      missingGates: includesAll(manifest.requiredRuntimeGates, [
        'production_asset_manifest_preflight',
        'real_wow_source_map_preflight',
        'page_adoption_preflight',
        'visual_acceptance_preflight',
        'route_smoke_execution_preflight',
        'devtools_action_ledger_preflight'
      ])
    })
  }

  if (readinessReview) {
    addCheck(checks, 'readiness_review_ready', readinessReview.decisionReadiness === 'ready_for_user_decision', {
      actual: readinessReview.decisionReadiness
    })
    addCheck(checks, 'readiness_review_target', readinessReview.recommendedTargetName === 'A-Cockpit + B-Ledger + C-Captain', {
      actual: readinessReview.recommendedTargetName
    })
  }

  if (decisionRequest) {
    addCheck(checks, 'decision_request_status', decisionRequest.status === 'target_lock_decision_request', {
      actual: decisionRequest.status
    })
    addCheck(checks, 'decision_request_explicit_user_decision', decisionRequest.requiresExplicitUserDecision === true, {
      actual: decisionRequest.requiresExplicitUserDecision
    })
    addCheck(checks, 'decision_request_three_options', (decisionRequest.decisionOptions || []).length === 3, {
      count: (decisionRequest.decisionOptions || []).length
    })
  }

  if (activationPacket) {
    addCheck(checks, 'activation_packet_status', activationPacket.status === 'activation_packet_draft', {
      actual: activationPacket.status
    })
    addCheck(checks, 'activation_packet_first_surface', activationPacket.plannedFirstActivePermit?.surface === 'news_list_detail', {
      actual: activationPacket.plannedFirstActivePermit?.surface
    })
  }

  validateMaterialSeed(checks, materialSeed)
  validateSourceMapSeed(checks, sourceMapSeed)

  if (productionAssetTemplate) {
    addCheck(checks, 'production_asset_template_status', productionAssetTemplate.status === 'production_asset_manifest_template_only', {
      actual: productionAssetTemplate.status
    })
    addCheck(checks, 'production_asset_template_missing_runtime', productionAssetTemplate.productionManifestReady === false, {
      actual: productionAssetTemplate.productionManifestReady
    })
  }

  if (realSourceMapTemplate) {
    addCheck(checks, 'real_source_map_template_status', realSourceMapTemplate.status === 'real_wow_source_map_template_only', {
      actual: realSourceMapTemplate.status
    })
    addCheck(checks, 'real_source_map_template_missing_runtime', realSourceMapTemplate.sourceMapReady === false, {
      actual: realSourceMapTemplate.sourceMapReady
    })
    addCheck(checks, 'real_source_map_template_entity_types', includesAll(realSourceMapTemplate.requiredEntityTypes, REQUIRED_ENTITY_TYPES).length === 0, {
      missingEntityTypes: includesAll(realSourceMapTemplate.requiredEntityTypes, REQUIRED_ENTITY_TYPES)
    })
  }

  if (activePermitTemplate) {
    addCheck(checks, 'active_permit_template_status', activePermitTemplate.status === 'active_implementation_permit_template_and_preflight', {
      actual: activePermitTemplate.status
    })
    addCheck(checks, 'active_permit_template_first_surface', activePermitTemplate.surface === 'news_list_detail', {
      actual: activePermitTemplate.surface
    })
    addCheck(checks, 'active_permit_template_runtime_gates', includesAll(activePermitTemplate.preIntegrationChecks, [
      'production_asset_manifest_preflight',
      'real_wow_source_map_preflight',
      'page_adoption_preflight'
    ]).length === 0, {
      missingGates: includesAll(activePermitTemplate.preIntegrationChecks, [
        'production_asset_manifest_preflight',
        'real_wow_source_map_preflight',
        'page_adoption_preflight'
      ])
    })
  }

  const failedChecks = checks.filter((check) => check.status === 'fail')
  const ready = failedChecks.length === 0

  return {
    status: ready ? 'target_lock_decision_brief_ready' : 'target_lock_decision_brief_invalid',
    readyForUserDecision: ready,
    targetLocked: false,
    activeImplementationPermit: false,
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    devtoolsTouched: false,
    recommendedTargetName: 'A-Cockpit + B-Ledger + C-Captain',
    recommendedFirstSurface: 'news_list_detail',
    paths,
    checkCount: checks.length,
    failedCheckCount: failedChecks.length,
    failedChecks,
    checks,
    nextRequiredEvidence: ready
      ? 'explicit user target-lock confirmation or written modification'
      : 'repair target-lock decision brief evidence before asking for decision'
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
    process.stdout.write(`readyForUserDecision=${report.readyForUserDecision}\n`)
    process.stdout.write(`failedCheckCount=${report.failedCheckCount}\n`)
  }

  if (flags.has('--require-ready') && !report.readyForUserDecision) {
    process.exitCode = EXIT_INVALID
  }
}

main()
