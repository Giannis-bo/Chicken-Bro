const test = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const preflightScript = 'scripts/ui-system-refactor-course-correction-preflight.js'

function runPreflight(args = []) {
  return spawnSync(process.execPath, [preflightScript, ...args], {
    encoding: 'utf8'
  })
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

test('course correction preflight passes the confirmed delivery convergence slice', () => {
  const result = runPreflight(['--require-ready', '--json'])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_refactor_course_correction_ready')
  assert.equal(report.courseCorrectionReady, true)
  assert.equal(report.surface, 'news_list_detail')
  assert.equal(report.checks.nativeTabBarIcons.tabBarIconContractReady, true)
  assert.equal(report.checks.pageOwnerAdoption.pageAdoptionReady, true)
  assert.deepEqual(report.missingRequirements, [])
  assert.ok(report.requiredCorrections.some((item) => /native app\.json tabBar iconPath/.test(item)))
  assert.ok(report.requiredCorrections.some((item) => /AppShell, PageFrame and surface owner components/.test(item)))
  assert.ok(report.nonPromotion.includes('not runtime_verified'))
})

test('course correction preflight accepts native tab icons when files are present', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-course-correction-'))
  const iconPaths = [
    'assets/tabbar/news.png',
    'assets/tabbar/news-active.png',
    'assets/tabbar/builds.png',
    'assets/tabbar/builds-active.png'
  ]
  iconPaths.forEach((iconPath) => {
    fs.mkdirSync(path.dirname(path.join(directory, iconPath)), { recursive: true })
    fs.writeFileSync(path.join(directory, iconPath), '')
  })
  writeJson(path.join(directory, 'app.json'), {
    tabBar: {
      list: [
        {
          pagePath: 'pages/news/news',
          text: '最新资讯',
          iconPath: 'assets/tabbar/news.png',
          selectedIconPath: 'assets/tabbar/news-active.png'
        },
        {
          pagePath: 'pages/builds/builds',
          text: '职业专精',
          iconPath: 'assets/tabbar/builds.png',
          selectedIconPath: 'assets/tabbar/builds-active.png'
        }
      ]
    }
  })

  const result = runPreflight([
    '--require-ready',
    '--json',
    '--root',
    directory,
    '--skip-page-adoption'
  ])

  assert.equal(result.status, 0)
  assert.equal(result.stderr, '')

  const report = JSON.parse(result.stdout)
  assert.equal(report.status, 'ui_refactor_course_correction_ready')
  assert.equal(report.courseCorrectionReady, true)
  assert.equal(report.checks.nativeTabBarIcons.tabBarIconContractReady, true)
  assert.equal(report.checks.nativeTabBarIcons.tabCount, 2)
})
