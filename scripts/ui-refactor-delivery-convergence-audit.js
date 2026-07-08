#!/usr/bin/env node

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_NOT_READY = 20

const PATHS = {
  deliveryManifest: 'artifacts/ui-system-rebuild/20260707-delivery-convergence/manifest.json',
  backlogManifest: 'artifacts/ui-system-rebuild/20260707-delivery-backlog/manifest.json',
  routePlanManifest: 'artifacts/ui-system-rebuild/20260707-news-list-detail-route-smoke-plan/manifest.json',
  runtimeStatusManifest: 'artifacts/ui-system-rebuild/20260707-news-list-detail-runtime-verification-status/manifest.json',
  activePermitManifest: 'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json'
}

const REQUIRED_SURFACE = 'news_list_detail'
const REQUIRED_TARGET = 'A-Cockpit + B-Ledger + C-Captain'
const REQUIRED_ROUTE_SCENES = [
  'news_list_metric_updates',
  'news_list_loading',
  'news_list_empty',
  'news_list_fallback',
  'news_list_open_detail',
  'news_detail_first',
  'news_detail_missing_id',
  'news_detail_not_found',
  'news_detail_fallback',
  'news_detail_copy_source',
  'news_detail_back_to_list'
]
const ALLOWED_BACKLOG_CLASSES = new Set([
  'next_permit_candidate',
  'risk_requires_design_lock',
  'blocked_by_runtime_verification',
  'backlog'
])

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(root, filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(root, filePath)
}

function exists(root, filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(root, filePath))
}

