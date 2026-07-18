#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

const PROFILES = new Set(['harness', 'backend', 'frontend', 'full'])
const DEFAULT_BASE = 'origin/main'
const maxSpawnBufferBytes = 1024 * 1024
const maxRecordedCommandOutputBytes = 64 * 1024
const maxTotalRecordedOutputBytes = 256 * 1024

function boundedCommandOutput(value, remainingBytes = maxRecordedCommandOutputBytes) {
  if (!value) return ''
  const buffer = Buffer.from(value)
  const maximumBytes = Math.max(0, Math.min(maxRecordedCommandOutputBytes, remainingBytes))
  if (buffer.length <= maximumBytes) return value
  if (maximumBytes === 0) return `[output omitted: ${buffer.length} bytes; total output budget exhausted]\n`
  const marker = Buffer.from(`[output truncated: ${buffer.length} bytes; retaining tail within ${maximumBytes}-byte budget]\n`)
  const tailBytes = Math.max(0, maximumBytes - marker.length)
  const tail = tailBytes > 0 ? buffer.subarray(-tailBytes) : Buffer.alloc(0)
  return Buffer.concat([marker.subarray(0, maximumBytes), tail]).subarray(0, maximumBytes).toString('utf8')
}

function parseArgs(argv) {
  const options = {
    root: process.cwd(),
    profile: 'full',
    release: null,
    base: DEFAULT_BASE,
    dryRun: false,
    json: false
  }

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--root' && argv[index + 1]) {
      options.root = argv[index + 1]
      index += 1
    } else if (arg === '--profile' && argv[index + 1]) {
      options.profile = argv[index + 1]
      index += 1
    } else if (arg === '--release' && argv[index + 1]) {
      options.release = argv[index + 1]
      index += 1
    } else if (arg === '--base' && argv[index + 1]) {
      options.base = argv[index + 1]
      index += 1
    } else if (arg === '--dry-run') {
      options.dryRun = true
    } else if (arg === '--json') {
      options.json = true
    }
  }

  options.root = path.resolve(options.root)
  return options
}

function pathInsideRoot(root, relativePath, label) {
  const rootPath = path.resolve(root)
  const fullPath = path.resolve(rootPath, relativePath)
  if (fullPath !== rootPath && !fullPath.startsWith(`${rootPath}${path.sep}`)) {
    throw new Error(`Refusing ${label} outside repository root: ${relativePath}`)
  }
  return fullPath
}

function relativePathInsideRoot(root, relativePath, label) {
  const fullPath = pathInsideRoot(root, relativePath, label)
  return path.relative(path.resolve(root), fullPath).split(path.sep).join('/')
}

function readJson(root, relativePath) {
  return JSON.parse(fs.readFileSync(pathInsideRoot(root, relativePath, 'JSON file'), 'utf8'))
}

function resolveRelease(options) {
  let release = options.release
  if (!release) {
    const projectState = readJson(options.root, 'docs/project-state.json')
    release = projectState.activeReleaseArtifact
  }
  if (!release || typeof release !== 'string') {
    throw new Error('Missing release directory. Provide --release or docs/project-state.json.activeReleaseArtifact.')
  }
  release = relativePathInsideRoot(options.root, release, 'release directory')
  for (const fileName of ['requirement.json', 'evidence.json', 'manifest.json']) {
    const relativeFile = `${release}/${fileName}`
    if (!fs.existsSync(pathInsideRoot(options.root, relativeFile, 'release file'))) {
      throw new Error(`Missing release file: ${relativeFile}`)
    }
  }
  return release
}

function commandSpec(label, cmd, args) {
  return {
    label,
    cmd,
    args,
    command: [cmd, ...args.map(shellQuote)].join(' ')
  }
}

function shellQuote(value) {
  if (/^[A-Za-z0-9_./:=@+-]+$/.test(value)) {
    return value
  }
  return JSON.stringify(value)
}

function findFiles(root, directories, predicate) {
  const files = []
  for (const directory of directories) {
    const start = pathInsideRoot(root, directory, 'search directory')
    if (!fs.existsSync(start)) {
      continue
    }
    walk(start, files, predicate, root)
  }
  return files.sort()
}

