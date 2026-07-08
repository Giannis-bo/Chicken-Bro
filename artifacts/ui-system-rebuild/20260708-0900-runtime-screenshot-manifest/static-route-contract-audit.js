#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const artifactDir = __dirname
const repoRoot = path.resolve(artifactDir, '../../..')

function read(relativePath) {
  return fs.readFileSync(path.join(repoRoot, relativePath), 'utf8')
}

function includesAll(text, snippets) {
  return snippets.every((snippet) => text.includes(snippet))
}

const appJson = JSON.parse(read('app.json'))
const files = {
  builds: read('pages/builds/builds.js'),
  workbench: read('pages/builds/workbench.js'),
  detail: read('pages/builds/detail.js'),
  tabbar: read('custom-tab-bar/index.js')
}

const checks = [
  {
    id: 'app_pages_registered',
    status: appJson.pages.length === 14 ? 'pass' : 'fail',
    evidence: `app.json pages=${appJson.pages.length}`
  },
  {
    id: 'native_custom_tabbar_routes',
    status: includesAll(JSON.stringify(appJson.tabBar || {}), [
      'pages/news/news',
      'pages/builds/builds',
      'pages/simulator/simulator',
      'pages/profile/profile'
    ]) ? 'pass' : 'fail',
    evidence: 'app.json custom tabBar contains news/builds/simulator/profile routes'
  },
  {
    id: 'custom_tabbar_switches_to_dataset_path',
    status: includesAll(files.tabbar, [
      'data: {',
      'TAB_LIST',
      'wx.switchTab({ url: path })'
    ]) ? 'pass' : 'fail',
    evidence: 'custom-tab-bar/index.js maps TAB_LIST and switches to tapped path'
  },
  {
    id: 'builds_to_workbench',
    status: includesAll(files.builds, [
      'openWorkbench()',
      'wx.navigateTo({',
      '/pages/builds/workbench?spec='
    ]) ? 'pass' : 'fail',
    evidence: 'pages/builds/builds.js openWorkbench navigates to workbench with spec'
  },
  {
    id: 'builds_quick_actions',
    status: includesAll(files.builds, [
      '/pages/builds/talent-simulator',
      '/pages/simulator/simc?from=builds',
      '/pages/simulator/tasks?from=builds',
      '/pages/builds/detail?query='
    ]) ? 'pass' : 'fail',
    evidence: 'pages/builds/builds.js quick actions route to talent/simc/tasks/detail'
  },
  {
    id: 'workbench_primary_action_dispatch',
    status: includesAll(files.workbench, [
      'openPrimaryAction()',
      'this.openActionByKey(action.key)',
      'openActionByKey(key)'
    ]) ? 'pass' : 'fail',
    evidence: 'pages/builds/workbench.js primary action dispatches through openActionByKey'
  },
  {
    id: 'workbench_module_routes',
    status: includesAll(files.workbench, [
      '/pages/simulator/simc?',
      '/pages/builds/talent-simulator?spec=',
      '/pages/builds/detail?query=gear&spec=',
      '/pages/simulator/chickenbro?',
      "wx.switchTab({ url: '/pages/profile/profile' })"
    ]) ? 'pass' : 'fail',
    evidence: 'pages/builds/workbench.js routes simc/talents/gear/chickenbro/profile'
  },
  {
    id: 'gear_detail_to_simc',
    status: includesAll(files.detail, [
      'openSimcWithBuildContext()',
      'wx.setStorageSync(SIMC_BUILD_CONTEXT_STORAGE_KEY, context)',
      '/pages/simulator/simc?from=builds&spec='
    ]) ? 'pass' : 'fail',
    evidence: 'pages/builds/detail.js stores context and navigates to SimC'
  }
]

const failed = checks.filter((check) => check.status !== 'pass')
const manifest = {
  status: failed.length ? 'static_route_contract_has_failures' : 'static_route_contract_passed',
  checkedAt: new Date().toISOString(),
  note: 'Static route contract only verifies source-level route wiring. It does not replace real mini-program screenshots or runtime route smoke.',
  checks,
  failedCount: failed.length
}

fs.writeFileSync(
  path.join(artifactDir, 'static-route-contract-audit.json'),
  `${JSON.stringify(manifest, null, 2)}\n`
)
console.log(JSON.stringify({
  status: manifest.status,
  checkCount: checks.length,
  failedCount: failed.length
}, null, 2))
if (failed.length) process.exitCode = 2
