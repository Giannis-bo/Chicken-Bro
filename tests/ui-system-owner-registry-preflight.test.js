const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-owner-registry-preflight.js'

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

test('owner registry preflight validates all current foundation and surface owners', () => {
  const result = runPreflight(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'owner_registry_source_ready')
  assert.equal(report.ownerRegistryReady, true)
  assert.equal(report.pageIntegration, false)
  assert.equal(report.runtimeVerified, false)
  assert.equal(report.finalAccepted, false)
  assert.equal(report.foundationOwnerCount, 12)
  assert.equal(report.surfaceOwnerCount, 14)
  assert.equal(report.ownerCount, 26)
  assert.deepEqual(report.requiredSurfaces.sort(), report.coveredSurfaces.sort())
  assert.equal(report.boundaryOwners.realObjectIconOwner, 'GameObjectIcon')
  assert.equal(report.boundaryOwners.materialOwner, 'MaterialImage')
  assert.equal(report.boundaryOwners.statusOwner, 'StatusVisual')
  assert.equal(report.boundaryOwners.evidenceOwner, 'EvidenceLedger')
  assert.ok(report.nonPromotion.includes('not_runtime_verified'))
})

test('owner registry preflight fails closed for missing component files or missing surface coverage', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-owner-registry-'))
  const registryPath = path.join(directory, 'registry.json')
  fs.writeFileSync(registryPath, JSON.stringify({
    schemaVersion: 1,
    status: 'owner_registry_source_ready',
    pageIntegration: false,
    runtimeVerified: false,
    finalAccepted: false,
    foundationOwners: [
      { name: 'GameObjectIcon', componentPath: 'components/game-object-icon/game-object-icon' },
      { name: 'MaterialImage', componentPath: 'components/material-image/material-image' },
      { name: 'StatusVisual', componentPath: 'components/status-visual/status-visual' },
      { name: 'ActionButton', componentPath: 'components/action-button/action-button' },
      { name: 'EvidenceLedger', componentPath: 'components/evidence-ledger/evidence-ledger' },
      { name: 'ChatShell', componentPath: 'components/chat-shell/chat-shell' }
    ],
    surfaceOwners: [
      { name: 'MissingSurface', componentPath: 'components/missing-surface/missing-surface', surface: 'news_home' }
    ],
    surfaceCoverage: {
      news_home: ['MissingSurface']
    },
    boundaryOwners: {
      realObjectIconOwner: 'GameObjectIcon',
      materialOwner: 'MaterialImage',
      statusOwner: 'StatusVisual',
      actionOwner: 'ActionButton',
      evidenceOwner: 'EvidenceLedger',
      chatOwner: 'ChatShell'
    },
    forbiddenOwners: ['StatusBadge', 'status-badge']
  }))

  const result = runPreflight(['--registry-file', registryPath, '--require-ready', '--json'])

  assert.equal(result.status, 17)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'owner_registry_incomplete')
  assert.equal(report.ownerRegistryReady, false)
  assert.ok(report.missingRequirements.includes('surface:simc:owners'))
  assert.ok(report.missingRequirements.some((item) => item.includes('MissingSurface:file:components/missing-surface/missing-surface.wxml')))
})
