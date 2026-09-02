'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  promoteWeappBuild,
  resolveIsolatedOutputRoot,
  stampWeappBuild,
  taroBuildCommand,
  validateBuild,
} = require('../scripts/build-weapp-safely')

function temporaryRoot(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-weapp-promotion-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  return root
}

function write(root, relative, contents) {
  const target = path.join(root, relative)
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, contents)
}

function writePage(root, pagePath, contents = 'page') {
  write(root, `${pagePath}.js`, `${contents} js`)
  write(root, `${pagePath}.json`, '{}')
  write(root, `${pagePath}.wxml`, '<view />')
  write(root, `${pagePath}.wxss`, '')
}

test('safe promotion keeps live launch entries present while installing a staged build', (t) => {
    const root = temporaryRoot(t)
    const staging = path.join(root, 'staging')
    const live = path.join(root, 'live')
    write(staging, 'app.json', '{"pages":["pages/news/news"],"version":"new"}')
    write(staging, 'app.js', 'new app')
    write(staging, 'app.wxss', 'new styles')
    writePage(staging, 'pages/news/news', 'new page')
    write(live, 'app.json', '{"pages":["pages/news/news"],"version":"old-and-long"}')
    write(live, 'app.js', 'old app')
    write(live, 'app.wxss', 'old styles')
    writePage(live, 'pages/news/news', 'old page')
    write(live, 'assets/ui-v2/stale.png', 'stale')

    const mutations = []
    const result = promoteWeappBuild(staging, live, {
      afterMutation(mutation) {
        mutations.push(mutation)
        assert.equal(fs.existsSync(path.join(live, 'app.json')), true)
        assert.equal(fs.existsSync(path.join(live, 'app.js')), true)
      },
    })

    assert.equal(result.installedFileCount, 4)
    assert.equal(result.unchangedFileCount, 3)
    assert.equal(result.removedFileCount, 1)
    assert.deepEqual(mutations.at(-1), { type: 'install', relative: 'app.js' })
    assert.ok(
      mutations.findIndex((mutation) => mutation.relative === 'pages/news/news.js')
        < mutations.findIndex((mutation) => mutation.relative === 'app.json'),
    )
    assert.equal(fs.readFileSync(path.join(live, 'app.js'), 'utf8'), 'new app')
    assert.equal(
      fs.readFileSync(path.join(live, 'app.json'), 'utf8'),
      '{"pages":["pages/news/news"],"version":"new"}',
    )
    assert.equal(fs.existsSync(path.join(live, 'assets/ui-v2/stale.png')), false)
    assert.equal(validateBuild(live).length, 7)
})

test('safe promotion does not touch an unchanged live package', (t) => {
  const root = temporaryRoot(t)
  const staging = path.join(root, 'staging')
  const live = path.join(root, 'live')
  for (const directory of [staging, live]) {
    write(directory, 'app.json', '{"pages":["pages/news/news"],"version":"same"}')
    write(directory, 'app.js', 'same app')
    write(directory, 'app.wxss', 'same styles')
    writePage(directory, 'pages/news/news', 'same page')
  }
  const before = fs.statSync(path.join(live, 'app.json')).mtimeMs
  const result = promoteWeappBuild(staging, live)

  assert.equal(result.installedFileCount, 0)
  assert.equal(result.unchangedFileCount, 7)
  assert.equal(fs.statSync(path.join(live, 'app.json')).mtimeMs, before)
})

test('safe promotion refreshes app.js last when only dependencies changed', (t) => {
  const root = temporaryRoot(t)
  const staging = path.join(root, 'staging')
  const live = path.join(root, 'live')
  for (const directory of [staging, live]) {
    write(directory, 'app.json', '{"pages":["pages/news/news"]}')
    write(directory, 'app.js', 'same app entry')
    write(directory, 'app.wxss', 'same styles')
    writePage(directory, 'pages/news/news', directory === staging ? 'new page' : 'old page')
  }
  const oldAppEntryInode = fs.statSync(path.join(live, 'app.js')).ino
  const mutations = []

  const result = promoteWeappBuild(staging, live, {
    afterMutation: (mutation) => mutations.push(mutation),
  })

  assert.equal(result.installedFileCount, 2)
  assert.deepEqual(mutations.at(-1), { type: 'install', relative: 'app.js' })
  assert.notEqual(fs.statSync(path.join(live, 'app.js')).ino, oldAppEntryInode)
  assert.equal(fs.readFileSync(path.join(live, 'app.js'), 'utf8'), 'same app entry')
})

