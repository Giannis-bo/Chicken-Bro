#!/usr/bin/env node

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const schemaRevision = 'gear-manifest-v2-reader-audit-v1'
const supportedExtensions = new Set(['.js', '.mjs', '.cjs', '.py', '.ts', '.tsx'])
const runtimePrefixes = [
  'apps/mini-taro/',
  'packages/api-client/',
  'packages/domain/',
  'scripts/',
  'server/',
]
const prohibitedSymbols = [
  'get_latest_gear_exact_registry',
  '.load_latest_registry(',
]
const requiredBoundSymbols = [
  'get_active_gear_exact_registry',
  'load_active_manifest_public_gear',
  'load_candidate_manifest_binding',
]

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonical(item)]),
    )
  }
  return value
}

function digest(value) {
  return crypto
    .createHash('sha256')
    .update(JSON.stringify(canonical(value)))
    .digest('hex')
}

function normalized(value) {
  return String(value || '').replaceAll(path.sep, '/').replace(/^\.\/+/, '')
}

function isDefinition(line, symbol) {
  const name = symbol.replace(/^[^.]*\./, '').replace(/\($/, '')
  return new RegExp(`^\\s*(?:async\\s+)?def\\s+${name}\\s*\\(`).test(line)
}

function trackedRuntimeFiles(root) {
  const result = spawnSync('git', ['ls-files', '-z'], {
    cwd: root,
    encoding: 'buffer',
    maxBuffer: 8 * 1024 * 1024,
  })
  if (result.status !== 0) throw new Error('git ls-files failed')
  return result.stdout
    .toString('utf8')
    .split('\0')
    .map(normalized)
    .filter((file) => (
      file !== 'scripts/audit-gear-manifest-v2-readers.js'
      && runtimePrefixes.some((prefix) => file.startsWith(prefix))
      && supportedExtensions.has(path.extname(file).toLowerCase())
    ))
    .sort()
}

function sourceLines(root, relativePath) {
  const absolute = path.resolve(root, relativePath)
  const repository = `${path.resolve(root)}${path.sep}`
  if (!absolute.startsWith(repository)) throw new Error('tracked path escapes repository')
  return fs.readFileSync(absolute, 'utf8').split(/\r?\n/)
}

function collectManifestV2ReaderAudit({ root, allowlist } = {}) {
  const repositoryRoot = path.resolve(root || process.cwd())
  const files = Array.isArray(allowlist)
    ? [...new Set(allowlist.map(normalized).filter(Boolean))].sort()
    : trackedRuntimeFiles(repositoryRoot)
  const prohibitedCallers = []
  const boundReaders = []
  const rollbackCompatibility = []

  for (const file of files) {
    sourceLines(repositoryRoot, file).forEach((line, index) => {
      for (const symbol of prohibitedSymbols) {
        if (line.includes(symbol) && !isDefinition(line, symbol)) {
          prohibitedCallers.push({ path: file, line: index + 1, symbol })
        }
      }
      for (const symbol of requiredBoundSymbols) {
        if (line.includes(symbol) && !isDefinition(line, symbol)) {
          boundReaders.push({ path: file, line: index + 1, symbol })
        }
      }
      if (
        file === 'server/postgres_cache_store.py'
        && line.includes('self._gear_release_store.load_active_public_gear')
      ) {
        rollbackCompatibility.push({
          path: file,
          line: index + 1,
          symbol: 'load_active_public_gear',
          scope: 'manifest_v1_rollback_only',
        })
      }
    })
  }
  const requiredSymbolsPresent = Object.fromEntries(
    requiredBoundSymbols.map((symbol) => [
      symbol,
      boundReaders.some((entry) => entry.symbol === symbol),
    ]),
  )
  const missingBoundReaders = Object.entries(requiredSymbolsPresent)
    .filter(([, present]) => !present)
    .map(([symbol]) => symbol)
  const identity = {
    schemaRevision,
    status: (
      prohibitedCallers.length === 0
      && missingBoundReaders.length === 0
    ) ? 'verified' : 'blocked',
    prohibitedCallerCount: prohibitedCallers.length,
    prohibitedCallers,
    missingBoundReaders,
    boundReaders,
    rollbackCompatibility,
  }
  return {
    ...identity,
    reportId: `gear-manifest-v2-readers:sha256:${digest(identity)}`,
  }
}

function main() {
  process.stdout.write(`${JSON.stringify(collectManifestV2ReaderAudit())}\n`)
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}

module.exports = { collectManifestV2ReaderAudit, main }
