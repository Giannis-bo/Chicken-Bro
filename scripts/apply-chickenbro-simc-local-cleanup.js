#!/usr/bin/env node

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync, spawnSync } = require('node:child_process')

const { canonicalJson } = require('./build-chickenbro-simc-refactor-inventory')

const SHA256 = /^[0-9a-f]{64}$/
const COMMIT = /^[0-9a-f]{40}$/
const ALLOWED_DISPOSITIONS = new Set(['keep', 'migrate', 'delete', 'review'])
const REFERENCE_EXTENSIONS = [
  '', '.js', '.cjs', '.mjs', '.ts', '.tsx', '.json', '.py', '.md', '.scss', '.css',
  '/index.js', '/index.ts', '/index.tsx', '/__init__.py',
]

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

function computeInventorySha256(inventory) {
  if (!inventory || typeof inventory !== 'object' || Array.isArray(inventory)) {
    throw new Error('inventory must be an object')
  }
  const { inventorySha256: _declared, ...withoutIdentity } = inventory
  return sha256(canonicalJson(withoutIdentity))
}

function validateTarget(relativePath) {
  if (
    typeof relativePath !== 'string'
    || relativePath.length === 0
    || relativePath === '.'
    || relativePath === '..'
    || relativePath === '~'
    || relativePath.includes('$')
    || relativePath.includes('\\')
    || relativePath.endsWith('/')
    || /[*?\[\]{}]/.test(relativePath)
    || path.posix.isAbsolute(relativePath)
  ) {
    throw new Error(`cleanup target must be one exact file: ${relativePath}`)
  }
  const normalized = path.posix.normalize(relativePath)
  if (normalized !== relativePath || normalized.startsWith('../')) {
    throw new Error(`cleanup target must be one exact file: ${relativePath}`)
  }
  return normalized
}

function verifyHash(relativePath, bytes, expectedSha256) {
  if (!SHA256.test(String(expectedSha256 || ''))) {
    throw new Error(`invalid expected hash for ${relativePath}`)
  }
  const actual = sha256(bytes)
  if (actual !== expectedSha256) {
    throw new Error(`hash mismatch for ${relativePath}: ${actual}`)
  }
  return actual
}

function validateInventory(inventory) {
  if (!inventory || inventory.schemaVersion !== 1 || !Array.isArray(inventory.entries)) {
    throw new Error('invalid cleanup inventory')
  }
  if (!COMMIT.test(String(inventory.generatedFromCommit || ''))) {
    throw new Error('invalid inventory commit')
  }
  if (inventory.entryCount !== inventory.entries.length) {
    throw new Error('inventory identity mismatch: entry count')
  }
  if (!SHA256.test(String(inventory.sourceRulesSha256 || ''))) {
    throw new Error('inventory identity mismatch: source rules SHA-256')
  }
  if (inventory.excludedSelfPath) validateTarget(inventory.excludedSelfPath)
  const computed = computeInventorySha256(inventory)
  if (computed !== inventory.inventorySha256) {
    throw new Error('inventory identity mismatch: canonical SHA-256')
  }
  const paths = new Set()
  const dispositionCounts = {}
  const categoryCounts = {}
  for (const rawEntry of inventory.entries) {
    if (!rawEntry || typeof rawEntry !== 'object') {
      throw new Error('inventory contains a non-object entry')
    }
    const target = validateTarget(rawEntry.path)
    if (paths.has(target)) throw new Error(`inventory contains duplicate path: ${target}`)
    paths.add(target)
    if (!ALLOWED_DISPOSITIONS.has(rawEntry.disposition)) {
      throw new Error(`inventory contains invalid disposition for ${target}`)
    }
    if (typeof rawEntry.category !== 'string' || rawEntry.category.length === 0) {
      throw new Error(`inventory contains invalid category for ${target}`)
    }
    if (!SHA256.test(String(rawEntry.sha256 || ''))) {
      throw new Error(`inventory contains invalid file hash for ${target}`)
    }
    dispositionCounts[rawEntry.disposition] = (dispositionCounts[rawEntry.disposition] || 0) + 1
    categoryCounts[rawEntry.category] = (categoryCounts[rawEntry.category] || 0) + 1
  }
  if (canonicalJson(dispositionCounts) !== canonicalJson(inventory.dispositionCounts || {})) {
    throw new Error('inventory identity mismatch: disposition counts')
  }
  if (canonicalJson(categoryCounts) !== canonicalJson(inventory.categoryCounts || {})) {
    throw new Error('inventory identity mismatch: category counts')
  }
  if (inventory.unresolvedCount !== (dispositionCounts.review || 0)) {
    throw new Error('inventory identity mismatch: unresolved count')
  }
  return inventory
}

