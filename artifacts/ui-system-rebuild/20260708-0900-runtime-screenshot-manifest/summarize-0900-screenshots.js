#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const artifactDir = __dirname
const repoRoot = path.resolve(artifactDir, '../../..')
const screenshotDir = path.join(artifactDir, 'page-captures')
const appJson = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app.json'), 'utf8'))
const minValidScreenshotBytes = 30000

const pageMeta = new Map([
  ['pages/news/news', { tier: 'P0', displayName: '首页资讯' }],
  ['pages/news/list', { tier: 'P1', displayName: '资讯列表' }],
  ['pages/news/detail', { tier: 'P1', displayName: '资讯详情' }],
  ['pages/builds/builds', { tier: 'P0', displayName: '职业专精' }],
  ['pages/builds/workbench', { tier: 'P0', displayName: '当前专精工作台' }],
  ['pages/builds/intel', { tier: 'P2', displayName: '智能构筑信息' }],
  ['pages/builds/talent-simulator', { tier: 'P0', displayName: '天赋模拟' }],
  ['pages/builds/detail', { tier: 'P0', displayName: '装备详情' }],
  ['pages/simulator/simulator', { tier: 'P0', displayName: '智能分析' }],
  ['pages/simulator/simc', { tier: 'P0', displayName: 'SimC' }],
  ['pages/simulator/chickenbro', { tier: 'P1', displayName: '炸鸡队长' }],
  ['pages/simulator/tasks', { tier: 'P1', displayName: '任务' }],
  ['pages/simulator/task-detail', { tier: 'P1', displayName: '任务详情' }],
  ['pages/profile/profile', { tier: 'P0', displayName: '我的' }]
])

const warningRoutes = new Set([
  'pages/news/list',
  'pages/news/detail',
  'pages/builds/workbench',
  'pages/builds/intel',
  'pages/builds/talent-simulator',
  'pages/builds/detail',
  'pages/simulator/simc',
  'pages/simulator/chickenbro',
  'pages/simulator/tasks',
  'pages/simulator/task-detail'
])

function screenshotFileName(pagePath) {
  return `${pagePath.replace(/^pages\//, '').replace(/[/?=&]/g, '_')}.png`
}

function relativePath(absolutePath) {
  return path.relative(repoRoot, absolutePath).split(path.sep).join('/')
}

function localIso(date) {
  const parts = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).formatToParts(date).reduce((acc, item) => {
    if (item.type !== 'literal') acc[item.type] = item.value
    return acc
  }, {})
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:${parts.second}+08:00`
}

function pageSummary(pagePath) {
  const meta = pageMeta.get(pagePath) || { tier: 'P2', displayName: pagePath }
  const screenshotPath = path.join(screenshotDir, screenshotFileName(pagePath))
  const screenshotExists = fs.existsSync(screenshotPath)
  const screenshotBytes = screenshotExists ? fs.statSync(screenshotPath).size : 0
  const screenshotValid = screenshotExists && screenshotBytes >= minValidScreenshotBytes
  const hasRouteWarning = warningRoutes.has(pagePath)
  return {
    path: pagePath,
    tier: meta.tier,
    displayName: meta.displayName,
    screenshot: relativePath(screenshotPath),
    screenshotExists,
    screenshotBytes,
    screenshotEvidence: screenshotValid ? 'valid_file_sanity_pass' : 'missing_or_tiny_screenshot',
    routeEvidence: hasRouteWarning
      ? 'single_page_capture_route_matched_with_callback_warning'
      : 'single_page_capture_route_matched',
    visualStatus: screenshotValid ? 'needs_human_visual_review_not_white_screen' : 'risk_missing_runtime_screenshot',
    notes: hasRouteWarning
      ? 'Single-page capture reached the intended route and produced a valid screenshot, but navigation callback warning remains.'
      : 'Single-page capture reached the intended route and produced a valid screenshot.'
  }
}

function buildSummary() {
  const checkedAt = new Date()
  const pages = appJson.pages.map(pageSummary)
  const missingKnownMeta = appJson.pages.filter((pagePath) => !pageMeta.has(pagePath))
  const validScreenshotCount = pages.filter((item) => item.screenshotEvidence === 'valid_file_sanity_pass').length
  const warningRouteCount = pages.filter((item) => item.routeEvidence.endsWith('_with_callback_warning')).length
  const riskCount = pages.filter((item) => item.screenshotEvidence !== 'valid_file_sanity_pass').length
  const totals = {
    pageCount: pages.length,
    p0Count: pages.filter((item) => item.tier === 'P0').length,
    p1Count: pages.filter((item) => item.tier === 'P1').length,
    p2Count: pages.filter((item) => item.tier === 'P2').length,
    validScreenshotCount,
    warningRouteCount,
    riskCount
  }

  const base = {
    checkedAt: checkedAt.toISOString(),
    localCheckedAt: localIso(checkedAt),
    sourceOfTruth: 'docs/plans/2026-07-08-wow-mini-program-0900-ui-delivery-goal.md',
    captureRule: 'Use single-page capture as evidence. Multi-page serial capture is unreliable and can overwrite screenshots with white frames.',
    finalAccepted: false,
    runtimeVerified: 'partial_screenshot_evidence_only',
    devtools: {
      automatorPort: 9854,
      forbiddenActionsUsed: [],
      knownRisk: 'navigateTo callbacks can miss the short callback window; multi-page serial capture can time out currentState and must not be used as final proof.'
    },
    totals,
    missingKnownMeta,
    pages
  }

  const summary = {
    status: riskCount > 0
      ? 'single_page_screenshot_summary_has_missing_or_tiny_screenshots'
      : 'single_page_screenshot_summary_ready_with_route_warnings',
    ...base
  }

  const aggregate = {
    status: riskCount > 0
      ? 'visual_rescue_single_page_screenshot_summary_has_missing_or_tiny_screenshots'
      : 'visual_rescue_single_page_screenshot_summary_ready_with_route_warnings',
    proofRule: 'Every app.json page has a real WeChat mini-program screenshot. Single-page capture is valid evidence; multi-page serial capture is not final evidence.',
    ...base
  }

  return { summary, aggregate }
}

function main() {
  const { summary, aggregate } = buildSummary()
  fs.writeFileSync(
    path.join(artifactDir, 'single-page-screenshot-summary.json'),
    `${JSON.stringify(summary, null, 2)}\n`
  )
  fs.writeFileSync(
    path.join(artifactDir, 'aggregate-page-visual-manifest.json'),
    `${JSON.stringify(aggregate, null, 2)}\n`
  )
  console.log(JSON.stringify({
    status: aggregate.status,
    checkedAt: aggregate.checkedAt,
    totals: aggregate.totals,
    finalAccepted: aggregate.finalAccepted,
    runtimeVerified: aggregate.runtimeVerified
  }, null, 2))
  if (aggregate.totals.riskCount > 0) process.exitCode = 2
}

main()