function readJson(root, filePath, missingRequirements) {
  if (!exists(root, filePath)) {
    missingRequirements.push(`${filePath}:exists`)
    return null
  }
  try {
    return JSON.parse(fs.readFileSync(resolvePath(root, filePath), 'utf8'))
  } catch (error) {
    missingRequirements.push(`${filePath}:parseable_json`)
    return null
  }
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function runJsonCommand(command) {
  const result = spawnSync(process.execPath, command, {
    cwd: ROOT,
    encoding: 'utf8'
  })
  let report
  try {
    report = JSON.parse(result.stdout)
  } catch (error) {
    report = {
      status: 'json_parse_error',
      parseError: error.message,
      rawStdout: result.stdout
    }
  }
  return {
    command: `node ${command.join(' ')}`,
    exitCode: result.status,
    status: report.status || 'unknown',
    stderr: result.stderr,
    report
  }
}

function requireEqual(missingRequirements, label, actual, expected) {
  if (actual !== expected) missingRequirements.push(`${label}:${expected}`)
}

function requireArrayIncludes(missingRequirements, label, actual, required) {
  if (!Array.isArray(actual)) {
    missingRequirements.push(`${label}:array`)
    return
  }
  for (const item of required) {
    if (!actual.includes(item)) missingRequirements.push(`${label}:missing:${item}`)
  }
}

function validateDeliveryManifest(manifest, missingRequirements) {
  if (!manifest) return
  requireEqual(missingRequirements, 'delivery.status', manifest.status, 'delivery_convergence_implemented_runtime_blocked')
  requireEqual(missingRequirements, 'delivery.recommendedTarget', manifest.recommendedTarget, REQUIRED_TARGET)
  requireEqual(missingRequirements, 'delivery.recommendedSingleSurface', manifest.recommendedSingleSurface, REQUIRED_SURFACE)
  requireEqual(missingRequirements, 'delivery.originMainFetched', manifest.originMainFetched, true)
  requireEqual(missingRequirements, 'delivery.fastForwardBlockedByDirtyOverlap', manifest.fastForwardBlockedByDirtyOverlap, true)
  requireArrayIncludes(missingRequirements, 'delivery.requiredCommands', manifest.requiredCommands, [
    'node scripts/ui-system-refactor-course-correction-preflight.js --require-ready --json',
    'node scripts/ui-system-implementation-gate.js --require-implementation --json'
  ])
  requireArrayIncludes(missingRequirements, 'delivery.implemented', manifest.implemented, [
    'explicit_target_lock_confirmation',
    'explicit_single_surface_confirmation',
    'permission_for_app_json_native_tabbar_icons_and_assets_tabbar',
    'native_tabbar_iconPath_and_selectedIconPath_for_all_tabs',
    'one_surface_AppShell_PageFrame_owner_component_adoption',
    'selected_surface_route_smoke_and_visual_evidence_plan'
  ])
  if (!manifest.nonPromotion || manifest.nonPromotion.runtimeVerified !== false || manifest.nonPromotion.finalAccepted !== false) {
    missingRequirements.push('delivery.nonPromotion.runtime_and_final_false')
  }
  if (!manifest.runtimeVerification || manifest.runtimeVerification.captureSafe !== false) {
    missingRequirements.push('delivery.runtimeVerification.captureSafe_false')
  }
}

function validateActivePermit(manifest, missingRequirements) {
  if (!manifest) return
  requireEqual(missingRequirements, 'activePermit.status', manifest.status, 'active_implementation_permit')
  requireEqual(missingRequirements, 'activePermit.surface', manifest.surface, REQUIRED_SURFACE)
  requireEqual(missingRequirements, 'activePermit.confirmedTarget', manifest.confirmedTarget, REQUIRED_TARGET)
  requireArrayIncludes(missingRequirements, 'activePermit.allowedPages', manifest.allowedPages, [
    'pages/news/list',
    'pages/news/detail'
  ])
  requireEqual(missingRequirements, 'activePermit.nativeTabBarIconException', manifest.nativeTabBarIconException, true)
  requireEqual(missingRequirements, 'activePermit.runtimeVerified', manifest.runtimeVerified, false)
  requireEqual(missingRequirements, 'activePermit.finalAccepted', manifest.finalAccepted, false)
}

function validateBacklog(manifest, missingRequirements) {
  if (!manifest) return
  requireEqual(missingRequirements, 'backlog.status', manifest.status, 'delivery_backlog_defined')
  requireEqual(missingRequirements, 'backlog.activeSurface', manifest.activeSurface, REQUIRED_SURFACE)
  if (!Array.isArray(manifest.remainingSurfaces) || manifest.remainingSurfaces.length === 0) {
    missingRequirements.push('backlog.remainingSurfaces_non_empty')
    return
  }
  for (const item of manifest.remainingSurfaces) {
    if (!hasText(item.surface)) missingRequirements.push('backlog.remainingSurfaces.surface')
    if (!ALLOWED_BACKLOG_CLASSES.has(item.classification)) {
      missingRequirements.push(`backlog.remainingSurfaces.classification:${item.surface || 'unknown'}`)
    }
    if (item.surface === REQUIRED_SURFACE) missingRequirements.push('backlog.must_not_include_active_surface')
  }
}

function validateRoutePlan(manifest, missingRequirements) {
  if (!manifest) return
  requireEqual(missingRequirements, 'routePlan.status', manifest.status, 'route_smoke_plan_ready')
  requireEqual(missingRequirements, 'routePlan.surface', manifest.surface, REQUIRED_SURFACE)
  requireArrayIncludes(missingRequirements, 'routePlan.sceneIds', manifest.sceneIds, REQUIRED_ROUTE_SCENES)
  requireEqual(missingRequirements, 'routePlan.pageAdoptionReady', manifest.pageAdoptionReady, true)
  requireEqual(missingRequirements, 'routePlan.runtimeScreenshotsCaptured', manifest.runtimeScreenshotsCaptured, false)
  requireEqual(missingRequirements, 'routePlan.runtimeVerified', manifest.runtimeVerified, false)
  requireEqual(missingRequirements, 'routePlan.finalAccepted', manifest.finalAccepted, false)
}

function validateRuntimeStatus(root, manifest, missingRequirements) {
  if (!manifest) return 'missing'
  requireEqual(missingRequirements, 'runtime.status', manifest.status, 'runtime_verification_blocked')
  requireEqual(missingRequirements, 'runtime.surface', manifest.surface, REQUIRED_SURFACE)
  requireEqual(missingRequirements, 'runtime.pageAdoptionReady', manifest.pageAdoptionReady, true)
  requireEqual(missingRequirements, 'runtime.staticGateReady', manifest.staticGateReady, true)
  requireEqual(missingRequirements, 'runtime.captureSafe', manifest.captureSafe, false)
  requireEqual(missingRequirements, 'runtime.blocker', manifest.blocker, 'missing_miniprogram_automator_runtime_endpoint')
  requireEqual(missingRequirements, 'runtime.screenshotsCaptured', manifest.screenshotsCaptured, false)
  requireEqual(missingRequirements, 'runtime.routeSmokeExecuted', manifest.routeSmokeExecuted, false)
  requireEqual(missingRequirements, 'runtime.runtimeVerified', manifest.runtimeVerified, false)
  requireEqual(missingRequirements, 'runtime.finalAccepted', manifest.finalAccepted, false)

  const health = manifest.devtoolsHealthCheck || {}
  if (!hasText(health.path) || !exists(root, health.path)) {
    missingRequirements.push('runtime.devtoolsHealthCheck.path_exists')
  } else {
    const healthReport = readJson(root, health.path, missingRequirements)
    if (healthReport) {
      if (!healthReport.safety || healthReport.safety.loginAffectingProbeUsed !== false) {
        missingRequirements.push('runtime.health.loginAffectingProbeUsed_false')
      }
      if (!healthReport.safety || healthReport.safety.screenshotProbeUsed !== false) {
        missingRequirements.push('runtime.health.screenshotProbeUsed_false')
      }
      if (!healthReport.safety || healthReport.safety.runtimeProbeUsed !== false) {
        missingRequirements.push('runtime.health.runtimeProbeUsed_false')
      }
      if (!healthReport.summary || healthReport.summary.captureSafe !== false) {
        missingRequirements.push('runtime.health.captureSafe_false')
      }
      if (!healthReport.summary || healthReport.summary.healthCategory !== 'candidate_ports_not_miniprogram_automator') {
        missingRequirements.push('runtime.health.healthCategory_candidate_ports_not_miniprogram_automator')
      }
    }
  }
  if (!Array.isArray(health.forbiddenActionsUsed) || health.forbiddenActionsUsed.length !== 0) {
    missingRequirements.push('runtime.devtoolsHealthCheck.forbiddenActionsUsed_empty')
  }
  const preflight = manifest.runtimePreflightResults || {}
  if (!preflight.routeSmokeExecution || preflight.routeSmokeExecution.status !== 'route_smoke_execution_missing') {
    missingRequirements.push('runtime.preflight.routeSmokeExecution_missing_recorded')
  }
  if (!preflight.devtoolsActionLedger || preflight.devtoolsActionLedger.status !== 'devtools_action_ledger_missing') {
    missingRequirements.push('runtime.preflight.devtoolsActionLedger_missing_recorded')
  }
  if (!preflight.visualAcceptance || preflight.visualAcceptance.status !== 'visual_acceptance_scorecard_missing') {
    missingRequirements.push('runtime.preflight.visualAcceptance_missing_recorded')
  }
  return 'blocked_explained'
}

function validateCommandResults(results, missingRequirements) {
  const expected = {
    courseCorrection: 'ui_refactor_course_correction_ready',
    implementationGate: 'ui_system_implementation_gate_passed',
    pageAdoption: 'page_adoption_ready',
    evidencePromotion: 'ui_system_evidence_promotion_clean'
  }
  for (const [key, status] of Object.entries(expected)) {
    const result = results[key]
    if (!result || result.exitCode !== 0 || result.status !== status) {
      missingRequirements.push(`command.${key}:${status}`)
    }
  }
}

function buildReport(args) {
  const root = optionValue(args, '--root', ROOT)
  const missingRequirements = []
  const deliveryManifest = readJson(root, PATHS.deliveryManifest, missingRequirements)
  const activePermitManifest = readJson(root, PATHS.activePermitManifest, missingRequirements)
  const backlogManifest = readJson(root, PATHS.backlogManifest, missingRequirements)
  const routePlanManifest = readJson(root, PATHS.routePlanManifest, missingRequirements)
  const runtimeStatusManifest = readJson(root, PATHS.runtimeStatusManifest, missingRequirements)

  validateDeliveryManifest(deliveryManifest, missingRequirements)
  validateActivePermit(activePermitManifest, missingRequirements)
  validateBacklog(backlogManifest, missingRequirements)
  validateRoutePlan(routePlanManifest, missingRequirements)
  const runtimeEvidenceMode = validateRuntimeStatus(root, runtimeStatusManifest, missingRequirements)

  const commandResults = {
    courseCorrection: runJsonCommand(['scripts/ui-system-refactor-course-correction-preflight.js', '--require-ready', '--json']),
    implementationGate: runJsonCommand(['scripts/ui-system-implementation-gate.js', '--require-implementation', '--json']),
    pageAdoption: runJsonCommand(['scripts/ui-system-page-adoption-preflight.js', '--surface', REQUIRED_SURFACE, '--require-adoption', '--json']),
    evidencePromotion: runJsonCommand(['scripts/ui-system-evidence-promotion-audit.js', '--require-clean', '--json'])
  }
  validateCommandResults(commandResults, missingRequirements)

  const deliveryConvergenceReady = missingRequirements.length === 0
  return {
    status: deliveryConvergenceReady
      ? 'ui_refactor_delivery_convergence_ready'
      : 'ui_refactor_delivery_convergence_incomplete',
    deliveryConvergenceReady,
    surface: REQUIRED_SURFACE,
    target: REQUIRED_TARGET,
    runtimeEvidenceMode,
    missingRequirements,
    commandResults,
    handoffMeaning: deliveryConvergenceReady
      ? 'Narrowed delivery package is ready for handoff with runtime capture explicitly blocked and not promoted.'
      : 'Narrowed delivery package is not yet ready for handoff.',
    nonPromotion: {
      runtimeVerified: false,
      finalAccepted: false,
      allSurfaceAccepted: false
    }
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
    process.stdout.write(`deliveryConvergenceReady=${report.deliveryConvergenceReady}\n`)
    process.stdout.write(`runtimeEvidenceMode=${report.runtimeEvidenceMode}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }
  if (flags.has('--require-ready') && !report.deliveryConvergenceReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
