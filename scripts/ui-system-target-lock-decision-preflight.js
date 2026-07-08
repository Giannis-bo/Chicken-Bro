#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_DECISION_PATH = 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md'
const DEFAULT_DECISION_BRIEF_PATH = 'artifacts/ui-system-rebuild/20260707-target-lock-decision-brief/manifest.json'
const DEFAULT_MATERIAL_SEED_PATH = 'artifacts/ui-system-rebuild/20260707-material-asset-seed/manifest.json'
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
const REQUIRED_MATERIAL_CLASSES = [
  'panel',
  'border',
  'texture',
  'socket',
  'state-base',
  'state-atomic',
  'decorative'
]
const REQUIRED_RUNTIME_GATES = [
  'production_asset_manifest_preflight',
  'real_wow_source_map_preflight',
  'page_adoption_preflight',
  'visual_acceptance_preflight',
  'route_smoke_execution_preflight',
  'devtools_action_ledger_preflight'
]
const REQUIRED_PATTERNS = [
  { id: 'status_target_locked', pattern: /^Status: `target_locked`$/m },
  { id: 'user_decision_source', pattern: /User Decision Source/ },
  { id: 'confirmed_target', pattern: /Confirmed Target/ },
  { id: 'decision_brief_boundary', pattern: /Decision Brief Boundary/ },
  { id: 'first_class_surfaces', pattern: /First-Class Surfaces/ },
  { id: 'foundation_owner_rules', pattern: /Foundation Owner Rules/ },
  { id: 'surface_owner_rules', pattern: /Surface Owner Rules/ },
  { id: 'asset_rules', pattern: /Asset Production And Quarantine Rules/ },
  { id: 'material_asset_seed_boundary', pattern: /Material Asset Seed Boundary/ },
  { id: 'real_wow_object_source_rules', pattern: /Real WoW Object Source Rules/ },
  { id: 'route_smoke_rules', pattern: /Route Smoke Rules/ },
  { id: 'implementation_permit_rule', pattern: /Implementation Permit Rule/ },
  { id: 'non_promotion_boundary', pattern: /Non-Promotion Boundary/ },
  { id: 'next_allowed_action', pattern: /Next Allowed Action/ },
  { id: 'recommended_target_name', pattern: /A-Cockpit \+ B-Ledger \+ C-Captain/ },
  { id: 'decision_brief_path', pattern: /artifacts\/ui-system-rebuild\/20260707-target-lock-decision-brief\/manifest\.json/ },
  { id: 'decision_brief_ready_status', pattern: /target_lock_decision_brief_ready|target_lock_decision_brief/ },
  { id: 'material_seed_path', pattern: /artifacts\/ui-system-rebuild\/20260707-material-asset-seed\/manifest\.json/ },
  { id: 'material_seed_ready_status', pattern: /material_asset_seed_ready/ },
  { id: 'material_seed_not_production', pattern: /productionManifest=false|production manifest.*false|not a production manifest/i },
  { id: 'material_seed_no_direct_use', pattern: /pageDirectUseAllowed=false|productionUseAllowed=false|no page direct use|no production direct use/i },
  { id: 'real_wow_not_imagegen', pattern: /Real WoW[\s\S]*imagegen/ },
  { id: 'exactly_one_active_permit', pattern: /exactly one|Exactly one/ },
  { id: 'runtime_evidence_boundary', pattern: /real WeChat mini-program screenshots[\s\S]*route smoke[\s\S]*DevTools action ledger/ }
]

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  if (index === -1) {
    return fallback
  }
  return args[index + 1]
}

function exists(relativePath) {
  const filePath = path.isAbsolute(relativePath) ? relativePath : path.join(ROOT, relativePath)
  return fs.existsSync(filePath)
}

