#!/usr/bin/env node

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_TARGET_DECISION_PATH = 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md'
const DEFAULT_ACTIVE_PERMIT_PATH = 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md'
const EXIT_BLOCKED = 16

const FROZEN_SURFACE_PREFIXES = [
  'pages/news/',
  'pages/builds/',
  'pages/simulator/',
  'pages/profile/',
  'pages/pve/'
]

const FROZEN_APP_FILES = new Set([
  'app.js',
  'app.json',
  'app.wxss',
  'project.config.json'
])

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function explicitChangedFiles(args) {
  const files = []
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === '--changed-file') {
      files.push(args[index + 1])
      index += 1
    }
  }
  return files.filter(Boolean)
}

function gitLines(args) {
  const result = spawnSync('git', args, { cwd: ROOT, encoding: 'utf8' })
  if (result.status !== 0) {
    throw new Error(result.stderr || `git ${args.join(' ')} failed`)
  }
  return result.stdout.split(/\r?\n/).filter(Boolean)
}

function readChangedFiles(args) {
  const explicit = explicitChangedFiles(args)
  if (explicit.length > 0) {
    return Array.from(new Set(explicit)).sort()
  }
  return Array.from(new Set([
    ...gitLines(['diff', '--name-only']),
    ...gitLines(['diff', '--cached', '--name-only']),
    ...gitLines(['ls-files', '--others', '--exclude-standard'])
  ])).sort()
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function exists(filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(filePath))
}

function isSurfaceFile(file) {
  return FROZEN_SURFACE_PREFIXES.some((prefix) => file.startsWith(prefix))
    && /\.(wxml|wxss|js|json)$/.test(file)
}

function isNavigationChromeFile(file) {
  return file.startsWith('components/navigation-bar/')
    && /\.(wxml|wxss|js|json)$/.test(file)
}

function isFrozenCoreFile(file) {
  return FROZEN_APP_FILES.has(file) || isSurfaceFile(file) || isNavigationChromeFile(file)
}

function classifyFrozenFile(file) {
  if (file === 'project.config.json') return 'devtools_project_config'
  if (FROZEN_APP_FILES.has(file)) return 'app_shell'
  if (isNavigationChromeFile(file)) return 'navigation_chrome'
  if (isSurfaceFile(file)) return 'core_surface_page'
  return 'not_frozen'
}

function groupFrozenFiles(files) {
  return files.reduce((groups, file) => {
    const category = classifyFrozenFile(file)
    if (category === 'not_frozen') return groups
    if (!groups[category]) groups[category] = []
    groups[category].push(file)
    return groups
  }, {})
}

function buildReport(args) {
  const targetDecisionPath = optionValue(args, '--target-decision-file', DEFAULT_TARGET_DECISION_PATH)
  const activePermitPath = optionValue(args, '--active-permit-file', DEFAULT_ACTIVE_PERMIT_PATH)
  const changedFiles = readChangedFiles(args)
  const frozenCoreFiles = changedFiles.filter(isFrozenCoreFile)
  const groupedFrozenFiles = groupFrozenFiles(frozenCoreFiles)
  const targetDecisionExists = exists(targetDecisionPath)
  const activePermitExists = exists(activePermitPath)
  const freezeSatisfied = frozenCoreFiles.length === 0 || (targetDecisionExists && activePermitExists)
  const blockedByMissingGate = frozenCoreFiles.length > 0 && (!targetDecisionExists || !activePermitExists)
  const missingRequirements = []

  if (!targetDecisionExists) missingRequirements.push('target_locked_decision_record')
  if (!activePermitExists) missingRequirements.push('active_implementation_permit')
  if (frozenCoreFiles.length > 0) missingRequirements.push('no_unpermitted_core_page_app_navigation_changes')

  return {
    status: freezeSatisfied ? 'core_page_freeze_clean' : 'core_page_freeze_blocked',
    freezeSatisfied,
    blockedByMissingGate,
    targetDecisionPath,
    targetDecisionExists,
    activePermitPath,
    activePermitExists,
    changedFileCount: changedFiles.length,
    frozenCoreFileCount: frozenCoreFiles.length,
    groupedFrozenFileCounts: Object.fromEntries(
      Object.entries(groupedFrozenFiles).map(([category, files]) => [category, files.length])
    ),
    frozenCoreFiles,
    groupedFrozenFiles,
    missingRequirements,
    requiredAction: blockedByMissingGate
      ? 'freeze or quarantine core page/app/navigation changes until target lock and active implementation permit exist'
      : 'continue evidence, owner component, asset manifest and preflight work without page-level patching',
    nonPromotion: [
      'not_target_locked',
      'not_active_implementation_permit',
      'not_page_integration_evidence',
      'not_runtime_verified',
      'not_final_accepted'
    ]
  }
}

function summarizeReport(report) {
  return {
    status: report.status,
    freezeSatisfied: report.freezeSatisfied,
    blockedByMissingGate: report.blockedByMissingGate,
    targetDecisionExists: report.targetDecisionExists,
    activePermitExists: report.activePermitExists,
    changedFileCount: report.changedFileCount,
    frozenCoreFileCount: report.frozenCoreFileCount,
    groupedFrozenFileCounts: report.groupedFrozenFileCounts,
    frozenCoreFiles: report.frozenCoreFiles,
    missingRequirements: report.missingRequirements,
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
    process.stdout.write(`freezeSatisfied=${report.freezeSatisfied}\n`)
    process.stdout.write(`frozenCoreFileCount=${report.frozenCoreFileCount}\n`)
    if (report.frozenCoreFiles.length > 0) {
      process.stdout.write(`frozenCoreFiles=${report.frozenCoreFiles.join(',')}\n`)
    }
  }

  if (flags.has('--require-frozen') && !report.freezeSatisfied) {
    process.exitCode = EXIT_BLOCKED
  }
}

main()
