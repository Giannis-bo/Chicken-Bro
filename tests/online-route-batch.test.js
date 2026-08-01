'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const test = require('node:test')

const { maxOnlineRoutesPerRun, requireOnlineRouteBatch } = require('../scripts/online-route-batch')

test('online WeChat validators require explicit resumable two-route batches', () => {
  assert.equal(maxOnlineRoutesPerRun, 2)
  assert.deepEqual([...requireOnlineRouteBatch('news_home,news_detail', 'TEST_ROUTES', ['news_home', 'news_detail'])], ['news_home', 'news_detail'])
  assert.throws(() => requireOnlineRouteBatch('', 'TEST_ROUTES', ['news_home']), /is required/)
  assert.throws(() => requireOnlineRouteBatch('all', 'TEST_ROUTES', ['news_home']), /rejects "all"/)
  assert.throws(() => requireOnlineRouteBatch('news_home,news_detail,build_intel', 'TEST_ROUTES', ['news_home', 'news_detail', 'build_intel']), /limited to 2 routes/)
  assert.throws(() => requireOnlineRouteBatch('unknown', 'TEST_ROUTES', ['news_home']), /unknown TEST_ROUTES/)
})

test('capture guard rejects missing routes before loading WeChat automation', () => {
  const root = path.resolve(__dirname, '..')
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-online-route-guard-'))
  const preloadPath = path.join(directory, 'reject-wechat-automator.js')
  fs.writeFileSync(preloadPath, [
    "'use strict'",
    "const Module = require('node:module')",
    'const originalLoad = Module._load',
    'Module._load = function guardedLoad(request) {',
    "  if (String(request).includes('wechat-automator')) throw new Error('WECHAT_AUTOMATOR_LOADED_BEFORE_ROUTE_GUARD')",
    '  return originalLoad.apply(this, arguments)',
    '}',
  ].join('\n'))
  try {
    const env = {
      ...process.env,
      NODE_OPTIONS: `${process.env.NODE_OPTIONS ?? ''} --require=${preloadPath}`.trim(),
    }
    delete env.UI_REVIEW_ROUTES
    const result = spawnSync(process.execPath, [path.join(root, 'scripts/capture-ui-review-cache.js')], {
      cwd: root,
      encoding: 'utf8',
      env,
      timeout: 3000,
    })
    assert.equal(result.status, 1)
    assert.match(result.stderr, /UI_REVIEW_ROUTES is required/)
    assert.doesNotMatch(result.stderr, /WECHAT_AUTOMATOR_LOADED_BEFORE_ROUTE_GUARD/)
    assert.equal(result.stdout, '')
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('all online WeChat entrypoints fail compactly before connect when route scope is missing', () => {
  const root = path.resolve(__dirname, '..')
  const entries = [
    ['UI_REVIEW_ROUTES', 'scripts/capture-ui-review-cache.js'],
    ['BASELINE_ROUTES', 'scripts/verify-ui-baselines.js'],
    ['GEOMETRY_ROUTES', 'scripts/verify-ui-route-geometry.js'],
    ['INTERACTION_ROUTES', 'scripts/verify-ui-interactions.js'],
    ['SELECTED_STATE_ROUTES', 'scripts/verify-ui-selected-states.js'],
    ['ASSET_SLOT_ROUTES', 'scripts/verify-ui-asset-slots.js'],
  ]
  for (const [environmentName, script] of entries) {
    const env = { ...process.env }
    delete env[environmentName]
    const result = spawnSync(process.execPath, [path.join(root, script)], { cwd: root, encoding: 'utf8', env, timeout: 3000 })
    assert.equal(result.status, 1, script)
    assert.match(result.stderr, new RegExp(`${environmentName} is required`), script)
    assert.ok(Buffer.byteLength(result.stderr) <= 256, `${script} emitted an unbounded guard error`)
    assert.doesNotMatch(result.stderr, /\n\s+at\s/u, script)
    assert.equal(result.stdout, '', script)
  }
})
