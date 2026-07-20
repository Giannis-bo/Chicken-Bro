const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  resolveDevToolsCli,
  verifyWeappOutput,
  refreshWeappPreview,
} = require('../scripts/refresh-weapp-preview')

function createFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-refresh-weapp-preview-'))
  const projectRoot = path.join(root, 'apps', 'mini-taro')
  const outputRoot = path.join(projectRoot, 'dist', 'weapp')
  fs.mkdirSync(outputRoot, { recursive: true })
  fs.writeFileSync(path.join(projectRoot, 'project.config.json'), JSON.stringify({
    miniprogramRoot: 'dist/weapp/',
  }))
  fs.writeFileSync(path.join(outputRoot, 'app.json'), JSON.stringify({ pages: ['pages/news/news'] }))
  fs.writeFileSync(path.join(outputRoot, 'app.js'), 'App({})\n')
  fs.writeFileSync(path.join(outputRoot, 'common.wxss'), '.root{display:block}\n')
  return { root, projectRoot, outputRoot }
}

test('DevTools CLI environment override wins when it points to a file', () => {
  const fixture = createFixture()
  const cli = path.join(fixture.root, 'wechat-cli')
  fs.writeFileSync(cli, '#!/bin/sh\n')

  assert.equal(resolveDevToolsCli({
    platform: 'darwin',
    env: { WECHAT_DEVTOOLS_CLI: cli },
  }), cli)
})

test('DevTools CLI detects the standard Windows installation path', () => {
  const cli = path.win32.join('C:\\Program Files', 'Tencent', '微信web开发者工具', 'cli.bat')

  assert.equal(resolveDevToolsCli({
    platform: 'win32',
    env: { ProgramFiles: 'C:\\Program Files' },
    fileExists: (candidate) => candidate === cli,
  }), cli)
})

test('WeChat output verification requires the configured output and final app.js marker', () => {
  const fixture = createFixture()
  const result = verifyWeappOutput(fixture.root, { buildStartedAt: 0 })

  assert.equal(result.status, 'pass')
  assert.equal(result.projectRoot, fixture.projectRoot)
  assert.equal(result.outputRoot, fixture.outputRoot)
  assert.ok(result.fileCount >= 3)
})

test('refresh builds first and opens the repository project through the detected CLI', () => {
  const fixture = createFixture()
  const cli = path.join(fixture.root, 'wechat-cli')
  fs.writeFileSync(cli, '#!/bin/sh\n')
  const calls = []

  const result = refreshWeappPreview({
    root: fixture.root,
    platform: 'darwin',
    env: { WECHAT_DEVTOOLS_CLI: cli },
    now: () => 0,
    execute(command, args, options) {
      calls.push({ command, args, options })
      return { status: 0 }
    },
  })

  assert.equal(result.status, 'preview_refreshed')
  assert.deepEqual(calls[0].args, ['run', 'build:weapp'])
  assert.equal(calls[1].command, cli)
  assert.deepEqual(calls[1].args, ['open', '--project', fixture.projectRoot, '--lang', 'zh'])
})

test('refresh launches the Windows cli.bat through a shell', () => {
  const fixture = createFixture()
  const cli = 'C:\\Program Files\\Tencent\\微信web开发者工具\\cli.bat'
  const calls = []

  const result = refreshWeappPreview({
    root: fixture.root,
    platform: 'win32',
    env: {},
    resolveCli: () => cli,
    execute(command, args, options) {
      calls.push({ command, args, options })
      return { status: 0 }
    },
  })

  assert.equal(result.status, 'preview_refreshed')
  assert.equal(calls[1].command, cli)
  assert.equal(calls[1].options.shell, true)
})

test('refresh stops before DevTools when the build fails', () => {
  const fixture = createFixture()
  let callCount = 0

  assert.throws(() => refreshWeappPreview({
    root: fixture.root,
    platform: 'darwin',
    env: {},
    execute() {
      callCount += 1
      return { status: 7 }
    },
  }), /build:weapp failed with exit code 7/)
  assert.equal(callCount, 1)
})

test('refresh preserves a verified build and reports manual handoff when CLI is unavailable', () => {
  const fixture = createFixture()

  const result = refreshWeappPreview({
    root: fixture.root,
    platform: 'linux',
    env: {},
    now: () => 0,
    execute() {
      return { status: 0 }
    },
  })

  assert.equal(result.status, 'manual_open_required')
  assert.equal(result.projectRoot, fixture.projectRoot)
  assert.match(result.reason, /WECHAT_DEVTOOLS_CLI/)
})
