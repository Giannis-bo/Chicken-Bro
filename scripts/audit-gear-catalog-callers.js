#!/usr/bin/env node

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const schemaRevision = 'gear-catalog-callers-v1'
const reportPrefix = 'gear-catalog-callers:sha256:'
const maximumSourceBytes = 2 * 1024 * 1024
const maximumReportBytes = 2 * 1024 * 1024
const supportedExtensions = new Set([
  '.cjs',
  '.js',
  '.json',
  '.md',
  '.mjs',
  '.py',
  '.sh',
  '.sql',
  '.ts',
  '.tsx',
])
const symbols = [
  '/api/websim/gear/resolve',
  '/api/websim/gear',
  '/api/websim/profile',
  '/api/simulator/simc',
  'load_active_public_gear',
  'load_active_authority_context',
  'load_active_manifest_binding',
  'gearCatalogReleaseId',
  'gearCatalogRevision',
]
const categoryNames = [
  'activeBackend',
  'taro',
  'compatibility',
  'testsDocs',
  'unresolved',
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

function stableJson(value) {
  return JSON.stringify(canonical(value))
}

function sha256(value) {
  return crypto.createHash('sha256').update(stableJson(value)).digest('hex')
}

function normalizedRelativePath(value) {
  return String(value || '').replaceAll(path.sep, '/').replace(/^\.\/+/, '')
}

function categoryFor(relativePath) {
  if (
    relativePath.startsWith('tests/')
    || relativePath.startsWith('docs/')
    || relativePath.startsWith('artifacts/')
    || /\.(?:test|spec)\./.test(relativePath)
    || relativePath.endsWith('.md')
  ) return 'testsDocs'
  if (
    relativePath.startsWith('apps/mini-taro/')
    || relativePath.startsWith('packages/api-client/')
    || relativePath.startsWith('packages/domain/')
  ) return 'taro'
  if (
    relativePath.startsWith('pages/')
    || relativePath.startsWith('websim/')
  ) return 'compatibility'
  if (relativePath.startsWith('server/')) return 'activeBackend'
  return 'unresolved'
}

function stripCodeComments(content, extension) {
  if (extension === '.json' || extension === '.md') return content.split(/\r?\n/)
  const output = []
  let inBlockComment = false
  for (const sourceLine of content.split(/\r?\n/)) {
    let line = ''
    let quote = ''
    let escaped = false
    for (let index = 0; index < sourceLine.length; index += 1) {
      const current = sourceLine[index]
      const next = sourceLine[index + 1] || ''
      if (inBlockComment) {
        if (current === '*' && next === '/') {
          inBlockComment = false
          index += 1
        }
        continue
      }
      if (quote) {
        line += current
        if (escaped) {
          escaped = false
        } else if (current === '\\') {
          escaped = true
        } else if (current === quote) {
          quote = ''
        }
        continue
      }
      if (current === '"' || current === "'" || current === '`') {
        quote = current
        line += current
        continue
      }
      if (current === '/' && next === '*') {
        inBlockComment = true
        index += 1
        continue
      }
      if (current === '/' && next === '/') break
      if (
        current === '#'
        && ['.py', '.sh'].includes(extension)
      ) break
      line += current
    }
    output.push(line)
  }
  return output
}

function isDefinition(line, symbol) {
  const escaped = symbol.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return new RegExp(
    `^\\s*(?:async\\s+)?(?:def|function)\\s+${escaped}\\s*\\(|^\\s*(?:export\\s+)?(?:async\\s+)?${escaped}\\s*\\(`,
  ).test(line)
}

function entriesForFile(root, relativePath) {
  const normalizedPath = normalizedRelativePath(relativePath)
  if (normalizedPath === 'scripts/audit-gear-catalog-callers.js') return []
  const extension = path.extname(normalizedPath).toLowerCase()
  if (!supportedExtensions.has(extension)) return []
  const absolutePath = path.resolve(root, normalizedPath)
  const expectedPrefix = `${path.resolve(root)}${path.sep}`
  if (!absolutePath.startsWith(expectedPrefix)) {
    throw new Error(`tracked path escapes repository: ${normalizedPath}`)
  }
  const stat = fs.statSync(absolutePath)
  if (!stat.isFile() || stat.size > maximumSourceBytes) return []
  const content = fs.readFileSync(absolutePath, 'utf8')
  const lines = stripCodeComments(content, extension)
  const category = categoryFor(normalizedPath)
  const entries = []
  lines.forEach((line, index) => {
    for (const symbol of symbols) {
      if (
        symbol === '/api/websim/gear'
        && line.includes('/api/websim/gear/resolve')
      ) continue
      if (!line.includes(symbol) || isDefinition(line, symbol)) continue
      entries.push({
        path: normalizedPath,
        line: index + 1,
        symbol,
        category,
      })
    }
  })
  return entries
}

function trackedFiles(root) {
  const result = spawnSync('git', ['ls-files', '-z'], {
    cwd: root,
    encoding: 'buffer',
    maxBuffer: 8 * 1024 * 1024,
  })
  if (result.status !== 0) {
    throw new Error('git ls-files failed for caller audit')
  }
  return result.stdout
    .toString('utf8')
    .split('\0')
    .map(normalizedRelativePath)
    .filter(Boolean)
}

function collectGearCatalogCallers({ root, allowlist } = {}) {
  const repositoryRoot = path.resolve(root || process.cwd())
  const files = Array.isArray(allowlist)
    ? [...new Set(allowlist.map(normalizedRelativePath).filter(Boolean))]
    : trackedFiles(repositoryRoot)
  files.sort((left, right) => left.localeCompare(right))
  const categories = Object.fromEntries(categoryNames.map((name) => [name, []]))
  for (const relativePath of files) {
    for (const entry of entriesForFile(repositoryRoot, relativePath)) {
      categories[entry.category].push(entry)
    }
  }
  for (const name of categoryNames) {
    categories[name].sort((left, right) => (
      left.path.localeCompare(right.path)
      || left.line - right.line
      || left.symbol.localeCompare(right.symbol)
    ))
  }
  const runtimeCallerCount = (
    categories.activeBackend.length
    + categories.taro.length
    + categories.compatibility.length
  )
  const unresolvedCount = categories.unresolved.length
  const identity = {
    schemaRevision,
    status: unresolvedCount ? 'partial' : 'verified',
    runtimeCallerCount,
    unresolvedCount,
    categories,
  }
  return {
    ...identity,
    reportId: `${reportPrefix}${sha256(identity)}`,
  }
}

function repositoryRelativeOutput(root, output) {
  const repositoryRoot = path.resolve(root)
  const absoluteOutput = path.resolve(output)
  const relative = path.relative(repositoryRoot, absoluteOutput)
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error('caller audit output must stay inside the repository')
  }
  return {
    absoluteOutput,
    relativeOutput: normalizedRelativePath(relative),
  }
}

