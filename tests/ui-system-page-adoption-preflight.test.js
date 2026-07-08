const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-page-adoption-preflight.js'
const templatePath = 'docs/design/2026-07-07-wow-ui-system-page-adoption-preflight-template.md'
const manifestPath = 'artifacts/ui-system-rebuild/20260707-page-adoption-preflight-template/manifest.json'
const readmePath = 'artifacts/ui-system-rebuild/20260707-page-adoption-preflight-template/README.md'

const pageSpecs = [
  ['pages/news/news', ['app-shell', 'page-frame', 'channel-dock', 'ranked-feed']],
  ['pages/news/list', ['app-shell', 'page-frame', 'article-list-board']],
  ['pages/news/detail', ['app-shell', 'page-frame', 'article-reader']],
  ['pages/builds/builds', ['app-shell', 'page-frame', 'builds-tab-surface']],
  ['pages/builds/workbench', ['app-shell', 'page-frame', 'workbench-cockpit-surface']],
  ['pages/builds/talent-simulator', ['app-shell', 'page-frame', 'talent-tree-canvas']],
  ['pages/builds/detail', ['app-shell', 'page-frame', 'gear-loadout-board', 'gear-config-sheet']],
  ['pages/simulator/simc', ['app-shell', 'page-frame', 'wow-panel', 'evidence-ledger', 'action-button', 'module-card']],
  ['pages/simulator/simulator', ['app-shell', 'page-frame', 'chickenbro-coach-surface', 'chat-shell']],
  ['pages/simulator/chickenbro', ['app-shell', 'page-frame', 'chickenbro-coach-surface', 'chat-shell']],
  ['pages/simulator/tasks', ['app-shell', 'page-frame', 'task-queue-board']],
  ['pages/simulator/task-detail', ['app-shell', 'page-frame', 'task-result-report']],
  ['pages/profile/profile', ['app-shell', 'page-frame', 'profile-identity-panel', 'template-library-board']]
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

function componentPath(component) {
  return `/components/${component}/${component}`
}

function writePage(root, page, components, wxmlOverride) {
  const directory = path.join(root, path.dirname(page))
  fs.mkdirSync(directory, { recursive: true })
  const usingComponents = Object.fromEntries(components.map((component) => [component, componentPath(component)]))
  const body = components
    .filter((component) => component !== 'app-shell' && component !== 'page-frame')
    .map((component) => `    <${component} bind:tap="noop"></${component}>`)
    .join('\n')
  const wxml = wxmlOverride || `<app-shell surface="test">\n  <page-frame title="测试">\n${body}\n  </page-frame>\n</app-shell>\n`
  fs.writeFileSync(path.join(root, `${page}.json`), JSON.stringify({ usingComponents }, null, 2))
  fs.writeFileSync(path.join(root, `${page}.wxml`), wxml)
  fs.writeFileSync(path.join(root, `${page}.wxss`), '/* page composition only */\n')
}

function makeRoot(mutator) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-page-adoption-'))
  for (const [page, components] of pageSpecs) {
    writePage(root, page, components)
  }
  if (mutator) mutator(root)
  return root
}

test('page adoption preflight reports current source pages are not vNext-adopted', () => {
  const result = runPreflight(['--require-adoption', '--json'])

  assert.equal(result.status, 12)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'page_adoption_invalid')
  assert.equal(report.pageAdoptionReady, false)
  assert.equal(report.pageCount, 13)
  assert.ok(report.failingPageCount > 0)
  assert.ok(report.missingRequirements.includes('page_adoption_not_ready'))
})

test('page adoption preflight accepts pages that only compose required owner components', () => {
  const root = makeRoot()
  const result = runPreflight(['--root', root, '--require-adoption', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'page_adoption_ready')
  assert.equal(report.pageAdoptionReady, true)
  assert.equal(report.failingPageCount, 0)
  assert.deepEqual(report.missingRequirements, [])
})

test('page adoption preflight rejects legacy page geometry and direct generated assets', () => {
  const root = makeRoot((fixtureRoot) => {
    writePage(
      fixtureRoot,
      'pages/builds/workbench',
      ['app-shell', 'page-frame', 'workbench-cockpit-surface', 'status-badge'],
      `<view class="page-shell workbench-shell verdict-slab pass37-page-frame">\n  <image class="surface-material" src="/assets/generated/ui-v2-1-slices/pass36/bad.png"></image>\n  <status-badge></status-badge>\n</view>\n`
    )
  })
  const result = runPreflight(['--root', root, '--require-adoption', '--json'])

  assert.equal(result.status, 12)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  const workbench = report.pages.find((page) => page.page === 'pages/builds/workbench')
  assert.equal(report.status, 'page_adoption_invalid')
  assert.equal(workbench.pageAdoptionReady, false)
  assert.ok(workbench.violations.includes('wxml_tag_missing:app-shell'))
  assert.ok(workbench.violations.includes('wxml_tag_missing:page-frame'))
  assert.ok(workbench.violations.includes('wxml_tag_missing:workbench-cockpit-surface'))
  assert.ok(workbench.violations.some((violation) => violation.startsWith('forbidden_component:status-badge')))
  assert.ok(workbench.violations.some((violation) => violation.startsWith('page_private_geometry_classes:')))
  assert.ok(workbench.violations.some((violation) => violation.startsWith('forbidden_generated_or_reference_asset:')))
  assert.ok(workbench.violations.includes('direct_image_tags:1'))
})

test('page adoption preflight template remains template-only and non-runtime', () => {
  const source = read(templatePath)
  const manifest = readJson(manifestPath)
  const readme = read(readmePath)

  assert.match(source, /^Status: `page_adoption_preflight_template_only`$/m)
  assert.match(source, /node scripts\/ui-system-page-adoption-preflight\.js --require-adoption --json/)
  assert.match(source, /Current expected exit code before permitted page integration: `12`/)
  assert.match(source, /`pages\/builds\/workbench` \| `app-shell`, `page-frame`, `workbench-cockpit-surface`/)
  assert.match(source, /avoid legacy `status-badge`/)
  assert.match(source, /This template can only prove `page_adoption_preflight_template_only`/)

  assert.equal(manifest.status, 'page_adoption_preflight_template_only')
  assert.equal(manifest.preflightScript, preflightScript)
  assert.equal(manifest.pageAdoptionReady, false)
  assert.equal(manifest.expectedRequireAdoptionExitCode, 12)
  assert.equal(manifest.pageCount, 13)
  assert.ok(manifest.requiredPages.includes('pages/simulator/chickenbro'))
  assert.ok(manifest.forbiddenPagePatterns.includes('status-badge'))
  assert.ok(manifest.nonPromotion.includes('not runtime_verified'))

  assert.match(readme, /pageAdoptionReady: false/)
})
