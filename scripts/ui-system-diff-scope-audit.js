#!/usr/bin/env node

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const ACTIVATION_MANIFEST_PATH = 'artifacts/ui-system-rebuild/20260707-activation-guard/manifest.json'

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, relativePath), 'utf8'))
}

function exists(relativePath) {
  return fs.existsSync(path.join(ROOT, relativePath))
}

function gitLines(args) {
  const result = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(result.stderr || `git ${args.join(' ')} failed`)
  }
  return result.stdout.split(/\r?\n/).filter(Boolean)
}

function readChangedFiles(args) {
  const explicit = []
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--changed-file') {
      explicit.push(args[index + 1])
      index += 1
    }
  }
  if (explicit.length) {
    return explicit
  }

  return Array.from(new Set([
    ...gitLines(['diff', '--name-only']),
    ...gitLines(['diff', '--cached', '--name-only']),
    ...gitLines(['ls-files', '--others', '--exclude-standard'])
  ])).sort()
}

function buildActivationSnapshot() {
  const manifest = readJson(ACTIVATION_MANIFEST_PATH)
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

  return {
    activationAllowed: blockingReasons.length === 0,
    pageIntegrationAllowed: blockingReasons.length === 0,
    blockingReasons
  }
}

function classify(file) {
  if (/^pages\/.*\.(wxml|wxss|js|json)$/.test(file)) {
    return 'pageIntegration'
  }
  if (/^app\.(json|wxss|js)$/.test(file)) {
    return 'appShellIntegration'
  }
  if (/^components\/navigation-bar\//.test(file)) {
    return 'existingChromeIntegration'
  }
  if (file === 'project.config.json') {
    return 'devtoolsProjectConfig'
  }
  if (/^components\//.test(file)) {
    return 'componentOwnerWork'
  }
  if (/^assets\//.test(file)) {
    return 'assetWork'
  }
  if (/^(docs|artifacts|tests|scripts)\//.test(file)) {
    return 'evidenceOrTooling'
  }
  if (/^(server|websim)\//.test(file)) {
    return 'backendOrDataWork'
  }
  return 'other'
}

function groupByCategory(files) {
  return files.reduce((groups, file) => {
    const category = classify(file)
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(file)
    return groups
  }, {})
}

function buildReport(args) {
  const changedFiles = readChangedFiles(args)
  const activation = buildActivationSnapshot()
  const categories = groupByCategory(changedFiles)
  const blockedPageIntegrationFiles = [
    ...(categories.pageIntegration || []),
    ...(categories.appShellIntegration || []),
    ...(categories.existingChromeIntegration || [])
  ].sort()
  const devtoolsTouchRiskFiles = [...(categories.devtoolsProjectConfig || [])]
  const pageScopeBlocked = !activation.pageIntegrationAllowed && blockedPageIntegrationFiles.length > 0
  const devtoolsScopeRisk = !activation.pageIntegrationAllowed && devtoolsTouchRiskFiles.length > 0

  return {
    status: pageScopeBlocked ? 'diff_scope_blocked_page_integration_present' : 'diff_scope_clean_for_current_gate',
    sourceActivationManifest: ACTIVATION_MANIFEST_PATH,
    activationAllowed: activation.activationAllowed,
    pageIntegrationAllowed: activation.pageIntegrationAllowed,
    activationBlockingReasons: activation.blockingReasons,
    changedFileCount: changedFiles.length,
    categories,
    blockedPageIntegrationFiles,
    devtoolsTouchRiskFiles,
    pageScopeBlocked,
    devtoolsScopeRisk,
    requiredAction: pageScopeBlocked
      ? 'quarantine page/app/navigation changes until target lock and active implementation permit exist'
      : 'continue evidence/component/precheck work within activation guard'
  }
}

function summarizeReport(report) {
  return {
    status: report.status,
    sourceActivationManifest: report.sourceActivationManifest,
    activationAllowed: report.activationAllowed,
    pageIntegrationAllowed: report.pageIntegrationAllowed,
    activationBlockingReasons: report.activationBlockingReasons,
    changedFileCount: report.changedFileCount,
    categoryCounts: Object.fromEntries(
      Object.entries(report.categories).map(([category, files]) => [category, files.length])
    ),
    blockedPageIntegrationFileCount: report.blockedPageIntegrationFiles.length,
    blockedPageIntegrationFiles: report.blockedPageIntegrationFiles,
    devtoolsTouchRiskFiles: report.devtoolsTouchRiskFiles,
    pageScopeBlocked: report.pageScopeBlocked,
    devtoolsScopeRisk: report.devtoolsScopeRisk,
    requiredAction: report.requiredAction
  }
}

function main() {
  const args = process.argv.slice(2)
  const flags = new Set(args)
  const report = buildReport(args)

  if (flags.has('--summary-json')) {
    process.stdout.write(`${JSON.stringify(summarizeReport(report), null, 2)}\n`)
  } else if (flags.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`changedFileCount=${report.changedFileCount}\n`)
    process.stdout.write(`pageScopeBlocked=${report.pageScopeBlocked}\n`)
    if (report.blockedPageIntegrationFiles.length) {
      process.stdout.write(`blockedPageIntegrationFiles=${report.blockedPageIntegrationFiles.join(',')}\n`)
    }
  }

  if (flags.has('--require-no-page-integration') && report.pageScopeBlocked) {
    process.exitCode = 3
  }
}

main()