function read(relativePath) {
  const filePath = path.isAbsolute(relativePath) ? relativePath : path.join(ROOT, relativePath)
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(relativePath) {
  return JSON.parse(read(relativePath))
}

function includesAll(actual, expected) {
  const actualSet = new Set(actual || [])
  return expected.filter((item) => !actualSet.has(item))
}

function validateDecision(source) {
  const missingRequirements = []
  for (const requirement of REQUIRED_PATTERNS) {
    if (!requirement.pattern.test(source)) {
      missingRequirements.push(requirement.id)
    }
  }
  for (const surface of REQUIRED_SURFACES) {
    if (!source.includes(surface)) {
      missingRequirements.push(`surface:${surface}`)
    }
  }
  return missingRequirements
}

function validateMaterialSeed(materialSeedPath) {
  const missingRequirements = []
  if (!exists(materialSeedPath)) {
    return ['material_seed_file']
  }

  let manifest
  try {
    manifest = readJson(materialSeedPath)
  } catch (error) {
    return ['material_seed_json_parse']
  }

  if (manifest.status !== 'material_asset_seed_ready') missingRequirements.push('material_seed_status')
  if (manifest.materialAssetSeedReady !== true) missingRequirements.push('material_seed_ready')
  if (manifest.productionManifest !== false) missingRequirements.push('material_seed_not_production')

  const seeds = manifest.assetSeeds || []
  const classes = Array.from(new Set(seeds.map((seed) => seed.class).filter(Boolean)))
  for (const materialClass of includesAll(classes, REQUIRED_MATERIAL_CLASSES)) {
    missingRequirements.push(`material_class:${materialClass}`)
  }

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
  for (const seed of unsafeSeeds) {
    missingRequirements.push(`unsafe_material_seed:${seed.id || 'unknown'}`)
  }

  const budget = manifest.packageBudget || {}
  if (!(budget.currentKb <= budget.maxKb && budget.maxKb <= 512)) {
    missingRequirements.push('material_seed_package_budget')
  }

  return missingRequirements
}

function validateDecisionBrief(decisionBriefPath) {
  const missingRequirements = []
  if (!exists(decisionBriefPath)) {
    return ['decision_brief_file']
  }

  let manifest
  try {
    manifest = readJson(decisionBriefPath)
  } catch (error) {
    return ['decision_brief_json_parse']
  }

  if (manifest.status !== 'target_lock_decision_brief') missingRequirements.push('decision_brief_status')
  if (manifest.recommendedTargetName !== 'A-Cockpit + B-Ledger + C-Captain') missingRequirements.push('decision_brief_target')
  if (manifest.recommendedFirstSurface !== 'news_list_detail') missingRequirements.push('decision_brief_first_surface')
  if (manifest.targetLocked !== false) missingRequirements.push('decision_brief_not_target_locked')
  if (manifest.activeImplementationPermit !== false) missingRequirements.push('decision_brief_not_active_permit')
  if (manifest.pageIntegration !== false) missingRequirements.push('decision_brief_not_page_integration')
  if (manifest.runtimeVerified !== false) missingRequirements.push('decision_brief_not_runtime_verified')
  if (manifest.finalAccepted !== false) missingRequirements.push('decision_brief_not_final_accepted')

  for (const gate of includesAll(manifest.requiredRuntimeGates, REQUIRED_RUNTIME_GATES)) {
    missingRequirements.push(`decision_brief_runtime_gate:${gate}`)
  }

  if (manifest.materialAssetSeed?.expectedStatus !== 'material_asset_seed_ready') {
    missingRequirements.push('decision_brief_material_seed')
  }
  if (manifest.realWowSourceMapSeed?.expectedStatus !== 'real_wow_source_map_seed_ready') {
    missingRequirements.push('decision_brief_source_map_seed')
  }

  return missingRequirements
}

function buildReport(args) {
  const candidatePath = optionValue(args, '--candidate-file', DEFAULT_DECISION_PATH)
  const decisionBriefPath = optionValue(args, '--decision-brief', DEFAULT_DECISION_BRIEF_PATH)
  const materialSeedPath = optionValue(args, '--material-asset-seed', DEFAULT_MATERIAL_SEED_PATH)
  if (!exists(candidatePath)) {
    return {
      status: 'target_lock_decision_missing',
      candidatePath,
      decisionBriefPath,
      materialSeedPath,
      decisionRecordExists: false,
      targetLocked: false,
      validDecisionRecord: false,
      missingRequirements: ['decision_record_file'],
      requiredSurfaces: REQUIRED_SURFACES,
      nextRequiredEvidence: 'explicit user target-lock confirmation or written modification'
    }
  }

  const source = read(candidatePath)
  const decisionMissingRequirements = validateDecision(source)
  const decisionBriefMissingRequirements = validateDecisionBrief(decisionBriefPath)
  const materialSeedMissingRequirements = validateMaterialSeed(materialSeedPath)
  const missingRequirements = [
    ...decisionMissingRequirements,
    ...decisionBriefMissingRequirements,
    ...materialSeedMissingRequirements
  ]
  const validDecisionRecord = missingRequirements.length === 0

  return {
    status: validDecisionRecord ? 'target_lock_decision_ready' : 'target_lock_decision_invalid',
    candidatePath,
    decisionBriefPath,
    materialSeedPath,
    decisionRecordExists: true,
    targetLocked: validDecisionRecord,
    validDecisionRecord,
    missingRequirements,
    requiredSurfaces: REQUIRED_SURFACES,
    nextRequiredEvidence: validDecisionRecord
      ? 'exactly one active implementation permit'
      : 'complete target_locked decision record'
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
    process.stdout.write(`candidatePath=${report.candidatePath}\n`)
    process.stdout.write(`validDecisionRecord=${report.validDecisionRecord}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-decision') && !report.validDecisionRecord) {
    process.exitCode = 4
  }
}

main()