function walk(currentPath, files, predicate, root) {
  const stat = fs.statSync(currentPath)
  if (stat.isDirectory()) {
    if (path.basename(currentPath) === '__pycache__' || path.basename(currentPath) === 'node_modules') {
      return
    }
    for (const entry of fs.readdirSync(currentPath)) {
      walk(path.join(currentPath, entry), files, predicate, root)
    }
    return
  }
  const relativePath = path.relative(root, currentPath).split(path.sep).join('/')
  if (predicate(relativePath)) {
    files.push(relativePath)
  }
}

function jsTestFiles(root) {
  return findFiles(root, ['tests'], (filePath) => filePath.endsWith('.test.js'))
}

function jsSyntaxFiles(root) {
  return findFiles(root, ['server', 'pages', 'components', 'scripts', 'tests'], (filePath) => filePath.endsWith('.js'))
}

function harnessJsonFiles(release) {
  return [
    'docs/project-state.json',
    'docs/project-owner-map.json',
    'docs/backend-owner-map.json',
    'docs/schemas/harness-requirement.schema.json',
    'docs/schemas/harness-evidence.schema.json',
    'docs/templates/harness-requirement.json',
    'docs/templates/harness-evidence.json',
    `${release}/requirement.json`,
    `${release}/evidence.json`,
    `${release}/manifest.json`
  ]
}

function harnessCheckCommand(release, base) {
  return commandSpec('harness packet check', 'node', [
    'scripts/project-harness.js',
    '--check',
    '--requirement-file',
    `${release}/requirement.json`,
    '--evidence-file',
    `${release}/evidence.json`,
    '--base',
    base
  ])
}

function jsonValidationCommand(release) {
  return commandSpec('json validation', 'node', [
    '-e',
    "const fs=require('fs'); for (const f of process.argv.slice(1)) JSON.parse(fs.readFileSync(f, 'utf8'))",
    ...harnessJsonFiles(release)
  ])
}

function harnessCommands(release, base) {
  return [
    commandSpec('harness contract tests', 'node', [
      '--test',
      'tests/project-harness.test.js',
      'tests/project-owner-map.test.js',
      'tests/project-state.test.js',
      'tests/backend-owner-map.test.js'
    ]),
    jsonValidationCommand(release),
    commandSpec('project harness syntax', 'node', ['--check', 'scripts/project-harness.js']),
    commandSpec('verify-project syntax', 'node', ['--check', 'scripts/verify-project.js']),
    harnessCheckCommand(release, base),
    commandSpec('diff whitespace check', 'git', ['diff', '--check'])
  ]
}

