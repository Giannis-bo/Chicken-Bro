#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const MANIFEST_PATH = 'artifacts/ui-system-rebuild/20260707-activation-guard/manifest.json'

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'))
}

function exists(relativePath) {
  return fs.existsSync(path.join(ROOT, relativePath))
}

function buildReport() {
  const manifest = readJson(MANIFEST_PATH)
  const targetLockedDecisionRecordExists = exists(manifest.targetLockedDecisionRecordPath)
  const firstActivePermitExists = exists(manifest.firstActivePermitPath)
  const blockingReasons = []

  if (!targetLockedDecisionRecordExists) {
    blockingReasons.push('missing_target_locked_decision_record')
  }
  if (!firstActivePermitExists) {
    blockingReasons.push('missing_active_implementation_permit')
  }
  if (!targetLockedDecisionRecordExists) {
    blockingReasons.push('continuation_turn_is_not_confirmation')
  }

  const activationAllowed = blockingReasons.length === 0

  return {
    status: activationAllowed ? 'activation_preflight_passed' : 'activation_preflight_blocked',
    sourceManifest: MANIFEST_PATH,
    activationAllowed,
    pageIntegrationAllowed: activationAllowed,
    targetLockedDecisionRecordPath: manifest.targetLockedDecisionRecordPath,
    targetLockedDecisionRecordExists,
    firstActivePermitPath: manifest.firstActivePermitPath,
    firstActivePermitExists,
    blockingReasons,
    allowedWhileBlocked: manifest.allowedWhileBlocked || [],
    forbiddenWhileBlocked: manifest.forbiddenWhileBlocked || [],
    nextValidTransitions: manifest.nextValidTransitions || []
  }
}

function main() {
  const args = new Set(process.argv.slice(2))
  const requireActivation = args.has('--require-activation')
  const json = args.has('--json')
  const report = buildReport()

  if (json) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`activationAllowed=${report.activationAllowed}\n`)
    process.stdout.write(`pageIntegrationAllowed=${report.pageIntegrationAllowed}\n`)
    if (report.blockingReasons.length) {
      process.stdout.write(`blockingReasons=${report.blockingReasons.join(',')}\n`)
    }
  }

  if (requireActivation && !report.activationAllowed) {
    process.exitCode = 2
  }
}

main()
