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
    activeReleaseArtifact: release
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

test('verify-project dry-run resolves the active release and selects harness commands', () => {
  const result = runVerify(['--json', '--dry-run', '--profile', 'harness'])
  const projectState = JSON.parse(fs.readFileSync('docs/project-state.json', 'utf8'))

  assert.equal(result.status, 0)
  const summary = parseJson(result)
  assert.equal(summary.status, 'project_verification_plan_ready')
  assert.equal(summary.profile, 'harness')
  assert.equal(summary.release, projectState.activeReleaseArtifact)
  assert.ok(summary.commands.some((command) => command.command.includes('tests/project-owner-map.test.js')))
  assert.ok(summary.commands.some((command) => command.command.includes('docs/project-owner-map.json')))
  assert.ok(summary.commands.some((command) => command.command.includes('scripts/project-harness.js --check')))
  assert.ok(summary.commands.some((command) => command.command === 'git diff --check'))
  assert.ok(!summary.commands.some((command) => /ssh|deploy_lighthouse|rsync|scp/.test(command.command)))
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
  const release = JSON.parse(fs.readFileSync('docs/project-state.json', 'utf8')).activeReleaseArtifact
  const harness = parseJson(runVerify(['--json', '--dry-run', '--profile', 'harness', '--release', release, '--base', 'origin/main']))
  const full = parseJson(runVerify(['--json', '--dry-run', '--profile', 'full', '--release', release, '--base', 'origin/main']))
  const harnessTests = harness.commands.find((command) => command.label === 'harness contract tests')
  const fullTests = full.commands.find((command) => command.label === 'node test discover')

  assert.equal(profileRuns.length, 1)
  assert.match(workflow, /run: npm ci/)
  assert.match(workflow, /name: Full profile/)
  assert.match(workflow, /--profile full/)
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
    activeReleaseArtifact: 'artifacts/releases/missing'
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
