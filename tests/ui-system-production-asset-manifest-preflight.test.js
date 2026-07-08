const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-production-asset-manifest-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-production-asset-manifest-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-production-asset-manifest-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-production-asset-manifest-template/README.md'

const oneByOnePng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lP5x3wAAAABJRU5ErkJggg==',
  'base64'
)

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

function makeManifest(source) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-prod-asset-manifest-'))
  const assetPath = path.join(directory, 'news_panel_shell.png')
  fs.writeFileSync(assetPath, oneByOnePng)
  const manifest = typeof source === 'function' ? source(assetPath) : source
  const manifestPath = path.join(directory, 'production-asset-manifest.json')
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2))
  return manifestPath
}

function validManifest(assetPath) {
  return {
    status: 'production_asset_manifest_ready',
    schemaVersion: 1,
    targetLockDecision: 'docs/design/2026-07-07-wow-ui-system-target-locked-decision.md',
    activePermit: 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md',
    checkedAt: '2026-07-07T00:00:00.000Z',
    packageBudget: {
      currentKb: 1,
      maxKb: 2048
    },
    assets: [
      {
        id: 'news_panel_shell',
        class: 'panel',
        owner: 'WowPanel',
        path: assetPath,
        width: 1,
        height: 1,
        sizeKb: 0.1,
        fit: 'nine_slice',
        allowedSurfaces: ['news_home', 'news_list_detail'],
        sourceType: 'imagegen_low_semantic',
        containsText: false,
        containsFakeChrome: false,
        containsRealWowObject: false,
        containsSourceLogo: false,
        containsBusinessConclusion: false
      }
    ],
    realObjectSourceMap: [
      {
        entityType: 'spec',
        sourceClass: 'api',
        owner: 'GameObjectIcon',
        requiredFields: 'entityType,entityId,iconUrl,source,status',
        fallback: 'localized initials',
        status: 'source_map_ready'
      }
    ],
    quarantine: [
      {
        path: 'assets/generated/ui-v2-1-slices/20260703/*pass36*',
        class: 'pass-named asset pending recut',
        reason: 'old pass evidence cannot enter runtime by filename inertia'
      }
    ]
  }
}

test('production asset manifest preflight reports missing runtime manifest by default', () => {
  const result = runPreflight(['--require-production-manifest', '--json'])

  assert.equal(result.status, 10)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'production_asset_manifest_missing')
  assert.equal(report.manifestExists, false)
  assert.equal(report.productionManifestReady, false)
  assert.ok(report.missingRequirements.includes('production_asset_manifest_file'))
  assert.ok(report.allowedClasses.includes('state-atomic'))
})

test('production asset manifest preflight accepts a complete low-semantic material candidate', () => {
  const candidatePath = makeManifest(validManifest)
  const result = runPreflight(['--manifest-file', candidatePath, '--require-production-manifest', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'production_asset_manifest_ready')
  assert.equal(report.productionManifestReady, true)
  assert.equal(report.assetCount, 1)
  assert.equal(report.realSourceCount, 1)
  assert.equal(report.quarantineCount, 1)
  assert.deepEqual(report.missingRequirements, [])
})

test('production asset manifest preflight rejects generated facts and quarantine paths', () => {
  const candidatePath = makeManifest((assetPath) => {
    const manifest = validManifest(assetPath)
    manifest.assets[0].containsRealWowObject = true
    manifest.assets[0].path = 'assets/generated/ui-v2-1-slices/20260703/news_tab_icon_pass36.png'
    manifest.realObjectSourceMap[0].sourceClass = 'imagegen'
    manifest.realObjectSourceMap[0].owner = 'MaterialImage'
    return manifest
  })
  const result = runPreflight(['--manifest-file', candidatePath, '--require-production-manifest', '--json'])

  assert.equal(result.status, 10)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'production_asset_manifest_invalid')
  assert.equal(report.productionManifestReady, false)
  assert.ok(report.missingRequirements.includes('assets[0].containsRealWowObject_false'))
  assert.ok(report.missingRequirements.includes('assets[0].path_not_quarantine_or_reference'))
  assert.ok(report.missingRequirements.includes('assets[0].file_exists'))
  assert.ok(report.missingRequirements.includes('realObjectSourceMap[0].sourceClass_not_forbidden'))
  assert.ok(report.missingRequirements.includes('realObjectSourceMap[0].owner_GameObjectIcon'))
})

test('production asset manifest template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `production_asset_manifest_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-production-asset-manifest-preflight\.js --require-production-manifest --json/)
  assert.match(source, /Current expected exit code without a real production manifest: `10`/)
  assert.match(source, /"sourceType": "imagegen_low_semantic"/)
  assert.match(source, /containsRealWowObject/)
  assert.match(source, /Forbidden source classes: `imagegen`, `target_screenshot_crop`, `random_cdn_without_mapping`, `generated_product_glyph`, `page_private_fallback_art`/)
  assert.match(source, /This template can only prove `production_asset_manifest_template_only`/)

  assert.equal(manifest.status, 'production_asset_manifest_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.productionManifestExists, false)
  assert.equal(manifest.productionManifestReady, false)
  assert.equal(manifest.expectedRequireProductionManifestExitCode, 10)
  assert.ok(manifest.allowedClasses.includes('panel'))
  assert.ok(manifest.forbiddenRealSourceClasses.includes('imagegen'))
  assert.equal(manifest.sizeBudgetKb.socketOrState, 96)

  assert.match(readme, /productionManifestReady: false/)
})
