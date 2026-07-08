const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'))
}

function packIgnoreSet() {
  const projectConfig = readJson('project.config.json')
  return new Set((projectConfig.packOptions?.ignore || []).map((entry) => `${entry.type}:${entry.value}`))
}

test('mini-program pack options keep non-client workspace and generated evidence out of source packages', () => {
  const ignored = packIgnoreSet()

  for (const value of [
    '.worktrees/**',
    '.git/**',
    'artifacts/**',
    'tmp/**',
    'tests/**',
    'docs/**',
    'scripts/**',
    'websim/**',
    'assets/generated/**'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  for (const value of [
    'server/**/*.py',
    'server/*.py',
    'server/**/*.sql',
    'server/**/*.json',
    'server/**/*.pyc',
    'server/**/__pycache__/**',
    'server/data/**',
    'server/*.sh',
    'server/*.service',
    'server/*.timer'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should keep backend-only files out of the package`)
  }

  assert.equal(ignored.has('glob:server/**'), false, 'server JS fallback modules must stay package-visible')
})

test('runtime JS fallback modules remain package-visible for mini-program require calls', () => {
  for (const runtimeModule of [
    'server/news/home-payload.js',
    'server/news/articles.seed.js',
    'server/builds/home-payload.js',
    'server/pve/home-payload.js',
    'server/game-season.js'
  ]) {
    assert.ok(fs.existsSync(runtimeModule), `${runtimeModule} should remain available to mini-program require()`)
  }
})

test('app config uses current custom tabbar assets and stays on default WebView renderer', () => {
  const appConfig = readJson('app.json')

  assert.equal(appConfig.renderer, undefined)
  assert.equal(appConfig.rendererOptions, undefined)
  assert.equal(appConfig.componentFramework, undefined)
  assert.equal(appConfig.tabBar?.custom, true)
  assert.equal(appConfig.tabBar.list.length, 4)

  for (const item of appConfig.tabBar.list) {
    assert.ok(appConfig.pages.includes(item.pagePath), `${item.pagePath} should be registered in app.json pages`)
    assert.ok(fs.existsSync(item.iconPath), `${item.iconPath} should be committed runtime tabbar asset`)
    assert.ok(fs.existsSync(item.selectedIconPath), `${item.selectedIconPath} should be committed runtime tabbar asset`)
    assert.doesNotMatch(item.iconPath, /^assets\/generated\//)
    assert.doesNotMatch(item.selectedIconPath, /^assets\/generated\//)
  }
})

test('custom tabbar owns icon fallback without depending on generated image slices', () => {
  const source = fs.readFileSync('custom-tab-bar/index.js', 'utf8')
  const wxml = fs.readFileSync('custom-tab-bar/index.wxml', 'utf8')
  const appConfig = readJson('app.json')

  for (const item of appConfig.tabBar.list) {
    assert.match(source, new RegExp(item.pagePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.match(source, new RegExp(item.iconPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
    assert.match(source, new RegExp(item.selectedIconPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }

  assert.match(source, /handleIconError/)
  assert.match(source, /iconLoadFailed/)
  assert.match(wxml, /wx:if="\{\{!item\.iconLoadFailed\}\}"/)
  assert.match(wxml, /wx:else class="wow-tabbar__glyph"/)
  assert.doesNotMatch(`${source}\n${wxml}`, /assets\/generated\//)
})