function backendCommands(release, base) {
  return [
    commandSpec('python unittest discover', 'python3', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', '*_test.py']),
    commandSpec('python compileall', 'python3', ['-m', 'compileall', '-q', 'server', 'tests']),
    harnessCheckCommand(release, base)
  ]
}

function frontendCommands(root, release, base) {
  const syntaxCommands = jsSyntaxFiles(root).map((filePath) => {
    return commandSpec(`js syntax ${filePath}`, 'node', ['--check', filePath])
  })
  return [
    commandSpec('node test discover', 'node', ['--test', ...jsTestFiles(root)]),
    commandSpec('taro architecture audit', 'npm', ['run', 'audit:ui-architecture']),
    commandSpec('raster asset integrity', 'npm', ['run', 'verify:ui-asset-integrity']),
    commandSpec('UI package mechanics', 'npm', ['run', 'verify:ui-package']),
    commandSpec('taro typecheck', 'npm', ['run', 'typecheck']),
    commandSpec('taro lint', 'npm', ['run', 'lint']),
    commandSpec('taro vitest', 'npm', ['run', 'test:taro']),
    ...syntaxCommands,
    harnessCheckCommand(release, base)
  ]
}

function profileCommands(options, release) {
  if (options.profile === 'harness') {
    return harnessCommands(release, options.base)
  }
  if (options.profile === 'backend') {
    return backendCommands(release, options.base)
  }
  if (options.profile === 'frontend') {
    return frontendCommands(options.root, release, options.base)
  }
  return [
    commandSpec('node test discover', 'node', ['--test', ...jsTestFiles(options.root)]),
    commandSpec('python unittest discover', 'python3', ['-m', 'unittest', 'discover', '-s', 'tests', '-p', '*_test.py']),
    commandSpec('python compileall', 'python3', ['-m', 'compileall', '-q', 'server', 'tests']),
    commandSpec('taro typecheck', 'npm', ['run', 'typecheck']),
    commandSpec('taro lint', 'npm', ['run', 'lint']),
    commandSpec('taro vitest', 'npm', ['run', 'test:taro']),
    commandSpec('taro architecture audit', 'npm', ['run', 'audit:ui-architecture']),
    commandSpec('raster asset integrity', 'npm', ['run', 'verify:ui-asset-integrity']),
    commandSpec('UI package mechanics', 'npm', ['run', 'verify:ui-package']),
    jsonValidationCommand(release),
    commandSpec('project harness syntax', 'node', ['--check', 'scripts/project-harness.js']),
    commandSpec('verify-project syntax', 'node', ['--check', 'scripts/verify-project.js']),
    ...jsSyntaxFiles(options.root).map((filePath) => commandSpec(`js syntax ${filePath}`, 'node', ['--check', filePath])),
    harnessCheckCommand(release, options.base),
    commandSpec('diff whitespace check', 'git', ['diff', '--check'])
  ]
}

function runCommands(root, commands, jsonMode) {
  const results = []
  let remainingOutputBytes = maxTotalRecordedOutputBytes
  for (const command of commands) {
    if (!jsonMode) {
      process.stdout.write(`> ${command.command}\n`)
    }
    const startedAt = Date.now()
    const result = spawnSync(command.cmd, command.args, {
      cwd: root,
      encoding: 'utf8',
      maxBuffer: maxSpawnBufferBytes
    })
    const stdout = boundedCommandOutput(result.stdout, remainingOutputBytes)
    remainingOutputBytes = Math.max(0, remainingOutputBytes - Buffer.byteLength(stdout))
    const stderr = boundedCommandOutput(result.stderr || result.error?.message, remainingOutputBytes)
    remainingOutputBytes = Math.max(0, remainingOutputBytes - Buffer.byteLength(stderr))
    if (!jsonMode) {
      if (stdout) process.stdout.write(stdout)
      if (stderr) process.stderr.write(stderr)
    }
    const item = {
      ...command,
      status: result.status === 0 ? 'pass' : 'fail',
      exitCode: result.status,
      durationMs: Date.now() - startedAt
    }
    if (jsonMode) {
      item.stdout = stdout
      item.stderr = stderr
    }
    results.push(item)
    if (result.status !== 0) {
      break
    }
  }
  return results
}

function buildSummary(options, release, commands, status) {
  return {
    schemaVersion: 1,
    status,
    profile: options.profile,
    release,
    base: options.base,
    dryRun: options.dryRun,
    commandCount: commands.length,
    commands
  }
}

function printHuman(summary) {
  process.stdout.write(`status=${summary.status}\n`)
  process.stdout.write(`profile=${summary.profile}\n`)
  process.stdout.write(`release=${summary.release}\n`)
  process.stdout.write(`commands=${summary.commandCount}\n`)
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2))
    if (!PROFILES.has(options.profile)) {
      throw new Error(`Unknown profile: ${options.profile}`)
    }
    const release = resolveRelease(options)
    const commands = profileCommands(options, release)

    if (options.dryRun) {
      const summary = buildSummary(options, release, commands, 'project_verification_plan_ready')
      if (options.json) {
        process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`)
      } else {
        printHuman(summary)
      }
      return
    }

    const results = runCommands(options.root, commands, options.json)
    const failed = results.some((command) => command.status === 'fail')
    const summary = buildSummary(
      options,
      release,
      results,
      failed ? 'project_verification_failed' : 'project_verification_passed'
    )
    if (options.json) {
      process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`)
    } else {
      printHuman(summary)
    }
    process.exitCode = failed ? 1 : 0
  } catch (error) {
    process.stderr.write(`${error && error.message ? error.message : String(error)}\n`)
    process.exitCode = 1
  }
}

main()