test('safe promotion rejects a manifest whose page view is incomplete', (t) => {
  const root = temporaryRoot(t)
  const staging = path.join(root, 'staging')
  write(staging, 'app.json', '{"pages":["pages/news/news"]}')
  write(staging, 'app.js', 'app')
  write(staging, 'app.wxss', 'styles')
  write(staging, 'pages/news/news.js', 'page')
  write(staging, 'pages/news/news.json', '{}')
  write(staging, 'pages/news/news.wxss', '')

  assert.throws(() => validateBuild(staging), /missing page entry pages\/news\/news\.wxml/u)
})

test('safe promotion rejects an incomplete staging tree before touching live output', (t) => {
  const root = temporaryRoot(t)
  const staging = path.join(root, 'staging')
  const live = path.join(root, 'live')
  write(staging, 'app.js', 'incomplete')
  write(live, 'app.json', '{"version":"old"}')
  write(live, 'app.js', 'old app')
  write(live, 'app.wxss', 'old styles')

  assert.throws(() => promoteWeappBuild(staging, live), /missing app\.json/u)
  assert.equal(fs.readFileSync(path.join(live, 'app.js'), 'utf8'), 'old app')
})

test('safe promotion rejects symbolic links in the live package before mutation', (t) => {
  const root = temporaryRoot(t)
  const staging = path.join(root, 'staging')
  const live = path.join(root, 'live')
  const outsideManifest = path.join(root, 'outside-app.json')
  write(staging, 'app.json', '{"pages":["pages/news/news"],"version":"new"}')
  write(staging, 'app.js', 'new app')
  write(staging, 'app.wxss', 'new styles')
  writePage(staging, 'pages/news/news', 'new page')
  write(live, 'app.js', 'old app')
  write(live, 'app.wxss', 'old styles')
  fs.writeFileSync(outsideManifest, '{"version":"outside"}')
  try {
    fs.symlinkSync(outsideManifest, path.join(live, 'app.json'))
  } catch (error) {
    if (process.platform === 'win32' && error?.code === 'EPERM') {
      t.skip('Windows file symlink privilege is unavailable')
      return
    }
    throw error
  }

  assert.throws(() => promoteWeappBuild(staging, live), /cannot contain symbolic links/u)
  assert.equal(fs.readFileSync(outsideManifest, 'utf8'), '{"version":"outside"}')
  assert.equal(fs.readFileSync(path.join(live, 'app.js'), 'utf8'), 'old app')
})

test('explicit isolated output cannot point back inside the watched app tree', () => {
  assert.throws(() => resolveIsolatedOutputRoot('dist/weapp'), /outside the watched app tree/u)
  assert.throws(() => resolveIsolatedOutputRoot('.staging/weapp'), /outside the watched app tree/u)
  assert.equal(resolveIsolatedOutputRoot(os.tmpdir()), path.resolve(os.tmpdir()))
})

test('safe build launches the Taro JavaScript entry with the current Node runtime', () => {
  const command = taroBuildCommand()
  assert.equal(command.executable, process.execPath)
  assert.match(command.args[0], /node_modules[\\/]@tarojs[\\/]cli[\\/]bin[\\/]taro$/u)
  assert.equal(fs.existsSync(command.args[0]), true, 'resolved Taro CLI entry must exist')
  assert.deepEqual(command.args.slice(1), ['build', '--type', 'weapp'])
})

test('safe build stamps the generated package with the exact source identity before publication', (t) => {
  const root = temporaryRoot(t)
  const output = path.join(root, 'dist', 'weapp')
  write(root, 'apps/mini-taro/src/app.tsx', 'export default function App() { return null }\n')
  write(output, 'app.js', 'App({})\n')

  const result = stampWeappBuild(output, {
    root,
    gitHead: '0123456789abcdef0123456789abcdef01234567',
    builtAt: '2026-07-28T03:00:00.000Z',
  })
  const identity = JSON.parse(fs.readFileSync(path.join(output, 'wow-build.json'), 'utf8'))

  assert.deepEqual(identity, {
    schemaRevision: 'wow-weapp-build-v1',
    gitHead: '0123456789abcdef0123456789abcdef01234567',
    sourceHash: result.identity.sourceHash,
    builtAt: '2026-07-28T03:00:00.000Z',
  })
  assert.match(identity.sourceHash, /^sha256:[0-9a-f]{64}$/u)
  assert.ok(fs.statSync(path.join(output, 'app.js')).mtimeMs > 0)
})
