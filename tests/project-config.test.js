const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

test('mini-program pack options ignore non-client workspace directories without dropping runtime fallback modules', () => {
  const projectConfig = JSON.parse(fs.readFileSync('project.config.json', 'utf8'))
  const ignored = new Set((projectConfig.packOptions?.ignore || []).map((entry) => `${entry.type}:${entry.value}`))

  for (const value of [
    '.worktrees/**',
    'tests/**',
    'docs/**',
    'websim/**'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  for (const value of [
    'server/**/*.py',
    'server/**/*.pyc',
    'server/**/__pycache__/**',
    'server/data/**',
    'server/*.sh',
    'server/*.service',
    'server/*.timer'
  ]) {
    assert.ok(ignored.has(`glob:${value}`), `${value} should be ignored by WeChat DevTools packaging`)
  }

  assert.equal(ignored.has('glob:server/**'), false, 'server JS fallback modules must stay package-visible')

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
