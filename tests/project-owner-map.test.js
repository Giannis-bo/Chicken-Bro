const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const { classifyPath, loadRules } = require('../scripts/build-chickenbro-simc-refactor-inventory')

const repositoryRoot = path.resolve(__dirname, '..')
const ownerMap = JSON.parse(fs.readFileSync(path.join(repositoryRoot, 'docs/project-owner-map.json'), 'utf8'))
const rules = loadRules(path.join(repositoryRoot, 'docs/refactor/chickenbro-simc-disposition-rules.json'))

test('project owner map covers exactly the rebuilt product domains', () => {
  assert.equal(ownerMap.schemaVersion, 2)
  assert.equal(ownerMap.activeMilestone, 'chickenbro_web_only_qq')
  assert.deepEqual(ownerMap.criticalDomains.map((domain) => domain.id), [
    'identity',
    'chickenbro_chat',
    'simc',
    'web_client',
    'migration_and_cutover',
    'control_and_cleanup',
    'admin_analytics',
  ])
  assert.deepEqual(ownerMap.unownedCriticalDomains, [])
  assert.deepEqual(ownerMap.conflictingFactOwners, [])
})

test('every owner and characterization path is retained and exists', () => {
  for (const domain of ownerMap.criticalDomains) {
    assert.equal(domain.status, 'active')
    assert.ok(domain.changedPathPatterns.length > 0, domain.id)
    for (const relativePath of [
      domain.factOwner,
      domain.writeOwner,
      ...domain.runtimeSurfaces,
      ...domain.characterization,
    ]) {
      assert.equal(fs.existsSync(path.join(repositoryRoot, relativePath)), true, `${domain.id}: ${relativePath}`)
      assert.equal(classifyPath(relativePath, rules).disposition, 'keep', `${domain.id}: ${relativePath}`)
    }
  }
})

test('the route owner targets Web Chat, SimC and restricted analytics', () => {
  assert.deepEqual(ownerMap.clientContract.clients, ['web'])
  assert.deepEqual(ownerMap.clientContract.webRoutes, ['/', '/simc', '/admin'])
  assert.deepEqual(ownerMap.clientContract.miniPages, [])
  assert.deepEqual(ownerMap.clientContract.tabs, [])
  assert.deepEqual(ownerMap.clientContract.businessDomains, ['chickenbro_chat', 'simc'])
})
