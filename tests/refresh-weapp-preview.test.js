const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  ensureDevToolsRuntimeProject,
  resolveDevToolsCli,
  verifyWeappOutput,
  refreshWeappPreview,
} = require('../scripts/refresh-weapp-preview')
const { writeWeappBuildIdentity } = require('../scripts/weapp-build-identity')

function createFixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-refresh-weapp-preview-'))
  const projectRoot = path.join(root, 'apps', 'mini-taro')
  const outputRoot = path.join(projectRoot, 'dist', 'weapp')
  fs.mkdirSync(outputRoot, { recursive: true })
  fs.mkdirSync(path.join(projectRoot, 'src'), { recursive: true })
  fs.writeFileSync(path.join(projectRoot, 'project.config.json'), JSON.stringify({
    miniprogramRoot: 'dist/weapp/',
    projectname: 'wow-mini-taro',
    setting: {
      urlCheck: true,
    },
  }))
  fs.writeFileSync(path.join(projectRoot, 'project.private.config.json'), JSON.stringify({
    projectname: 'wow-mini-taro',
    setting: {
      urlCheck: false,
      compileHotReLoad: true,
    },
  }))
  fs.writeFileSync(path.join(outputRoot, 'app.json'), JSON.stringify({ pages: ['pages/news/news'] }))
  fs.writeFileSync(path.join(outputRoot, 'app.js'), 'App({})\n')
  fs.writeFileSync(path.join(outputRoot, 'common.wxss'), '.root{display:block}\n')
  fs.writeFileSync(path.join(projectRoot, 'src', 'app.tsx'), 'export default function App() { return null }\n')
  writeWeappBuildIdentity(root, outputRoot, {
    gitHead: '0123456789abcdef0123456789abcdef01234567',
    builtAt: '2026-07-28T00:00:00.000Z',
  })
  return { root, projectRoot, outputRoot }
}

test('WeChat output verification rejects a package whose source identity is stale', () => {
  const fixture = createFixture()
  fs.writeFileSync(path.join(fixture.outputRoot, 'wow-build.json'), JSON.stringify({
    schemaRevision: 'wow-weapp-build-v1',
    gitHead: '0000000000000000000000000000000000000000',
    sourceHash: `sha256:${'0'.repeat(64)}`,
    builtAt: '2026-07-28T00:00:00.000Z',
  }))

  assert.throws(
    () => verifyWeappOutput(fixture.root),
    /WeChat build source identity mismatch/u,
  )
})

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

test('DevTools runtime project opens the exact built package without relying on miniprogramRoot', () => {
  const fixture = createFixture()
  const verified = verifyWeappOutput(fixture.root)
  const runtimeProjectRoot = ensureDevToolsRuntimeProject(verified)
  const runtimeConfig = JSON.parse(fs.readFileSync(
    path.join(runtimeProjectRoot, 'project.config.json'),
    'utf8',
  ))
  const sourceConfig = JSON.parse(fs.readFileSync(
    path.join(fixture.projectRoot, 'project.config.json'),
    'utf8',
  ))

  assert.equal(runtimeProjectRoot, fixture.outputRoot)
  assert.equal(runtimeConfig.appid, sourceConfig.appid)
  assert.equal(runtimeConfig.compileType, 'miniprogram')
  assert.equal(runtimeConfig.miniprogramRoot, '')
  assert.match(runtimeConfig.projectname, /runtime$/u)
})

test('DevTools runtime project preserves the ignored local domain-check override outside release config', () => {
  const fixture = createFixture()
  const verified = verifyWeappOutput(fixture.root)
  ensureDevToolsRuntimeProject(verified)
  const runtimeConfig = JSON.parse(fs.readFileSync(
    path.join(fixture.outputRoot, 'project.config.json'),
    'utf8',
  ))
  const runtimePrivateConfig = JSON.parse(fs.readFileSync(
    path.join(fixture.outputRoot, 'project.private.config.json'),
    'utf8',
  ))

  assert.equal(runtimeConfig.setting.urlCheck, true)
  assert.equal(runtimePrivateConfig.projectname, 'wow-mini-taro-runtime')
  assert.equal(runtimePrivateConfig.setting.urlCheck, false)
  assert.equal(runtimePrivateConfig.setting.compileHotReLoad, true)
})

test('refresh builds first and opens the exact runtime package through the detected CLI', () => {
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
  assert.deepEqual(calls[1].args, ['open', '--project', fixture.outputRoot, '--lang', 'zh'])
  assert.equal(result.devToolsProjectRoot, fixture.outputRoot)
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
  assert.equal(calls[0].command, 'npm.cmd')
  assert.equal(calls[0].options.shell, true)
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
