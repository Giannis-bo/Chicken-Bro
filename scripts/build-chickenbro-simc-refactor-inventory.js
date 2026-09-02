#!/usr/bin/env node

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')

const ALLOWED_DISPOSITIONS = new Set(['keep', 'migrate', 'delete'])
const FORBIDDEN_CATCH_ALL_PREFIXES = new Set(['', '.', './', '/', '**', '**/'])

function canonicalize(value) {
  if (Array.isArray(value)) {
    return value.map(canonicalize)
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonicalize(value[key])]),
    )
  }
  return value
}

function canonicalJson(value) {
  return JSON.stringify(canonicalize(value))
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex')
}

function normalizeRepositoryPath(relativePath, label = 'path') {
  if (typeof relativePath !== 'string' || relativePath.length === 0) {
    throw new Error(`${label} must be a non-empty string`)
  }
  if (relativePath.includes('\\')) {
    throw new Error(`${label} must use forward slashes: ${relativePath}`)
  }
  const normalized = path.posix.normalize(relativePath)
  if (
    path.posix.isAbsolute(relativePath) ||
    normalized === '..' ||
    normalized.startsWith('../') ||
    normalized !== relativePath
  ) {
    throw new Error(`${label} must be a normalized repository-relative path: ${relativePath}`)
  }
  return normalized
}

function validateStringArray(value, field, ruleId) {
  if (value === undefined) return []
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error(`rule ${ruleId} ${field} must be a non-empty array when present`)
  }
  if (field === 'prefixes' && value.some((item) => FORBIDDEN_CATCH_ALL_PREFIXES.has(item))) {
    throw new Error(`rule ${ruleId} contains a forbidden repository catch-all prefix`)
  }
  const normalized = value.map((item) => normalizeRepositoryPath(item, `rule ${ruleId} ${field}`))
  if (new Set(normalized).size !== normalized.length) {
    throw new Error(`rule ${ruleId} ${field} contains duplicates`)
  }
  return normalized
}

function selectorMatches(relativePath, rule) {
  return rule.paths.includes(relativePath) || rule.prefixes.some((prefix) => relativePath.startsWith(prefix))
}

function validateRules(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    throw new Error('rules must be an object')
  }
  if (input.schemaVersion !== 1) {
    throw new Error(`unsupported rules schemaVersion: ${input.schemaVersion}`)
  }
  if (!Array.isArray(input.rules) || input.rules.length === 0) {
    throw new Error('rules.rules must be a non-empty array')
  }

  const ids = new Set()
  const normalizedRules = input.rules.map((rawRule, index) => {
    if (!rawRule || typeof rawRule !== 'object' || Array.isArray(rawRule)) {
      throw new Error(`rule at index ${index} must be an object`)
    }
    for (const field of ['id', 'category', 'owner', 'reason']) {
      if (typeof rawRule[field] !== 'string' || rawRule[field].trim().length === 0) {
        throw new Error(`rule at index ${index} requires non-empty ${field}`)
      }
    }
    if (ids.has(rawRule.id)) {
      throw new Error(`duplicate rule id: ${rawRule.id}`)
    }
    ids.add(rawRule.id)
    if (!ALLOWED_DISPOSITIONS.has(rawRule.disposition)) {
      throw new Error(`rule ${rawRule.id} has invalid disposition: ${rawRule.disposition}`)
    }

    const paths = validateStringArray(rawRule.paths, 'paths', rawRule.id)
    const prefixes = validateStringArray(rawRule.prefixes, 'prefixes', rawRule.id)
    if (paths.length === 0 && prefixes.length === 0) {
      throw new Error(`rule ${rawRule.id} must declare paths or prefixes`)
    }
    for (const prefix of prefixes) {
      if (FORBIDDEN_CATCH_ALL_PREFIXES.has(prefix)) {
        throw new Error(`rule ${rawRule.id} contains a forbidden repository catch-all prefix`)
      }
      if (!prefix.endsWith('/')) {
        throw new Error(`rule ${rawRule.id} prefix must end with '/': ${prefix}`)
      }
    }

    return {
      id: rawRule.id,
      disposition: rawRule.disposition,
      category: rawRule.category,
      owner: rawRule.owner,
      reason: rawRule.reason,
      paths,
      prefixes,
    }
  })

  for (let index = 0; index < normalizedRules.length; index += 1) {
    const rule = normalizedRules[index]
    const earlier = normalizedRules.slice(0, index)
    for (const exactPath of rule.paths) {
      const shadow = earlier.find((candidate) => selectorMatches(exactPath, candidate))
      if (shadow) {
        throw new Error(`rule ${rule.id} path ${exactPath} is shadowed by earlier rule ${shadow.id}`)
      }
    }
    for (const prefix of rule.prefixes) {
      const shadow = earlier.find((candidate) => selectorMatches(prefix, candidate))
      if (shadow) {
        throw new Error(`rule ${rule.id} prefix ${prefix} is shadowed by earlier rule ${shadow.id}`)
      }
    }
  }

  return { schemaVersion: 1, rules: normalizedRules }
}

