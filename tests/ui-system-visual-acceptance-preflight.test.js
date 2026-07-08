const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-visual-acceptance-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-visual-acceptance-scorecard-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-visual-acceptance-scorecard-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-visual-acceptance-scorecard-template/README.md'

const oneByOnePng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lP5x3wAAAABJRU5ErkJggg==',
  'base64'
)

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

function writeText(filePath, text = '') {
  fs.writeFileSync(filePath, text)
  return filePath
}

function writePng(filePath) {
  fs.writeFileSync(filePath, oneByOnePng)
  return filePath
}

function makeScorecard(mutator) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-visual-scorecard-'))
  const targetLockDecision = writeText(path.join(directory, 'target-locked-decision.md'), 'target lock')
  const activePermit = writeText(path.join(directory, 'active-permit.md'), 'active permit')
  const routeSmokeExecutionManifest = writeText(path.join(directory, 'route-smoke-execution-manifest.json'), '{}')
  const productionAssetManifestPath = writeText(path.join(directory, 'production-asset-manifest.json'), '{}')
  const scorecardPath = path.join(directory, 'visual-acceptance-scorecard.json')
  const image = (name) => writePng(path.join(directory, `${name}.png`))
  const surfaces = requiredSurfaces.map((surface) => ({
    id: surface,
    status: 'pass',
    score: 92,
    viewports: ['compact', 'standard', 'large'],
    currentScreenshotPath: image(`${surface}-current`),
    targetImagePath: image(`${surface}-target`),
    implementationScreenshotPath: image(`${surface}-implementation`),
    comparisonPath: image(`${surface}-comparison`),
    overlayPath: image(`${surface}-overlay`),
    redZonePath: image(`${surface}-red-zone`),
    componentCrops: [
      {
        component: `${surface}-primary-owner`,
        owner: `${surface}-primary-owner`,
        status: 'pass',
        score: 93,
        currentCropPath: image(`${surface}-component-current`),
        targetCropPath: image(`${surface}-component-target`),
        implementationCropPath: image(`${surface}-component-implementation`),
        overlayPath: image(`${surface}-component-overlay`),
        redZonePath: image(`${surface}-component-red-zone`),
        redZones: []
      }
    ],
    metrics: {
      gutterDeltaPxMax: 2,
      slotDeltaPxMax: 2,
      glyphCenterDeltaPxMax: 1,
      textOverflowCount: 0,
      horizontalOverflowCount: 0,
      fakeChromeCount: 0,
      blockingRedZoneCount: 0
    }
  }))
  const scorecard = {
    status: 'visual_acceptance_scorecard_ready',
    schemaVersion: 1,
    targetLockDecision,
    activePermit,
    routeSmokeExecutionManifest,
    productionAssetManifestPath,
    checkedAt: '2026-07-07T00:00:00.000Z',
    source: 'real_miniprogram_runtime',
    captureSafe: true,
    minSurfaceScore: 90,
    minComponentScore: 90,
    requiredViewports: ['compact', 'standard', 'large'],
    failedSurfaces: [],
    blockingRedZones: [],
    surfaces
  }
  if (mutator) mutator(scorecard)
  fs.writeFileSync(scorecardPath, JSON.stringify(scorecard, null, 2))
  return scorecardPath
}

test('visual acceptance preflight reports missing runtime scorecard by default', () => {
  const result = runPreflight(['--require-scorecard', '--json'])

  assert.equal(result.status, 13)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'visual_acceptance_scorecard_missing')
  assert.equal(report.scorecardExists, false)
  assert.equal(report.visualAcceptanceReady, false)
  assert.ok(report.missingRequirements.includes('visual_acceptance_scorecard_file'))
  assert.equal(report.requiredSurfaces.length, 10)
  assert.equal(report.minSurfaceScore, 90)
})

test('visual acceptance preflight accepts a complete runtime scorecard candidate', () => {
  const scorecardPath = makeScorecard()
  const result = runPreflight(['--scorecard-file', scorecardPath, '--require-scorecard', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'visual_acceptance_scorecard_ready')
  assert.equal(report.visualAcceptanceReady, true)
  assert.equal(report.surfaceCount, 10)
  assert.deepEqual(report.missingRequirements, [])
})

test('visual acceptance preflight rejects weak scorecards and blocking red-zones', () => {
  const scorecardPath = makeScorecard((scorecard) => {
    scorecard.surfaces = scorecard.surfaces.filter((surface) => surface.id !== 'chickenbro')
    scorecard.surfaces[0].status = 'fail'
    scorecard.surfaces[0].score = 87
    scorecard.surfaces[0].metrics.textOverflowCount = 1
    scorecard.surfaces[0].metrics.blockingRedZoneCount = 1
    scorecard.surfaces[0].componentCrops[0].status = 'fail'
    scorecard.surfaces[0].componentCrops[0].score = 84
    scorecard.surfaces[0].componentCrops[0].redZones = [
      {
        owner: 'RankedFeed',
        issue: 'row gutter outside target'
      }
    ]
    scorecard.failedSurfaces = ['news_home']
    scorecard.blockingRedZones = ['news_home:RankedFeed']
  })
  const result = runPreflight(['--scorecard-file', scorecardPath, '--require-scorecard', '--json'])

  assert.equal(result.status, 13)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'visual_acceptance_scorecard_invalid')
  assert.equal(report.visualAcceptanceReady, false)
  assert.ok(report.missingRequirements.includes('surfaces_missing:chickenbro'))
  assert.ok(report.missingRequirements.includes('surfaces[0].status_pass'))
  assert.ok(report.missingRequirements.includes('surfaces[0].score_gte_90'))
  assert.ok(report.missingRequirements.includes('surfaces[0].metrics.textOverflowCount_within_0'))
  assert.ok(report.missingRequirements.includes('surfaces[0].metrics.blockingRedZoneCount_within_0'))
  assert.ok(report.missingRequirements.includes('surfaces[0].componentCrops[0].status_pass'))
  assert.ok(report.missingRequirements.includes('surfaces[0].componentCrops[0].score_gte_90'))
  assert.ok(report.missingRequirements.includes('surfaces[0].componentCrops[0].redZones_empty_for_pass'))
  assert.ok(report.missingRequirements.includes('failedSurfaces_empty'))
  assert.ok(report.missingRequirements.includes('blockingRedZones_empty'))
})

test('visual acceptance scorecard template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `visual_acceptance_scorecard_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-visual-acceptance-preflight\.js --require-scorecard --json/)
  assert.match(source, /Current expected exit code without a real runtime scorecard: `13`/)
  assert.match(source, /"status": "visual_acceptance_scorecard_ready"/)
  assert.match(source, /"source": "real_miniprogram_runtime"/)
  assert.match(source, /"minSurfaceScore": 90/)
  assert.match(source, /`current_spec_workbench`/)
  assert.match(source, /This template can only prove `visual_acceptance_scorecard_template_only`/)

  assert.equal(manifest.status, 'visual_acceptance_scorecard_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.visualAcceptanceScorecardExists, false)
  assert.equal(manifest.visualAcceptanceReady, false)
  assert.equal(manifest.expectedRequireScorecardExitCode, 13)
  assert.equal(manifest.requiredSurfaces.length, 10)
  assert.equal(manifest.minSurfaceScore, 90)
  assert.equal(manifest.maxDeltas.glyphCenterDeltaPxMax, 1)
  assert.ok(manifest.requiredEvidencePerSurface.includes('red-zone image'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /visualAcceptanceReady: false/)
})