function isText(bytes) {
  const sample = bytes.subarray(0, Math.min(bytes.length, 8192))
  return !sample.includes(0)
}

function normalizeReference(sourcePath, rawReference) {
  if (typeof rawReference !== 'string') return []
  let value = rawReference.trim()
  if (!value || /^(?:https?:|data:|mailto:|#)/i.test(value)) return []
  value = value.split('#', 1)[0].split('?', 1)[0]
  if (!value || value.includes('\\') || value.includes('*') || value.includes('$')) return []
  if (value.startsWith('/')) value = value.slice(1)
  const base = value.startsWith('.')
    ? path.posix.normalize(path.posix.join(path.posix.dirname(sourcePath), value))
    : path.posix.normalize(value)
  if (!base || base === '.' || base === '..' || base.startsWith('../')) return []
  return REFERENCE_EXTENSIONS.map((extension) => `${base}${extension}`)
}

function extractReferenceCandidates(sourcePath, text) {
  const candidates = new Set()
  const quoted = /["'`]([^"'`\r\n]{1,512})["'`]/g
  const markdown = /\]\(([^)\s]+)(?:\s+["'][^"']*["'])?\)/g
  const moduleSpecifier = /(?:\bfrom\s+|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+|\bexport[^;\r\n]*?\sfrom\s+)["'`]([^"'`\r\n]{1,512})["'`]/g
  const pythonImport = /\b(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)/g
  const looksLikePath = (value) => {
    const normalized = String(value || '').trim().split('#', 1)[0].split('?', 1)[0]
    return normalized.startsWith('.')
      || normalized.startsWith('/')
      || normalized.includes('/')
      || /\.(?:c?js|mjs|tsx?|json|py|md|scss|css|html|sh|service|timer|nginx|sql|toml|ya?ml)$/i.test(normalized)
  }
  const addMatches = (expression, predicate = () => true) => {
    let match
    while ((match = expression.exec(text)) !== null) {
      if (!predicate(match[1])) continue
      for (const candidate of normalizeReference(sourcePath, match[1])) candidates.add(candidate)
    }
  }
  const lowerPath = sourcePath.toLowerCase()
  const extension = path.posix.extname(lowerPath)
  const isTestSource = /(?:^|\/)[^/]+\.(?:test|spec)\.[^.]+$/.test(lowerPath)
  const isConfigSource = /(?:^|\/)[^/]*(?:config|manifest|registry|owner-map|project-state)[^/]*\.(?:js|cjs|mjs|ts|tsx|json)$/.test(lowerPath)

  if (extension === '.md') {
    addMatches(markdown)
    return candidates
  }

  addMatches(moduleSpecifier)
  if (extension === '.json' || isConfigSource || (!isTestSource && [
    '.html', '.sh', '.service', '.timer', '.nginx', '.toml', '.yaml', '.yml',
  ].includes(extension))) {
    addMatches(quoted, looksLikePath)
  }

  let match
  while ((match = pythonImport.exec(text)) !== null) {
    const modulePath = match[1].replaceAll('.', '/')
    candidates.add(`${modulePath}.py`)
    candidates.add(`${modulePath}/__init__.py`)
  }
  return candidates
}

function findRetainedCallers(deletePaths, retainedEntries, repository) {
  const callers = new Map([...deletePaths].map((target) => [target, new Set()]))
  for (const entry of retainedEntries) {
    if (entry.matchedRule === 'rebuild-inventory-owner') continue
    if (
      entry.matchedRule === 'current-rebuild-release-packet'
      && entry.category === 'current-release-evidence'
    ) continue
    if (!repository.isRegularFile(entry.path)) continue
    const bytes = repository.readFile(entry.path)
    if (!isText(bytes)) continue
    const text = bytes.toString('utf8')
    const candidates = extractReferenceCandidates(entry.path, text)
    for (const target of candidates) {
      if (deletePaths.has(target)) callers.get(target).add(entry.path)
    }
  }
  return callers
}

function verifyCleanup(inventoryInput, repository) {
  const inventory = validateInventory(inventoryInput)
  if (!repository || typeof repository.listTrackedFiles !== 'function') {
    throw new Error('repository adapter is required')
  }
  const inventoryPaths = new Set(inventory.entries.map((entry) => entry.path))
  const excludedSelfPath = inventory.excludedSelfPath
    ? validateTarget(inventory.excludedSelfPath)
    : null
  const review = []
  const matchesInventoryBase = repository.headCommit === inventory.generatedFromCommit
    || (
      typeof repository.matchesInventoryBase === 'function'
      && repository.matchesInventoryBase(inventory.generatedFromCommit, excludedSelfPath)
    )
  if (!matchesInventoryBase) {
    review.push({
      path: excludedSelfPath || '(inventory)',
      reason: 'INVENTORY_BASE_COMMIT_DIFFERS_FROM_HEAD',
      expectedCommit: inventory.generatedFromCommit,
      actualCommit: repository.headCommit,
    })
  }
  for (const trackedPath of repository.listTrackedFiles()) {
    if (trackedPath !== excludedSelfPath && !inventoryPaths.has(trackedPath)) {
      review.push({ path: trackedPath, reason: 'UNCLASSIFIED_TRACKED_FILE' })
    }
  }
  for (const entry of inventory.entries) {
    if (entry.disposition === 'review') {
      review.push({ path: entry.path, reason: entry.reason || 'INVENTORY_REVIEW_REQUIRED' })
    }
  }

  const deleteEntries = inventory.entries
    .filter((entry) => entry.disposition === 'delete')
    .sort((left, right) => left.path.localeCompare(right.path))
  const retainedEntries = inventory.entries
    .filter((entry) => entry.disposition === 'keep' || entry.disposition === 'migrate')
    .sort((left, right) => left.path.localeCompare(right.path))
  const blockedByPath = new Map()
  const validDeletePaths = new Set()
  for (const entry of deleteEntries) {
    if (!repository.isRegularFile(entry.path)) {
      blockedByPath.set(entry.path, { path: entry.path, reason: 'TARGET_MISSING' })
      continue
    }
    try {
      verifyHash(entry.path, repository.readFile(entry.path), entry.sha256)
      validDeletePaths.add(entry.path)
    } catch (error) {
      blockedByPath.set(entry.path, {
        path: entry.path,
        reason: 'HASH_MISMATCH',
        detail: error.message,
      })
    }
  }

  const callers = findRetainedCallers(validDeletePaths, retainedEntries, repository)
  for (const [target, incoming] of callers) {
    if (incoming.size > 0) {
      blockedByPath.set(target, {
        path: target,
        reason: 'RETAINED_CALLER',
        callers: [...incoming].sort(),
      })
    }
  }

  const blocked = [...blockedByPath.values()].sort((left, right) => left.path.localeCompare(right.path))
  const deletable = deleteEntries
    .filter((entry) => !blockedByPath.has(entry.path))
    .map((entry) => ({ path: entry.path, sha256: entry.sha256, category: entry.category }))
  const retained = retainedEntries.map((entry) => ({
    path: entry.path,
    disposition: entry.disposition,
    category: entry.category,
  }))
  review.sort((left, right) => left.path.localeCompare(right.path))
  return {
    inventorySha256: inventory.inventorySha256,
    generatedFromCommit: inventory.generatedFromCommit,
    headCommit: repository.headCommit,
    phase5Accepted: repository.phase5Accepted === true,
    deletable,
    blocked,
    retained,
    review,
  }
}

function applyCleanup(verification, repository) {
  if (!verification || !Array.isArray(verification.deletable)) {
    throw new Error('verified cleanup result is required')
  }
  if (verification.blocked.length > 0 || verification.review.length > 0) {
    throw new Error('cleanup has blocked or review targets')
  }
  if (repository.phase5Accepted !== true || verification.phase5Accepted !== true) {
    throw new Error('Phase 5 accepted production evidence is required before local cleanup')
  }
  const recovery = []
  for (const item of verification.deletable) {
    const bytes = repository.readFile(item.path)
    verifyHash(item.path, bytes, item.sha256)
    recovery.push({ path: item.path, bytes, mode: repository.fileMode?.(item.path) })
  }
  const deleted = []
  try {
    for (const item of recovery) {
      repository.deleteFile(item.path)
      deleted.push(item.path)
    }
  } catch (error) {
    for (const item of recovery.filter((candidate) => deleted.includes(candidate.path)).reverse()) {
      repository.restoreFile?.(item.path, item.bytes, item.mode)
    }
    throw error
  }
  return { deleted }
}

function git(repositoryRoot, args, options = {}) {
  return execFileSync('git', args, {
    cwd: repositoryRoot,
    encoding: options.encoding || 'utf8',
  })
}

function readPhase5Accepted(repositoryRoot) {
  const statePath = path.join(repositoryRoot, 'docs/project-state.json')
  if (!fs.existsSync(statePath)) return false
  const state = JSON.parse(fs.readFileSync(statePath, 'utf8'))
  const target = state.targetProduct || {}
  const evidencePath = target.phase5Evidence
    ? path.join(repositoryRoot, ...target.phase5Evidence.split('/'))
    : null
  if (!evidencePath || !fs.existsSync(evidencePath)) return false
  const evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8'))
  const acceptedRuntime = Array.isArray(evidence.runtimeEvidence)
    && evidence.runtimeEvidence.some((item) => item
      && item.type === 'production_cutover'
      && item.state === 'accepted_write'
      && item.postCutoverRealUserAcceptance === 'passed')
  return target.productionCutoverAuthorized === true
    && target.productionCutoverReady === true
    && evidence.highestEvidenceLevel === 'live_verified'
    && evidence.manualAcceptance?.status === 'complete'
    && acceptedRuntime
}

function localRepository(repositoryRoot) {
  const headCommit = git(repositoryRoot, ['rev-parse', 'HEAD']).trim()
  const tracked = git(repositoryRoot, ['ls-files', '-z'])
    .split('\0')
    .filter(Boolean)
    .sort()
  const absolute = (relativePath) => path.join(repositoryRoot, ...validateTarget(relativePath).split('/'))
  return {
    headCommit,
    phase5Accepted: readPhase5Accepted(repositoryRoot),
    listTrackedFiles: () => tracked,
    isRegularFile: (relativePath) => {
      try {
        const metadata = fs.lstatSync(absolute(relativePath))
        return metadata.isFile() && !metadata.isSymbolicLink()
      } catch (error) {
        if (error.code === 'ENOENT') return false
        throw error
      }
    },
    readFile: (relativePath) => fs.readFileSync(absolute(relativePath)),
    fileMode: (relativePath) => fs.lstatSync(absolute(relativePath)).mode,
    deleteFile: (relativePath) => fs.unlinkSync(absolute(relativePath)),
    restoreFile: (relativePath, bytes, mode) => {
      const target = absolute(relativePath)
      fs.mkdirSync(path.dirname(target), { recursive: true })
      fs.writeFileSync(target, bytes, { mode })
    },
    isClean: () => git(repositoryRoot, ['status', '--porcelain', '--untracked-files=normal']).trim() === '',
    matchesInventoryBase: (baseCommit, excludedPath) => {
      const args = ['diff', '--quiet', baseCommit, 'HEAD', '--', '.']
      if (excludedPath) args.push(`:(exclude)${excludedPath}`)
      return spawnSync('git', args, { cwd: repositoryRoot }).status === 0
    },
  }
}

function parseArguments(argv) {
  let mode = 'dry-run'
  const values = {}
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index]
    if (argument === '--dry-run') {
      mode = 'dry-run'
    } else if (argument === '--apply') {
      mode = 'apply'
    } else if (['--inventory', '--inventory-sha', '--commit'].includes(argument)) {
      if (index + 1 >= argv.length) throw new Error(`${argument} requires a value`)
      values[argument.slice(2)] = argv[index + 1]
      index += 1
    } else if (argument === '--help' || argument === '-h') {
      return { help: true }
    } else {
      throw new Error(`unknown argument: ${argument}`)
    }
  }
  if (!values.inventory) throw new Error('--inventory is required')
  if (mode === 'apply' && (!values['inventory-sha'] || !values.commit)) {
    throw new Error('--apply requires --inventory-sha and --commit')
  }
  return { mode, ...values }
}

function printUsage() {
  process.stderr.write(
    'Usage: node scripts/apply-chickenbro-simc-local-cleanup.js --inventory <path> [--dry-run | --apply --inventory-sha <sha256> --commit <40-char-sha>]\n',
  )
}

function main(argv = process.argv.slice(2)) {
  const args = parseArguments(argv)
  if (args.help) {
    printUsage()
    return
  }
  const repositoryRoot = git(process.cwd(), ['rev-parse', '--show-toplevel']).trim()
  const inventoryPath = path.resolve(repositoryRoot, args.inventory)
  const relativeInventoryPath = path.relative(repositoryRoot, inventoryPath).split(path.sep).join('/')
  validateTarget(relativeInventoryPath)
  const inventoryBytes = fs.readFileSync(inventoryPath)
  const inventory = JSON.parse(inventoryBytes.toString('utf8'))
  const repository = localRepository(repositoryRoot)
  const verification = verifyCleanup(inventory, repository)
  const response = {
    mode: args.mode,
    mutationAuthorized: false,
    inventoryFileSha256: sha256(inventoryBytes),
    inventorySha256: verification.inventorySha256,
    generatedFromCommit: verification.generatedFromCommit,
    headCommit: verification.headCommit,
    phase5Accepted: verification.phase5Accepted,
    counts: {
      deletable: verification.deletable.length,
      blocked: verification.blocked.length,
      retained: verification.retained.length,
      review: verification.review.length,
    },
    deletable: verification.deletable,
    blocked: verification.blocked,
    review: verification.review,
  }
  if (args.mode === 'dry-run') {
    process.stdout.write(`${JSON.stringify(response)}\n`)
    return response
  }

  if (!SHA256.test(args['inventory-sha']) || args['inventory-sha'] !== response.inventoryFileSha256) {
    throw new Error('reviewed inventory file SHA mismatch')
  }
  if (!COMMIT.test(args.commit) || args.commit !== inventory.generatedFromCommit) {
    throw new Error('reviewed commit does not match the inventory base')
  }
  if (!repository.isClean()) throw new Error('tracked worktree must be clean before cleanup apply')
  if (!repository.matchesInventoryBase(args.commit, inventory.excludedSelfPath)) {
    throw new Error('current HEAD differs from the reviewed inventory outside the inventory file')
  }
  const result = applyCleanup(verification, repository)
  response.mutationAuthorized = true
  response.deleted = result.deleted
  process.stdout.write(`${JSON.stringify(response)}\n`)
  return response
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`${error.message}\n`)
    process.exitCode = 1
  }
}

module.exports = {
  applyCleanup,
  computeInventorySha256,
  extractReferenceCandidates,
  main,
  readPhase5Accepted,
  validateInventory,
  validateTarget,
  verifyCleanup,
  verifyHash,
}