function loadRules(rulesPath) {
  return validateRules(JSON.parse(fs.readFileSync(rulesPath, 'utf8')))
}

function classifyPath(relativePath, rulesInput) {
  const normalizedPath = normalizeRepositoryPath(relativePath)
  const rules = rulesInput.rules ? rulesInput : validateRules(rulesInput)
  const match = rules.rules.find((rule) => selectorMatches(normalizedPath, rule))
  if (!match) {
    return {
      disposition: 'review',
      category: 'unresolved',
      owner: '',
      reason: 'NO_RULE_MATCH',
      matchedRule: '',
    }
  }
  return {
    disposition: match.disposition,
    category: match.category,
    owner: match.owner,
    reason: match.reason,
    matchedRule: match.id,
  }
}

function incrementCount(counts, key) {
  counts[key] = (counts[key] || 0) + 1
}

function buildInventory({ root, commit, paths, rules: rulesInput, excludedSelfPath }) {
  if (!/^[0-9a-f]{40}$/.test(commit)) {
    throw new Error(`commit must be a full lowercase 40-character SHA: ${commit}`)
  }
  const rules = rulesInput.rules ? rulesInput : validateRules(rulesInput)
  const excluded = excludedSelfPath
    ? normalizeRepositoryPath(excludedSelfPath, 'excludedSelfPath')
    : ''
  const normalizedPaths = [...new Set(paths.map((item) => normalizeRepositoryPath(item)))]
    .filter((item) => item !== excluded)
    .sort()
  const dispositionCounts = {}
  const categoryCounts = {}

  const entries = normalizedPaths.map((relativePath) => {
    const absolutePath = path.join(root, ...relativePath.split('/'))
    const stat = fs.statSync(absolutePath)
    if (!stat.isFile()) {
      throw new Error(`inventory path is not a regular file: ${relativePath}`)
    }
    const classification = classifyPath(relativePath, rules)
    incrementCount(dispositionCounts, classification.disposition)
    incrementCount(categoryCounts, classification.category)
    return {
      path: relativePath,
      ...classification,
      bytes: stat.size,
      sha256: sha256(fs.readFileSync(absolutePath)),
    }
  })

  const withoutHash = {
    schemaVersion: 1,
    generatedFromCommit: commit,
    excludedSelfPath: excluded,
    sourceRulesSha256: sha256(canonicalJson(rules)),
    entryCount: entries.length,
    unresolvedCount: dispositionCounts.review || 0,
    dispositionCounts: canonicalize(dispositionCounts),
    categoryCounts: canonicalize(categoryCounts),
    entries,
  }
  return {
    ...withoutHash,
    inventorySha256: sha256(canonicalJson(withoutHash)),
  }
}

function parseArguments(argv) {
  const values = {}
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index]
    const value = argv[index + 1]
    if (!['--rules', '--output'].includes(flag) || !value) {
      throw new Error('usage: build-chickenbro-simc-refactor-inventory.js --rules <path> --output <path>')
    }
    values[flag.slice(2)] = value
  }
  if (!values.rules || !values.output) {
    throw new Error('both --rules and --output are required')
  }
  return values
}

function main(argv = process.argv.slice(2)) {
  const repositoryRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], {
    encoding: 'utf8',
  }).trim()
  const trackedStatus = execFileSync(
    'git',
    ['status', '--porcelain', '--untracked-files=no'],
    { cwd: repositoryRoot, encoding: 'utf8' },
  ).trim()
  if (trackedStatus) {
    throw new Error('tracked worktree must be clean before generating the commit-bound inventory')
  }

  const args = parseArguments(argv)
  const rulesPath = path.resolve(repositoryRoot, args.rules)
  const outputPath = path.resolve(repositoryRoot, args.output)
  const outputRelativePath = path.relative(repositoryRoot, outputPath).split(path.sep).join('/')
  const rules = loadRules(rulesPath)
  const commit = execFileSync('git', ['rev-parse', 'HEAD'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  }).trim()
  const paths = execFileSync('git', ['ls-files', '-z'], {
    cwd: repositoryRoot,
    encoding: 'utf8',
  })
    .split('\0')
    .filter(Boolean)
  const inventory = buildInventory({
    root: repositoryRoot,
    commit,
    paths,
    rules,
    excludedSelfPath: outputRelativePath,
  })
  if (inventory.unresolvedCount !== 0) {
    const unresolved = inventory.entries
      .filter((entry) => entry.disposition === 'review')
      .map((entry) => entry.path)
      .join('\n')
    throw new Error(`inventory contains ${inventory.unresolvedCount} unresolved paths:\n${unresolved}`)
  }

  fs.mkdirSync(path.dirname(outputPath), { recursive: true })
  fs.writeFileSync(outputPath, `${JSON.stringify(inventory, null, 2)}\n`)
  process.stdout.write(
    `status=chickenbro_simc_refactor_inventory_generated entries=${inventory.entryCount} sha256=${inventory.inventorySha256}\n`,
  )
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`${error.stack || error.message}\n`)
    process.exitCode = 1
  }
}

module.exports = {
  buildInventory,
  canonicalJson,
  classifyPath,
  loadRules,
  main,
  validateRules,
}
