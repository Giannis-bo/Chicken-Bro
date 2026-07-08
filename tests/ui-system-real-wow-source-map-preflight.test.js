const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-real-wow-source-map-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-real-wow-source-map-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-real-wow-source-map-template/README.md'

const requiredEntityTypes = [
  'class',
  'spec',
  'hero',
  'talent',
  'spell',
  'item',
  'source',
  'dungeon',
  'raid',
  'affix'
]

const requiredSurfaces = [
  'news_home',
  'news_list_detail',
  'builds_tab',
  'current_spec_workbench',
  'talent_simulator',
  'gear_detail',
  'simc',
  'chickenbro',
  'tasks',
  'profile_templates'
]

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

function read(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function readJson(filePath) {
  return JSON.parse(read(filePath))
}

function makeSourceMap(mutator = (manifest) => manifest) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-real-source-map-'))
  const sourceMapPath = path.join(directory, 'real-wow-source-map.json')
  const manifest = {
    status: 'real_wow_source_map_ready',
    schemaVersion: 1,
    targetLockDecision: 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md',
    activePermit: 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md',
    checkedAt: '2026-07-07T00:00:00.000Z',
    sourceMaps: requiredEntityTypes.map((entityType, index) => ({
      id: `${entityType}-source`,
      entityType,
      sourceClass: index % 3 === 0 ? 'api' : index % 3 === 1 ? 'battlenet' : 'websim',
      owner: 'GameObjectIcon',
      allowedSurfaces: [requiredSurfaces[index]],
      payloadField: `payload.${entityType}.gameAsset.iconUrl`,
      contractReference: index % 3 === 0
        ? 'pages/common/game-asset.js'
        : index % 3 === 1
          ? 'server/websim_payload.py game_asset_from_icon_url'
          : 'server/news_backend.py /api/websim/assets',
      requiredFields: ['entityType', 'entityId', 'iconUrl', 'source', 'status'],
      fallback: 'text_fallback',
      status: 'source_map_ready',
      generatedByImagegen: false,
      containsGeneratedObject: false
    }))
  }
  fs.writeFileSync(sourceMapPath, JSON.stringify(mutator(manifest), null, 2))
  return sourceMapPath
}

test('real WoW source-map preflight reports missing runtime source map by default', () => {
  const result = runPreflight(['--require-source-map', '--json'])

  assert.equal(result.status, 15)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'real_wow_source_map_missing')
  assert.equal(report.sourceMapExists, false)
  assert.equal(report.sourceMapReady, false)
  assert.ok(report.missingRequirements.includes('real_wow_source_map_file'))
  assert.ok(report.requiredEntityTypes.includes('talent'))
  assert.ok(report.requiredSurfaces.includes('current_spec_workbench'))
  assert.ok(report.forbiddenSourceClasses.includes('imagegen'))
})

test('real WoW source-map preflight accepts a complete source-map candidate', () => {
  const candidatePath = makeSourceMap()
  const result = runPreflight(['--source-map-file', candidatePath, '--require-source-map', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'real_wow_source_map_ready')
  assert.equal(report.sourceMapReady, true)
  assert.equal(report.sourceMapCount, requiredEntityTypes.length)
  assert.deepEqual(report.missingRequirements, [])
  assert.ok(report.coveredEntityTypes.includes('item'))
  assert.ok(report.coveredSurfaces.includes('profile_templates'))
})

test('real WoW source-map preflight rejects imagegen and page-private object sources', () => {
  const candidatePath = makeSourceMap((manifest) => {
    manifest.sourceMaps[0].sourceClass = 'imagegen'
    manifest.sourceMaps[0].generatedByImagegen = true
    manifest.sourceMaps[0].containsGeneratedObject = true
    manifest.sourceMaps[0].owner = 'MaterialImage'
    manifest.sourceMaps[0].payloadField = ''
    return manifest
  })
  const result = runPreflight(['--source-map-file', candidatePath, '--require-source-map', '--json'])

  assert.equal(result.status, 15)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'real_wow_source_map_invalid')
  assert.equal(report.sourceMapReady, false)
  assert.ok(report.missingRequirements.includes('sourceMaps[0].sourceClass_not_forbidden'))
  assert.ok(report.missingRequirements.includes('sourceMaps[0].sourceClass_allowed'))
  assert.ok(report.missingRequirements.includes('sourceMaps[0].owner_GameObjectIcon'))
  assert.ok(report.missingRequirements.includes('sourceMaps[0].generatedByImagegen_false'))
  assert.ok(report.missingRequirements.includes('sourceMaps[0].containsGeneratedObject_false'))
})

test('real WoW source-map template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `real_wow_source_map_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-real-wow-source-map-preflight\.js --require-source-map --json/)
  assert.match(source, /Current expected exit code without a real source map: `15`/)
  assert.match(source, /sourceClass.*api.*battlenet.*websim.*repo_verified.*user_provided/s)
  assert.match(source, /imagegen/)
  assert.match(source, /This template can only prove `real_wow_source_map_template_only`/)

  assert.equal(manifest.status, 'real_wow_source_map_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.sourceMapExists, false)
  assert.equal(manifest.sourceMapReady, false)
  assert.equal(manifest.expectedRequireSourceMapExitCode, 15)
  assert.ok(manifest.requiredEntityTypes.includes('affix'))
  assert.ok(manifest.requiredSurfaces.includes('gear_detail'))
  assert.ok(manifest.forbiddenSourceClasses.includes('imagegen'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /sourceMapReady: false/)
})
