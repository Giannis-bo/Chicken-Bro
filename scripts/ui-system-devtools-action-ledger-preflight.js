#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_LEDGER_PATH = 'artifacts/ui-system-rebuild/runtime/devtools-action-ledger.json'
const FORBIDDEN_ACTIONS = [
  'cli open',
  'cli close',
  'forced_restart',
  'force restart',
  'clear_cache',
  'clear cache',
  'switch_project',
  'switch project',
  'switch_appid',
  'switch appid',
  'delete_user_data_dir',
  'delete user data directory',
  'login',
  'logout',
  'screenshot_before_capture_safe',
  'navigation_before_capture_safe'
]

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  if (index === -1) {
    return fallback
  }
  return args[index + 1]
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

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function hasNonEmptyArray(value) {
  return Array.isArray(value) && value.length > 0
}

function stringContainsForbiddenAction(value) {
  if (typeof value !== 'string') {
    return false
  }
  const normalized = value.toLowerCase()
  return FORBIDDEN_ACTIONS.some((action) => normalized.includes(action))
}

function collectActionStrings(value, results = []) {
  if (!value) {
    return results
  }
  if (typeof value === 'string') {
    results.push(value)
    return results
  }
  if (Array.isArray(value)) {
    value.forEach((item) => collectActionStrings(item, results))
    return results
  }
  if (typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (['action', 'command', 'operation', 'name'].includes(key)) {
        collectActionStrings(child, results)
      }
    }
  }
  return results
}

function validateLedger(ledger) {
  const missingRequirements = []
  const forbiddenActionsDetected = []

  if (ledger.status !== 'devtools_action_ledger_capture_safe') {
    missingRequirements.push('status_devtools_action_ledger_capture_safe')
  }
  if (ledger.captureSafe !== true) {
    missingRequirements.push('captureSafe_true')
  }
  if (!ledger.devtools || typeof ledger.devtools !== 'object') {
    missingRequirements.push('devtools_object')
  } else {
    if (!hasText(ledger.devtools.appPath)) {
      missingRequirements.push('devtools.appPath')
    }
    if (!Number.isInteger(ledger.devtools.port) && !hasText(ledger.devtools.port)) {
      missingRequirements.push('devtools.port')
    }
    if (!hasText(ledger.devtools.appidState)) {
      missingRequirements.push('devtools.appidState')
    }
  }
  if (!ledger.forbiddenActionCheck || typeof ledger.forbiddenActionCheck !== 'object') {
    missingRequirements.push('forbiddenActionCheck_object')
  } else {
    if (ledger.forbiddenActionCheck.status !== 'pass') {
      missingRequirements.push('forbiddenActionCheck.status_pass')
    }
    if (!Array.isArray(ledger.forbiddenActionCheck.prohibitedActionsUsed)) {
      missingRequirements.push('forbiddenActionCheck.prohibitedActionsUsed_array')
    } else if (ledger.forbiddenActionCheck.prohibitedActionsUsed.length > 0) {
      forbiddenActionsDetected.push(...ledger.forbiddenActionCheck.prohibitedActionsUsed)
      missingRequirements.push('forbiddenActionCheck.prohibitedActionsUsed_empty')
    }
  }
  if (!hasNonEmptyArray(ledger.sceneList)) {
    missingRequirements.push('sceneList_non_empty')
  }
  if (!Array.isArray(ledger.failedScenes)) {
    missingRequirements.push('failedScenes_array')
  }
  if (!hasNonEmptyArray(ledger.screenshotPathList)) {
    missingRequirements.push('screenshotPathList_non_empty')
  }
  if (!hasNonEmptyArray(ledger.routeActionList)) {
    missingRequirements.push('routeActionList_non_empty')
  }
  if (!hasText(ledger.loginStateIncidentNote)) {
    missingRequirements.push('loginStateIncidentNote')
  }
  if (!hasText(ledger.checkedAt)) {
    missingRequirements.push('checkedAt')
  }
  if (!hasText(ledger.captureRunner)) {
    missingRequirements.push('captureRunner')
  }

  for (const action of collectActionStrings(ledger.routeActionList)) {
    if (stringContainsForbiddenAction(action)) {
      forbiddenActionsDetected.push(action)
    }
  }
  if (forbiddenActionsDetected.length > 0 && !missingRequirements.includes('forbidden_actions_detected')) {
    missingRequirements.push('forbidden_actions_detected')
  }

  return {
    valid: missingRequirements.length === 0,
    missingRequirements,
    forbiddenActionsDetected
  }
}

function buildReport(args) {
  const ledgerPath = optionValue(args, '--ledger-file', DEFAULT_LEDGER_PATH)
  if (!exists(ledgerPath)) {
    return {
      status: 'devtools_action_ledger_missing',
      ledgerPath,
      ledgerExists: false,
      runtimeCaptureEvidenceReady: false,
      missingRequirements: ['devtools_action_ledger_file'],
      forbiddenActions: FORBIDDEN_ACTIONS,
      requiredFields: [
        'status',
        'captureSafe',
        'devtools.appPath',
        'devtools.port',
        'devtools.appidState',
        'forbiddenActionCheck',
        'sceneList',
        'failedScenes',
        'screenshotPathList',
        'routeActionList',
        'loginStateIncidentNote',
        'checkedAt',
        'captureRunner'
      ]
    }
  }

  let ledger
  try {
    ledger = JSON.parse(read(ledgerPath))
  } catch (error) {
    return {
      status: 'devtools_action_ledger_invalid_json',
      ledgerPath,
      ledgerExists: true,
      runtimeCaptureEvidenceReady: false,
      missingRequirements: ['valid_json'],
      parseError: error.message,
      forbiddenActions: FORBIDDEN_ACTIONS
    }
  }

  const validation = validateLedger(ledger)
  return {
    status: validation.valid ? 'devtools_action_ledger_ready' : 'devtools_action_ledger_invalid',
    ledgerPath,
    ledgerExists: true,
    runtimeCaptureEvidenceReady: validation.valid,
    captureSafe: ledger.captureSafe === true,
    sceneCount: Array.isArray(ledger.sceneList) ? ledger.sceneList.length : 0,
    screenshotCount: Array.isArray(ledger.screenshotPathList) ? ledger.screenshotPathList.length : 0,
    failedSceneCount: Array.isArray(ledger.failedScenes) ? ledger.failedScenes.length : 0,
    routeActionCount: Array.isArray(ledger.routeActionList) ? ledger.routeActionList.length : 0,
    forbiddenActionsDetected: validation.forbiddenActionsDetected,
    missingRequirements: validation.missingRequirements,
    forbiddenActions: FORBIDDEN_ACTIONS,
    nonPromotion: [
      'not runtime_verified',
      'not final_accepted',
      'not visual acceptance'
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
    process.stdout.write(`ledgerPath=${report.ledgerPath}\n`)
    process.stdout.write(`runtimeCaptureEvidenceReady=${report.runtimeCaptureEvidenceReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-ledger') && !report.runtimeCaptureEvidenceReady) {
    process.exitCode = 9
  }
}

main()
