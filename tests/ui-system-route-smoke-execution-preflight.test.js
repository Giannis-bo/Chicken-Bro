const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-route-smoke-execution-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-route-smoke-execution-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-route-smoke-execution-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-route-smoke-execution-template/README.md'

const oneByOnePng = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/lP5x3wAAAABJRU5ErkJggg==',
  'base64'
)

const requiredScenes = [
  { id: 'news_home_top', surface: 'news_home', route: '/pages/news/news' },
  { id: 'news_home_scrolled', surface: 'news_home', route: '/pages/news/news' },
  { id: 'news_channel_official', surface: 'news_list_detail', route: '/pages/news/list?type=channel&value=official' },
  { id: 'news_detail_first', surface: 'news_list_detail', route: '/pages/news/detail?id=article-1' },
  { id: 'builds_tab_top', surface: 'builds_tab', route: '/pages/builds/builds' },
  { id: 'builds_spec_switch', surface: 'builds_tab', route: '/pages/builds/builds' },
  { id: 'workbench_ready', surface: 'current_spec_workbench', route: '/pages/builds/workbench?spec=frost' },
  { id: 'workbench_blocked_gear', surface: 'current_spec_workbench', route: '/pages/builds/workbench?spec=frost' },
  { id: 'workbench_partial_talent', surface: 'current_spec_workbench', route: '/pages/builds/workbench?spec=frost' },
  { id: 'workbench_stale', surface: 'current_spec_workbench', route: '/pages/builds/workbench?spec=frost' },
  { id: 'workbench_evidence_expanded', surface: 'current_spec_workbench', route: '/pages/builds/workbench?spec=frost' },
  { id: 'talent_simulator_load', surface: 'talent_simulator', route: '/pages/builds/talent-simulator?spec=frost' },
  { id: 'talent_simulator_missing', surface: 'talent_simulator', route: '/pages/builds/talent-simulator?spec=frost' },
  { id: 'gear_detail_load', surface: 'gear_detail', route: '/pages/builds/detail?query=gear&spec=frost' },
  { id: 'gear_missing_slot', surface: 'gear_detail', route: '/pages/builds/detail?query=gear&spec=frost' },
  { id: 'simc_from_workbench', surface: 'simc', route: '/pages/simulator/simc?from=workbench&spec=frost' },
  { id: 'simc_blocked_templates', surface: 'simc', route: '/pages/simulator/simc?from=workbench&spec=frost' },
  { id: 'smart_analysis_tab', surface: 'simc', route: '/pages/simulator/simulator' },
  { id: 'chickenbro_empty', surface: 'chickenbro', route: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_workbench_context', surface: 'chickenbro', route: '/pages/simulator/chickenbro?from=workbench&spec=frost' },
  { id: 'chickenbro_generating', surface: 'chickenbro', route: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_done', surface: 'chickenbro', route: '/pages/simulator/chickenbro' },
  { id: 'chickenbro_failed', surface: 'chickenbro', route: '/pages/simulator/chickenbro' },
  { id: 'tasks_list', surface: 'tasks', route: '/pages/simulator/tasks?from=builds' },
  { id: 'task_detail', surface: 'tasks', route: '/pages/simulator/task-detail?id=task-1' },
  { id: 'profile_guest', surface: 'profile_templates', route: '/pages/profile/profile' },
  { id: 'profile_templates', surface: 'profile_templates', route: '/pages/profile/profile' }
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

function makeExecutionManifest(mutator) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-route-smoke-execution-'))
  const screenshotsDir = path.join(directory, 'screenshots')
  const componentCropsDir = path.join(directory, 'component-crops')
  const comparisonsDir = path.join(directory, 'comparisons')
  const overlaysDir = path.join(directory, 'overlays')
  const redZonesDir = path.join(directory, 'red-zones')
  for (const subdir of [screenshotsDir, componentCropsDir, comparisonsDir, overlaysDir, redZonesDir]) {
    fs.mkdirSync(subdir, { recursive: true })
  }
  const targetLockDecision = writeText(path.join(directory, 'target-locked-decision.md'), 'target lock')
  const activePermit = writeText(path.join(directory, 'active-permit.md'), 'active permit')
  const devtoolsActionLedgerPath = writeText(path.join(directory, 'devtools-action-ledger.json'), '{}')
  const productionAssetManifestPath = writeText(path.join(directory, 'production-asset-manifest.json'), '{}')
  const scorecardJson = writeText(path.join(directory, 'scorecard.json'), '{}')
  const routeSmokeReport = writeText(path.join(directory, 'route-smoke-report.md'), '# report\n')
  const executionManifestPath = path.join(directory, 'route-smoke-execution-manifest.json')
  const sceneResults = requiredScenes.map((scene) => {
    const screenshotPath = writePng(path.join(screenshotsDir, `${scene.id}.png`))
    const cropPath = writePng(path.join(componentCropsDir, `${scene.id}-crop.png`))
    const comparisonPath = writePng(path.join(comparisonsDir, `${scene.id}.png`))
    const overlayPath = writePng(path.join(overlaysDir, `${scene.id}.png`))
    const redZonePath = writePng(path.join(redZonesDir, `${scene.id}.png`))
    return {
      id: scene.id,
      surface: scene.surface,
      route: scene.route,
      status: 'pass',
      viewports: ['compact', 'standard', 'large'],
      assertions: {
        noFakeChrome: true,
        noHorizontalOverflow: true,
        noForbiddenStrongClaims: true,
        noQuarantineAssets: true,
        safeAreaClear: true,
        longTextFits: true,
        ownerFitRespected: true
      },
      screenshotPath,
      componentCropPaths: [cropPath],
      comparisonPath,
      overlayPath,
      redZonePath,
      routeActions: [
        {
          action: scene.route.startsWith('/pages/profile') || scene.route.endsWith('/news') || scene.route.endsWith('/builds') || scene.route.endsWith('/simulator')
            ? 'switchTab'
            : 'navigateTo',
          route: scene.route
        }
      ],
      visibleStrongClaims: [],
      quarantineAssetReferences: []
    }
  })
  const manifest = {
    status: 'route_smoke_execution_ready',
    schemaVersion: 1,
    targetLockDecision,
    activePermit,
    devtoolsActionLedgerPath,
    productionAssetManifestPath,
    checkedAt: '2026-07-07T00:00:00.000Z',
    captureSafe: true,
    viewportMatrix: ['compact', 'standard', 'large'],
    artifactPaths: {
      manifest: executionManifestPath,
      devtoolsActionLedger: devtoolsActionLedgerPath,
      screenshotsDir,
      componentCropsDir,
      comparisonsDir,
      overlaysDir,
      redZonesDir,
      scorecardJson,
      routeSmokeReport
    },
    scorecard: {
      status: 'pass',
      sceneCount: requiredScenes.length,
      failedScenes: []
    },
    sceneResults
  }
  if (mutator) mutator(manifest)
  fs.writeFileSync(executionManifestPath, JSON.stringify(manifest, null, 2))
  return executionManifestPath
}

test('route smoke execution preflight reports missing runtime execution manifest by default', () => {
  const result = runPreflight(['--require-execution', '--json'])

  assert.equal(result.status, 11)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'route_smoke_execution_missing')
  assert.equal(report.executionManifestExists, false)
  assert.equal(report.routeSmokeExecutionReady, false)
  assert.ok(report.missingRequirements.includes('route_smoke_execution_manifest_file'))
  assert.equal(report.requiredSceneIds.length, 27)
  assert.ok(report.requiredArtifacts.includes('redZonesDir'))
})

test('route smoke execution preflight accepts a complete runtime execution candidate', () => {
  const candidatePath = makeExecutionManifest()
  const result = runPreflight(['--execution-file', candidatePath, '--require-execution', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'route_smoke_execution_ready')
  assert.equal(report.routeSmokeExecutionReady, true)
  assert.equal(report.sceneCount, 27)
  assert.equal(report.captureSafe, true)
  assert.deepEqual(report.missingRequirements, [])
})

test('route smoke execution preflight rejects missing scenes, failed scenes, strong claims and quarantine assets', () => {
  const candidatePath = makeExecutionManifest((manifest) => {
    manifest.sceneResults = manifest.sceneResults.filter((scene) => scene.id !== 'chickenbro_failed')
    manifest.sceneResults[0].status = 'fail'
    manifest.sceneResults[0].visibleStrongClaims = ['DPS']
    manifest.sceneResults[0].quarantineAssetReferences = ['assets/generated/ui-v2-1-slices/pass36/bad.png']
    manifest.sceneResults[0].routeActions.push({
      action: 'cli close',
      route: '/pages/news/news'
    })
    manifest.scorecard.status = 'fail'
    manifest.scorecard.failedScenes = ['news_home_top']
  })
  const result = runPreflight(['--execution-file', candidatePath, '--require-execution', '--json'])

  assert.equal(result.status, 11)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'route_smoke_execution_invalid')
  assert.equal(report.routeSmokeExecutionReady, false)
  assert.ok(report.missingRequirements.includes('sceneResults_missing:chickenbro_failed'))
  assert.ok(report.missingRequirements.includes('sceneResults[0].status_pass'))
  assert.ok(report.missingRequirements.includes('sceneResults[0].visibleStrongClaims_empty'))
  assert.ok(report.missingRequirements.includes('sceneResults[0].visibleStrongClaims_no_forbidden_claims'))
  assert.ok(report.missingRequirements.includes('sceneResults[0].quarantineAssetReferences_empty'))
  assert.ok(report.missingRequirements.includes('sceneResults[0].routeActions_no_forbidden_actions'))
  assert.ok(report.missingRequirements.includes('scorecard.status_pass'))
  assert.ok(report.missingRequirements.includes('scorecard.failedScenes_empty'))
})

test('route smoke execution template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `route_smoke_execution_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-route-smoke-execution-preflight\.js --require-execution --json/)
  assert.match(source, /Current expected exit code without a real runtime execution manifest: `11`/)
  assert.match(source, /"status": "route_smoke_execution_ready"/)
  assert.match(source, /"captureSafe": true/)
  assert.match(source, /`chickenbro_failed`/)
  assert.match(source, /This template can only prove `route_smoke_execution_template_only`/)

  assert.equal(manifest.status, 'route_smoke_execution_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.routeSmokeExecutionExists, false)
  assert.equal(manifest.routeSmokeExecutionReady, false)
  assert.equal(manifest.expectedRequireExecutionExitCode, 11)
  assert.equal(manifest.requiredSceneIds.length, 27)
  assert.ok(manifest.requiredArtifacts.includes('overlaysDir'))
  assert.ok(manifest.requiredAssertions.includes('ownerFitRespected'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /routeSmokeExecutionReady: false/)
})