function writeCallerAudit({ root, output, report }) {
  const repositoryRoot = path.resolve(root || process.cwd())
  const { absoluteOutput, relativeOutput } = repositoryRelativeOutput(
    repositoryRoot,
    output,
  )
  if (fs.existsSync(absoluteOutput)) {
    throw new Error(`caller audit output already exists: ${relativeOutput}`)
  }
  const serialized = `${JSON.stringify(report, null, 2)}\n`
  if (Buffer.byteLength(serialized) > maximumReportBytes) {
    throw new Error('caller audit output exceeds bounded report size')
  }
  fs.mkdirSync(path.dirname(absoluteOutput), { recursive: true })
  const temporaryPath = `${absoluteOutput}.tmp-${process.pid}`
  let descriptor
  try {
    descriptor = fs.openSync(temporaryPath, 'wx', 0o600)
    fs.writeFileSync(descriptor, serialized, 'utf8')
    fs.fsyncSync(descriptor)
    fs.closeSync(descriptor)
    descriptor = undefined
    fs.renameSync(temporaryPath, absoluteOutput)
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor)
    if (fs.existsSync(temporaryPath)) fs.unlinkSync(temporaryPath)
    throw error
  }
  return relativeOutput
}

function parseArguments(argv) {
  const options = { output: '' }
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index]
    if (argument === '--output') {
      const value = argv[index + 1]
      if (!value || value.startsWith('--')) {
        throw new Error('--output requires a path')
      }
      options.output = value
      index += 1
      continue
    }
    throw new Error(`unknown option: ${argument}`)
  }
  return options
}

function main(argv = process.argv.slice(2)) {
  const options = parseArguments(argv)
  const root = process.cwd()
  const report = collectGearCatalogCallers({ root })
  if (options.output) {
    const written = writeCallerAudit({
      root,
      output: options.output,
      report,
    })
    process.stdout.write(`${JSON.stringify({
      status: report.status,
      reportId: report.reportId,
      output: written,
    })}\n`)
    return
  }
  process.stdout.write(`${JSON.stringify(report)}\n`)
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}

module.exports = {
  collectGearCatalogCallers,
  main,
  writeCallerAudit,
}
