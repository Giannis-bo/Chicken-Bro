const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const verifyScript = 'scripts/verify-project.js'

function runVerify(args = [], options = {}) {
  return spawnSync(process.execPath, [verifyScript, ...args], {
    encoding: 'utf8',
    ...options
  })
}

function writeFile(filePath, source) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, source)
}

function writeJson(filePath, value) {
  writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

function writeReleaseFixture(root, release = 'artifacts/releases/fixture') {
  writeJson(path.join(root, 'docs/project-state.json'), {
    schemaVersion: 1,
    defaultLocalReleaseArtifact: release
  })
  writeJson(path.join(root, release, 'requirement.json'), {
    schemaVersion: 1,
    slug: 'fixture'
  })
  writeJson(path.join(root, release, 'evidence.json'), {
    schemaVersion: 1,
    slug: 'fixture',
    requirementSlug: 'fixture'
  })
  writeJson(path.join(root, release, 'manifest.json'), {
    schemaVersion: 1,
    slug: 'fixture'
  })
}

function parseJson(result) {
  assert.equal(result.stderr, '')
  return JSON.parse(result.stdout)
}

function git(root, args) {
  const result = spawnSync('git', args, { cwd: root, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr || result.stdout)
  return result.stdout.trim()
}

function createTaskReleaseRepo() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-verify-task-release-'))
  writeReleaseFixture(root, 'artifacts/releases/stale-global-release')
  git(root, ['init'])
  git(root, ['config', 'user.email', 'harness-test@example.invalid'])
  git(root, ['config', 'user.name', 'Harness Test'])
  git(root, ['add', '.'])
  git(root, ['commit', '-m', 'base'])
  return { root, base: git(root, ['rev-parse', 'HEAD']) }
}

function addTaskRelease(root, release, files = ['requirement.json', 'evidence.json', 'manifest.json']) {
  for (const fileName of files) {
    writeJson(path.join(root, release, fileName), {
      schemaVersion: 1,
      slug: path.basename(release),
      requirementSlug: path.basename(release)
    })
  }
}

test('verify-project exposes help without running verification', () => {
  const result = runVerify(['--help'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')
  assert.match(result.stdout, /Usage: node scripts\/verify-project\.js/)
  assert.doesNotMatch(result.stdout, /project_verification_/)
})

test('verify-project rejects unknown options and missing option values', () => {
  const unknown = runVerify(['--dryrun'])
  assert.notEqual(unknown.status, 0)
  assert.match(unknown.stderr, /Unknown option: --dryrun/)

  const missing = runVerify(['--profile'])
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /Missing value for --profile/)
})

test('verify-project dry-run resolves the explicit local default release and selects harness commands', () => {
  const result = runVerify(['--json', '--dry-run', '--profile', 'harness'])
  const projectState = JSON.parse(fs.readFileSync('docs/project-state.json', 'utf8'))

  assert.equal(result.status, 0)
  const summary = parseJson(result)
  assert.equal(summary.status, 'project_verification_plan_ready')
  assert.equal(summary.profile, 'harness')
  assert.equal(summary.release, projectState.defaultLocalReleaseArtifact)
  assert.ok(summary.commands.some((command) => command.command.includes('tests/verify-project.test.js')))
  assert.ok(summary.commands.some((command) => command.command.includes('tests/project-owner-map.test.js')))
  assert.ok(summary.commands.some((command) => command.command.includes('docs/project-owner-map.json')))
  assert.ok(summary.commands.some((command) => command.command.includes('scripts/project-harness.js --check')))
  assert.ok(summary.commands.some((command) => command.command === 'git diff --check'))
  assert.ok(!summary.commands.some((command) => /ssh|deploy_lighthouse|rsync|scp/.test(command.command)))
})

test('verify-project resolves the unique task release from the branch diff instead of the stale global pointer', () => {
  const { root, base } = createTaskReleaseRepo()
  const release = 'artifacts/releases/task-release'
  addTaskRelease(root, release)
  git(root, ['add', '.'])
  git(root, ['commit', '-m', 'task packet'])

  const result = runVerify([
    '--root', root,
    '--json',
    '--dry-run',
    '--profile', 'harness',
    '--release-from-changes',
    '--base', base
  ])

  assert.equal(result.status, 0, result.stderr)
  assert.equal(parseJson(result).release, release)
})

test('verify-project fails closed when a branch has no task release packet', () => {
  const { root, base } = createTaskReleaseRepo()
  writeFile(path.join(root, 'docs/change.md'), 'changed\n')
  git(root, ['add', '.'])
  git(root, ['commit', '-m', 'change without packet'])

  const result = runVerify([
    '--root', root,
    '--dry-run',
    '--profile', 'harness',
    '--release-from-changes',
    '--base', base
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /task_release_missing/)
})

test('verify-project fails closed when a branch changes multiple task release packets', () => {
  const { root, base } = createTaskReleaseRepo()
  addTaskRelease(root, 'artifacts/releases/task-one')
  addTaskRelease(root, 'artifacts/releases/task-two')
  git(root, ['add', '.'])
  git(root, ['commit', '-m', 'ambiguous packets'])

  const result = runVerify([
    '--root', root,
    '--dry-run',
    '--profile', 'harness',
    '--release-from-changes',
    '--base', base
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /task_release_ambiguous/)
})

test('verify-project fails closed when the task release packet is incomplete', () => {
  const { root, base } = createTaskReleaseRepo()
  addTaskRelease(root, 'artifacts/releases/incomplete-task', ['requirement.json', 'evidence.json'])
  git(root, ['add', '.'])
  git(root, ['commit', '-m', 'incomplete packet'])

  const result = runVerify([
    '--root', root,
    '--dry-run',
    '--profile', 'harness',
    '--release-from-changes',
    '--base', base
  ])

  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /task_release_incomplete/)
  assert.match(result.stderr, /manifest\.json/)
})

test('verify-project launches Windows command shims through executable runtimes', () => {
  const source = fs.readFileSync(verifyScript, 'utf8')

  assert.match(source, /process\.platform !== 'win32'/)
  assert.match(source, /process\.execPath/)
  assert.match(source, /node_modules', 'npm', 'bin', 'npm-cli\.js'/)
  assert.match(source, /command\.cmd === 'python3'/)
  assert.match(source, /function childProcessEnv\(/)
  assert.match(source, /path\.dirname\(process\.execPath\)/)
  assert.match(source, /Path: nodeRuntimePath/)
})

test('verify-project dry-run exposes backend, frontend and full profile boundaries', () => {
  const backend = parseJson(runVerify(['--json', '--dry-run', '--profile', 'backend', '--release', 'artifacts/releases/2026-07-10-executable-project-harness']))
  const frontend = parseJson(runVerify(['--json', '--dry-run', '--profile', 'frontend', '--release', 'artifacts/releases/2026-07-10-executable-project-harness']))
  const full = parseJson(runVerify(['--json', '--dry-run', '--profile', 'full', '--release', 'artifacts/releases/2026-07-10-executable-project-harness']))

  assert.ok(backend.commands.some((command) => command.command.includes('python3 -m unittest discover')))
  assert.ok(backend.commands.some((command) => command.command.includes('python3 -m compileall')))
  assert.ok(frontend.commands.some((command) => command.command.includes('node --test')))
  assert.ok(frontend.commands.some((command) => command.command.includes('node --check')))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run audit:ui-architecture'))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run typecheck'))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run lint'))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run test:taro'))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run verify:ui-asset-integrity'))
  assert.ok(frontend.commands.some((command) => command.command === 'npm run verify:ui-package'))
  assert.ok(full.commands.some((command) => command.command.includes('python3 -m unittest discover')))
  assert.ok(full.commands.some((command) => command.command.includes('node --test')))
  assert.ok(full.commands.some((command) => command.command.includes('scripts/project-harness.js --check')))
  assert.ok(full.commands.some((command) => command.command === 'npm run audit:ui-architecture'))
  assert.ok(full.commands.some((command) => command.command === 'npm run lint'))
  assert.ok(full.commands.some((command) => command.command === 'npm run verify:ui-asset-integrity'))
  assert.ok(full.commands.some((command) => command.command === 'npm run verify:ui-package'))
  assert.ok(full.commands.some((command) => command.command === 'npm run test:taro'))
})

test('GitHub CI installs dependencies and runs the full profile with UI release mechanics', () => {
  const workflow = fs.readFileSync('.github/workflows/project-harness.yml', 'utf8')
  const profileRuns = workflow.match(/node scripts\/verify-project\.js --profile/g) || []
  const release = JSON.parse(fs.readFileSync('docs/project-state.json', 'utf8')).defaultLocalReleaseArtifact
  const harness = parseJson(runVerify(['--json', '--dry-run', '--profile', 'harness', '--release', release, '--base', 'origin/main']))
  const full = parseJson(runVerify(['--json', '--dry-run', '--profile', 'full', '--release', release, '--base', 'origin/main']))
  const harnessTests = harness.commands.find((command) => command.label === 'harness contract tests')
  const fullTests = full.commands.find((command) => command.label === 'node test discover')

  assert.equal(profileRuns.length, 1)
  assert.match(workflow, /run: npm ci/)
  assert.match(workflow, /name: Full profile/)
  assert.match(workflow, /--profile full/)
  assert.match(workflow, /--release-from-changes/)
  assert.doesNotMatch(workflow, /activeReleaseArtifact/)
  assert.doesNotMatch(workflow, /Resolve active release/)
  assert.doesNotMatch(workflow, /name: Harness profile/)
  assert.ok(harnessTests)
  assert.ok(fullTests)
  assert.ok(full.commands.some((command) => command.command === 'npm run audit:ui-architecture'))
  assert.ok(full.commands.some((command) => command.command === 'npm run lint'))
  assert.ok(full.commands.some((command) => command.command === 'npm run verify:ui-asset-integrity'))
  assert.ok(full.commands.some((command) => command.command === 'npm run verify:ui-package'))
  for (const testFile of harnessTests.args.slice(2)) {
    assert.ok(fullTests.args.includes(testFile), `full profile must include ${testFile}`)
  }
  for (const harnessCommand of harness.commands.filter((command) => command !== harnessTests)) {
    assert.ok(full.commands.some((command) => command.command === harnessCommand.command), `full profile must include ${harnessCommand.label}`)
  }
})

test('verify-project rejects unknown profiles and missing releases', () => {
  const unknown = runVerify(['--json', '--dry-run', '--profile', 'deploy'])
  assert.notEqual(unknown.status, 0)
  assert.match(unknown.stderr, /Unknown profile/)

  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-verify-missing-release-'))
  writeJson(path.join(root, 'docs/project-state.json'), {
    schemaVersion: 1,
    defaultLocalReleaseArtifact: 'artifacts/releases/missing'
  })

  const missing = runVerify(['--root', root, '--json', '--dry-run', '--profile', 'harness'])
  assert.notEqual(missing.status, 0)
  assert.match(missing.stderr, /Missing release file/)
})

test('verify-project propagates command failures', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-verify-failing-command-'))
  writeReleaseFixture(root)

  const result = runVerify(['--root', root, '--json', '--profile', 'harness'])

  assert.notEqual(result.status, 0)
  const summary = JSON.parse(result.stdout)
  assert.equal(summary.status, 'project_verification_failed')
  assert.ok(summary.commands.some((command) => command.status === 'fail'))
})
