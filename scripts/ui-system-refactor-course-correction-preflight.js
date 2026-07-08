#!/usr/bin/env node

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = process.cwd()
const EXIT_NOT_READY = 19
const ACTIVE_PERMIT_PATH = 'docs/plans/2026-07-07-wow-ui-system-news-list-detail-active-implementation-permit.md'
const ACTIVE_SURFACE = 'news_list_detail'

function optionValue(args, name, fallback) {
  const index = args.indexOf(name)
  return index === -1 ? fallback : args[index + 1]
}

function resolvePath(root, filePath) {
  return path.isAbsolute(filePath) ? filePath : path.join(root, filePath)
}

function readJson(root, filePath) {
  return JSON.parse(fs.readFileSync(resolvePath(root, filePath), 'utf8'))
}

function fileExists(root, filePath) {
  return Boolean(filePath) && fs.existsSync(resolvePath(root, filePath))
}

function activeSurfaceFor(root, explicitSurface) {
  if (explicitSurface) return explicitSurface
  return fileExists(root, ACTIVE_PERMIT_PATH) ? ACTIVE_SURFACE : ''
}

function inspectTabBar(root) {
  const missingRequirements = []
  let app
  try {
    app = readJson(root, 'app.json')
  } catch (error) {
    return {
      tabBarIconContractReady: false,
      tabCount: 0,
      missingRequirements: ['app_json_parseable'],
      error: error.message
    }
  }

  const list = app.tabBar && Array.isArray(app.tabBar.list) ? app.tabBar.list : []
  if (!list.length) missingRequirements.push('tabBar.list_non_empty')

  list.forEach((item, index) => {
    const prefix = `tabBar.list[${index}]`
    if (!item.pagePath) missingRequirements.push(`${prefix}.pagePath`)
    if (!item.text) missingRequirements.push(`${prefix}.text`)

    for (const key of ['iconPath', 'selectedIconPath']) {
      const value = item[key]
      if (!value) {
        missingRequirements.push(`${prefix}.${key}`)
        continue
      }
      if (!fileExists(root, value)) missingRequirements.push(`${prefix}.${key}_exists`)
      if (!/^assets\/tabbar\//.test(value)) missingRequirements.push(`${prefix}.${key}_assets_tabbar`)
      if (!/\.(png|jpg|jpeg)$/i.test(value)) missingRequirements.push(`${prefix}.${key}_png_or_jpg`)
    }
  })

  return {
    tabBarIconContractReady: missingRequirements.length === 0,
    tabCount: list.length,
    tabs: list.map((item) => ({
      pagePath: item.pagePath || '',
      text: item.text || '',
      iconPath: item.iconPath || '',
      selectedIconPath: item.selectedIconPath || ''
    })),
    missingRequirements
  }
}

function runPageAdoption(root, surface) {
  const command = ['scripts/ui-system-page-adoption-preflight.js', '--json', '--root', root]
  if (surface) command.push('--surface', surface)
  const result = spawnSync(
    process.execPath,
    command,
    {
      cwd: ROOT,
      encoding: 'utf8'
    }
  )

  let report
  try {
    report = JSON.parse(result.stdout)
  } catch (error) {
    report = {
      status: 'page_adoption_parse_error',
      pageAdoptionReady: false,
      missingRequirements: ['page_adoption_report_json'],
      parseError: error.message,
      rawStdout: result.stdout
    }
  }

  return {
    command: `node ${command.join(' ')}`,
    surface: surface || 'all',
    exitCode: result.status,
    status: report.status || 'unknown',
    pageAdoptionReady: Boolean(report.pageAdoptionReady),
    failingPageCount: report.failingPageCount || 0,
    missingRequirements: report.missingRequirements || [],
    stderr: result.stderr,
    report
  }
}

function buildReport(args) {
  const root = optionValue(args, '--root', ROOT)
  const surface = activeSurfaceFor(root, optionValue(args, '--surface', ''))
  const skipPageAdoption = args.includes('--skip-page-adoption')
  const tabBar = inspectTabBar(root)
  const pageAdoption = skipPageAdoption
    ? {
        status: 'page_adoption_skipped',
        pageAdoptionReady: true,
        failingPageCount: 0,
        missingRequirements: []
      }
    : runPageAdoption(root, surface)

  const missingRequirements = [
    ...tabBar.missingRequirements.map((item) => `native_tab_bar_icon:${item}`),
    ...pageAdoption.missingRequirements.map((item) => `page_adoption:${item}`)
  ]
  const courseCorrectionReady = tabBar.tabBarIconContractReady && pageAdoption.pageAdoptionReady

  return {
    status: courseCorrectionReady
      ? 'ui_refactor_course_correction_ready'
      : 'ui_refactor_course_correction_blocked',
    courseCorrectionReady,
    root,
    surface: surface || 'all',
    checks: {
      nativeTabBarIcons: tabBar,
      pageOwnerAdoption: pageAdoption
    },
    missingRequirements,
    requiredCorrections: [
      'Use native app.json tabBar iconPath and selectedIconPath for every fixed bottom tab; do not fake fixed tab icons inside pages.',
      'Route pages must compose AppShell, PageFrame and surface owner components; pages may bind data and handle routes only.',
      'Horizontal gutters, section rhythm, panel geometry, status visuals, action buttons, evidence rows and chat layout must stay inside owner components.',
      'Keep current page/app/navigation edits quarantined until target lock and exactly one active implementation permit exist.'
    ],
    nonPromotion: [
      'not target_locked',
      'not active_implementation_permit',
      'not page_integration',
      'not runtime_verified',
      'not final_accepted'
    ]
  }
}

function main() {
  const args = process.argv.slice(2)
  const flags = new Set(args)
  const report = buildReport(args)

  if (flags.has('--json')) {
    process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
  } else {
    process.stdout.write(`status=${report.status}\n`)
    process.stdout.write(`courseCorrectionReady=${report.courseCorrectionReady}\n`)
    process.stdout.write(`tabBarIconContractReady=${report.checks.nativeTabBarIcons.tabBarIconContractReady}\n`)
    process.stdout.write(`pageAdoptionReady=${report.checks.pageOwnerAdoption.pageAdoptionReady}\n`)
    if (report.missingRequirements.length) {
      process.stdout.write(`missingRequirements=${report.missingRequirements.join(',')}\n`)
    }
  }

  if (flags.has('--require-ready') && !report.courseCorrectionReady) {
    process.exitCode = EXIT_NOT_READY
  }
}

main()
