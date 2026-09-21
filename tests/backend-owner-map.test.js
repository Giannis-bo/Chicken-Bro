const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const repositoryRoot = path.resolve(__dirname, '..')
const ownerMap = JSON.parse(fs.readFileSync(path.join(repositoryRoot, 'docs/backend-owner-map.json'), 'utf8'))

test('backend owner map names formal Identity, Chat, SimC, POE2, Worker deployment and analytics owners', () => {
  assert.equal(ownerMap.schemaVersion, 2)
  assert.equal(ownerMap.status, 'active')
  assert.deepEqual(Object.keys(ownerMap.owners), [
    'composition',
    'identity',
    'chat',
    'simc',
    'worker',
    'migration',
    'deployment',
    'admin_analytics',
    'poe2',
  ])

  for (const owner of Object.values(ownerMap.owners)) {
    assert.equal(fs.existsSync(path.join(repositoryRoot, owner.path)), true, owner.path)
    assert.ok(owner.characterization.length > 0, owner.path)
    assert.ok(owner.characterization.every((relativePath) => fs.existsSync(path.join(repositoryRoot, relativePath))))
  }
})

test('engineering health hotspots are current formal owners', () => {
  assert.deepEqual(ownerMap.hotspotFiles.map((entry) => entry.path), [
    'server/app/main.py',
    'server/app/chickenbro/application.py',
    'server/app/simulation/application.py',
  ])
  assert.ok(ownerMap.hotspotFiles.every((entry) => entry.owners.length > 0))
})
