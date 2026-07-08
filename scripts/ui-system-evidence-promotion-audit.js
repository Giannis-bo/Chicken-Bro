#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const DEFAULT_SCAN_DIRS = [
  'docs/design',
  'docs/plans',
  'artifacts/ui-system-rebuild'
]
const FORBIDDEN_STATUSES = [
  'target_locked',
  'active_implementation_permit',
  'runtime_verified',
  'final_accepted'
]
const FORBIDDEN_TRUE_FIELDS = [
  'targetLocked',
  'activePermit',
  'activeImplementationPermit',
  'pageIntegration',
  'runtimeVerified',
  'finalAccepted',
  'goalComplete',
  'completionClaimAllowed',
  'runtimeVerifiedAllowed',
  'finalAcceptedAllowed',
  'implementationAllowed'
]
const ALLOWED_STATUS_FILES = {
  target_locked: new Set([
    'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md',
    'artifacts/ui-system-rebuild/20260707-target-locked-decision/manifest.json'
  ]),
  active_implementation_permit: new Set([
    'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md',
    'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json'
  ])
}
const ALLOWED_TRUE_FIELDS_BY_FILE = {
  'artifacts/ui-system-rebuild/20260707-activation-guard/manifest.json': new Set([
    'targetLocked',
    'activePermit'
  ]),
  'artifacts/ui-system-rebuild/20260707-delivery-convergence/manifest.json': new Set([
    'targetLocked',
    'activeImplementationPermit'
  ]),
  'artifacts/ui-system-rebuild/20260707-implementation-gate/manifest.json': new Set([
    'implementationAllowed'
  ]),
  'artifacts/ui-system-rebuild/20260707-news-list-detail-active-permit/manifest.json': new Set([
    'targetLocked',
    'activeImplementationPermit'
  ]),
  'artifacts/ui-system-rebuild/20260707-target-locked-decision/manifest.json': new Set([
    'targetLocked'
  ])
}

function resolvePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(ROOT, filePath)
}

function optionValues(args, name) {
  const values = []
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] === name && args[index + 1]) {
      values.push(args[index + 1])
      index += 1
    }
  }
  return values
}

function walk(directory, results = []) {
  const fullDirectory = resolvePath(directory)
  if (!fs.existsSync(fullDirectory)) {
    return results
  }
  for (const entry of fs.readdirSync(fullDirectory, { withFileTypes: true })) {
    const fullPath = path.join(fullDirectory, entry.name)
    if (entry.isDirectory()) {
      walk(fullPath, results)
      continue
    }
    if (entry.isFile() && (entry.name.endsWith('.md') || entry.name.endsWith('.json'))) {
      results.push(fullPath)
    }
  }
  return results
}

function relativePath(filePath) {
  return path.relative(ROOT, filePath) || filePath
}

function addMarkdownViolations(filePath, source, violations) {
  const relative = relativePath(filePath)
  const statusPattern = /^Status:\s*`([^`]+)`\s*$/gm
  let match
  while ((match = statusPattern.exec(source)) !== null) {
    const status = match[1]
    const allowedFiles = ALLOWED_STATUS_FILES[status]
    if (FORBIDDEN_STATUSES.includes(status) && !(allowedFiles && allowedFiles.has(relative))) {
      violations.push({
        file: relative,
        type: 'forbidden_status_line',
        value: status,
        detail: 'Status lines cannot claim promotion-only states while target lock, active permit and runtime evidence are missing.'
      })
    }
  }
}

function inspectJsonValue(filePath, value, pointer, violations) {
  if (!value || typeof value !== 'object') {
    return
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => inspectJsonValue(filePath, item, `${pointer}/${index}`, violations))
    return
  }
  const relative = relativePath(filePath)
  for (const [key, child] of Object.entries(value)) {
    const childPointer = `${pointer}/${key}`
    const allowedStatusFiles = ALLOWED_STATUS_FILES[child]
    if (key === 'status' && FORBIDDEN_STATUSES.includes(child) && !(allowedStatusFiles && allowedStatusFiles.has(relative))) {
      violations.push({
        file: relative,
        type: 'forbidden_manifest_status',
        field: childPointer,
        value: child,
        detail: 'Manifest status cannot claim promotion-only states while target lock, active permit and runtime evidence are missing.'
      })
    }
    const allowedTrueFields = ALLOWED_TRUE_FIELDS_BY_FILE[relative]
    if (FORBIDDEN_TRUE_FIELDS.includes(key) && child === true && !(allowedTrueFields && allowedTrueFields.has(key))) {
      violations.push({
        file: relative,
        type: 'forbidden_manifest_true_field',
        field: childPointer,
        value: true,
        detail: 'Promotion gate booleans must remain false until their required evidence exists.'
      })
    }
    inspectJsonValue(filePath, child, childPointer, violations)
  }
}

function addJsonViolations(filePath, source, violations) {
  try {
    inspectJsonValue(filePath, JSON.parse(source), '', violations)
  } catch (error) {
    violations.push({
      file: relativePath(filePath),
      type: 'json_parse_error',
      detail: error.message
    })
  }
}

function buildReport(args) {
  const scanDirs = optionValues(args, '--scan-dir')
  const directories = scanDirs.length ? scanDirs : DEFAULT_SCAN_DIRS
  const files = Array.from(new Set(directories.flatMap((directory) => walk(directory))))
    .sort((left, right) => relativePath(left).localeCompare(relativePath(right)))
  const violations = []

  for (const filePath of files) {
    const source = fs.readFileSync(filePath, 'utf8')
    if (filePath.endsWith('.md')) {
      addMarkdownViolations(filePath, source, violations)
    } else if (filePath.endsWith('.json')) {
      addJsonViolations(filePath, source, violations)
    }
  }

  return {
    status: violations.length
      ? 'ui_system_evidence_promotion_violation'
      : 'ui_system_evidence_promotion_clean',
    promotionAllowed: false,
    scannedFileCount: files.length,
    scanDirs: directories,
    forbiddenStatuses: FORBIDDEN_STATUSES,
    forbiddenTrueFields: FORBIDDEN_TRUE_FIELDS,
    allowedStatusFiles: Object.fromEntries(
      Object.entries(ALLOWED_STATUS_FILES).map(([status, files]) => [status, Array.from(files)])
    ),
    allowedTrueFieldsByFile: Object.fromEntries(
      Object.entries(ALLOWED_TRUE_FIELDS_BY_FILE).map(([file, fields]) => [file, Array.from(fields)])
    ),
    violationCount: violations.length,
    violations,
    nextAllowedPromotion: 'only after target lock, active permit, permitted page integration, real mini-program screenshots, crops, overlay, red-zone, scorecard, route smoke and DevTools ledger exist'
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
    process.stdout.write(`promotionAllowed=${report.promotionAllowed}\n`)
    process.stdout.write(`scannedFileCount=${report.scannedFileCount}\n`)
    process.stdout.write(`violationCount=${report.violationCount}\n`)
  }

  if (flags.has('--require-clean') && report.violations.length > 0) {
    process.exitCode = 8
  }
}

main()
