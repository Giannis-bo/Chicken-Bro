#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram } = require('../../ui-v2-1-strict-restoration/connect-miniprogram-automator')

const artifactDir = __dirname
const repoRoot = path.resolve(artifactDir, '../../..')
const outDir = path.join(artifactDir, 'route-selector-proofs')
const automatorPort = Number(process.env.WECHAT_AUTOMATOR_PORT || 9854)
const wsEndpoint = `ws://127.0.0.1:${automatorPort}`
const appJson = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app.json'), 'utf8'))
const tabRoutes = new Set(((appJson.tabBar && appJson.tabBar.list) || []).map((item) => item.pagePath))

const pageSpecs = [
  {
    path: 'pages/news/news',
    tier: 'P0',
    name: '首页资讯',
    selectors: ['.news-content', '.news-command', '.news-swiper', 'channel-dock', 'ranked-feed']
  },
  {
    path: 'pages/news/list',
    tier: 'P1',
    name: '资讯列表',
    selectors: ['article-list-board', '.article-list-board', '.page-scroll', '.page-content']
  },
  {
    path: 'pages/news/detail',
    tier: 'P1',
    name: '资讯详情',
    query: 'id=blizzard-midnight-revelations-2026-06-03',
    selectors: ['article-reader', '.article-reader', '.page-scroll', '.page-content']
  },
  {
    path: 'pages/builds/builds',
    tier: 'P0',
    name: '职业专精',
    selectors: ['.builds-content', '.builds-spec-console', '.workbench-entry', '.query-section']
  },
  {
    path: 'pages/builds/workbench',
    tier: 'P0',
    name: '当前专精工作台',
    query: 'spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C',
    selectors: ['.workbench-content', '.workbench-cockpit', '.readiness-panel', '.verdict-status-slot', '.module-band']
  },
  {
    path: 'pages/builds/intel',
    tier: 'P2',
    name: '智能构筑信息',
    selectors: ['.page-scroll', '.page-content', '.section', '.intel-card']
  },
  {
    path: 'pages/builds/talent-simulator',
    tier: 'P0',
    name: '天赋模拟',
    selectors: ['.talent-simulator-page', '.talent-page-content', '.talent-toolbar', '.active-tree-panel', '.mobile-action-bar']
  },
  {
    path: 'pages/builds/detail',
    tier: 'P0',
    name: '装备详情',
    query: 'query=gear&spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C',
    selectors: ['.detail-content', '.detail-hero', '.filter-panel', '.gear-panel', '.gear-template-actions']
  },
  {
    path: 'pages/simulator/simulator',
    tier: 'P0',
    name: '智能分析',
    selectors: ['.chickenbro-panel', '.chickenbro-head', '.chickenbro-scroll', '.chickenbro-inputbar']
  },
  {
    path: 'pages/simulator/simc',
    tier: 'P0',
    name: 'SimC',
    selectors: ['.simc-page', '.template-hero', '.identity-selector-row', '.confirm-summary', '.submit-bar']
  },
  {
    path: 'pages/simulator/chickenbro',
    tier: 'P1',
    name: '炸鸡队长',
    selectors: ['.chickenbro-panel', '.chickenbro-head', '.chickenbro-scroll', '.chickenbro-inputbar']
  },
  {
    path: 'pages/simulator/tasks',
    tier: 'P1',
    name: '任务',
    selectors: ['.task-list-page', '.page-scroll', '.task-card', '.task-list']
  },
  {
    path: 'pages/simulator/task-detail',
    tier: 'P1',
    name: '任务详情',
    selectors: ['.task-detail-page', '.page-scroll', '.task-detail-card', '.result-panel']
  },
  {
    path: 'pages/profile/profile',
    tier: 'P0',
    name: '我的',
    selectors: ['.profile-page', '.profile-cockpit', '.profile-identity-row', '.profile-signal-strip', '.template-module-list']
  }
]

const selectedRoute = String(process.env.WOW_0900_PROOF_PAGE || '').trim()
const selectedSpecs = selectedRoute
  ? pageSpecs.filter((item) => item.path === selectedRoute)
  : pageSpecs
const allowBatch = process.env.WOW_0900_ALLOW_PROOF_BATCH === '1'

if (!selectedRoute && !allowBatch) {
  console.error([
    'Refusing to run a 14-page proof batch by default.',
    'Use WOW_0900_PROOF_PAGE=<route> for one short route/selector proof.',
    'Set WOW_0900_ALLOW_PROOF_BATCH=1 only when explicitly accepting DevTools risk.',
    'This script does not screenshot, close, restart, clear cache, switch appid, switch project, or delete user data.'
  ].join('\n'))
  process.exit(2)
}

if (!selectedSpecs.length) {
  console.error(`Unknown route for WOW_0900_PROOF_PAGE: ${selectedRoute}`)
  process.exit(2)
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function withTimeout(promise, ms, label) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

function safeId(route) {
  return route.replace(/^pages\//, '').replace(/[/?=&]/g, '_')
}

function urlFor(spec) {
  return `/${spec.path}${spec.query ? `?${spec.query}` : ''}`
}

async function automatorRouteCall(miniProgram, methodName, url) {
  try {
    await withTimeout(miniProgram[methodName](url), 5000, `automator ${methodName} ${url}`)
    return { ok: true, warning: '' }
  } catch (error) {
    return { ok: false, error: error && error.message ? error.message : String(error) }
  }
}

async function currentState(miniProgram) {
  return withTimeout(
    miniProgram.evaluate(() => {
      const pages = getCurrentPages()
      const page = pages[pages.length - 1]
      return {
        route: page ? page.route : '',
        loading: !!(page && page.data && page.data.loading),
        title: page && page.data ? page.data.navTitle || page.data.title || '' : '',
        pagesLength: pages.length
      }
    }),
    3000,
    'currentState'
  )
}

async function navigate(miniProgram, spec) {
  const url = urlFor(spec)
  const warnings = []
  let error = ''
  if (tabRoutes.has(spec.path)) {
    const result = await automatorRouteCall(miniProgram, 'switchTab', url)
    if (result.warning) warnings.push(result.warning)
    if (result.ok === false) error = result.error || 'switchTab failed'
  } else {
    const home = await automatorRouteCall(miniProgram, 'switchTab', '/pages/news/news')
    if (home.warning) warnings.push(`home:${home.warning}`)
    await wait(350)
    const result = await automatorRouteCall(miniProgram, 'navigateTo', url)
    if (result.warning) warnings.push(result.warning)
    if (result.ok === false) {
      const fallback = await automatorRouteCall(miniProgram, 'redirectTo', url)
      if (fallback.warning) warnings.push(`redirect:${fallback.warning}`)
      if (fallback.ok === false) error = `${result.error || 'navigateTo failed'}; ${fallback.error || 'redirectTo failed'}`
    }
  }
  await wait(spec.settleMs || 1300)
  const state = await currentState(miniProgram).catch((stateError) => ({
    route: '',
    loading: null,
    title: '',
    pagesLength: null,
    stateError: stateError.message
  }))
  return { state, warnings, error: error || state.stateError || '' }
}

async function selectorRects(miniProgram, selectors) {
  return withTimeout(
    miniProgram.evaluate((payload) => new Promise((resolve) => {
      const query = wx.createSelectorQuery()
      payload.selectors.forEach((selector) => query.select(selector).boundingClientRect())
      query.exec((rects) => resolve(rects || []))
    }), { selectors }),
    5200,
    'selector rects'
  )
}

async function tabbarData(miniProgram) {
  return withTimeout(
    miniProgram.evaluate(() => {
      const pages = getCurrentPages()
      const page = pages[pages.length - 1]
      const tabBar = page && typeof page.getTabBar === 'function' ? page.getTabBar() : null
      return {
        hasTabBar: Boolean(tabBar),
        selected: tabBar && tabBar.data ? tabBar.data.selected : null,
        labels: tabBar && tabBar.data && Array.isArray(tabBar.data.list)
          ? tabBar.data.list.map((item) => item.text)
          : []
      }
    }),
    3000,
    'tabbar data'
  ).catch((error) => ({
    hasTabBar: false,
    selected: null,
    labels: [],
    error: error.message
  }))
}

async function proofPage(miniProgram, spec) {
  const startedAt = new Date().toISOString()
  const navigation = await navigate(miniProgram, spec)
  const routeMatches = navigation.state.route === spec.path
  let rects = []
  let selectorError = ''
  if (routeMatches) {
    try {
      rects = await selectorRects(miniProgram, spec.selectors)
    } catch (error) {
      selectorError = error.message
    }
  }
  const selectorResults = spec.selectors.map((selector, index) => ({
    selector,
    rect: rects[index] || null,
    present: Boolean(rects[index] && rects[index].width > 0 && rects[index].height > 0)
  }))
  const presentSelectorCount = selectorResults.filter((item) => item.present).length
  const requiredSelectorCount = Math.min(2, spec.selectors.length)
  const tabs = tabRoutes.has(spec.path) ? await tabbarData(miniProgram) : null
  const passWithoutScreenshot = routeMatches && !navigation.error && !selectorError && presentSelectorCount >= requiredSelectorCount
  return {
    ...spec,
    startedAt,
    finishedAt: new Date().toISOString(),
    status: passWithoutScreenshot
      ? 'route_selector_pass_missing_screenshot'
      : 'route_selector_risk',
    routeAfter: navigation.state.route,
    routeMatches,
    loading: navigation.state.loading,
    title: navigation.state.title,
    pagesLength: navigation.state.pagesLength,
    navigationWarnings: navigation.warnings,
    navigationError: navigation.error,
    selectorError,
    presentSelectorCount,
    requiredSelectorCount,
    selectorResults,
    tabbarData: tabs,
    screenshot: {
      attempted: false,
      status: 'not_attempted_known_App_captureScreenshot_timeout_risk',
      note: '截图 RPC 在本轮多次超时；此 proof 只证明 route 和关键 selector，不能替代真实小程序截图验收。'
    },
    forbiddenActionsUsed: []
  }
}

async function main() {
  fs.mkdirSync(outDir, { recursive: true })
  const { mini, toolInfo } = await connectMiniProgram(wsEndpoint, { timeoutMs: 2400, toolInfoTimeoutMs: 3000 })
  const results = []
  try {
    for (const spec of selectedSpecs) {
      results.push(await proofPage(mini, spec))
    }
  } finally {
    mini.disconnect()
  }
  const manifest = {
    status: results.every((item) => item.status === 'route_selector_pass_missing_screenshot')
      ? 'route_selector_proof_pass_missing_screenshots'
      : 'route_selector_proof_has_risks',
    checkedAt: new Date().toISOString(),
    wsEndpoint,
    toolInfo,
    captureScreenshotUsed: false,
    forbiddenActionsUsed: [],
    pageCount: results.length,
    results
  }
  const manifestPath = selectedRoute
    ? path.join(outDir, `${safeId(selectedRoute)}.json`)
    : path.join(outDir, 'manifest.json')
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  console.log(JSON.stringify({
    status: manifest.status,
    manifestPath,
    pageCount: manifest.pageCount,
    results: results.map((item) => ({
      path: item.path,
      status: item.status,
      routeAfter: item.routeAfter,
      presentSelectorCount: item.presentSelectorCount,
      selectorError: item.selectorError || '',
      navigationError: item.navigationError || ''
    }))
  }, null, 2))
  if (manifest.status === 'route_selector_proof_has_risks') process.exitCode = 2
}

main().catch((error) => {
  fs.mkdirSync(outDir, { recursive: true })
  const manifest = {
    status: 'route_selector_proof_not_completed',
    checkedAt: new Date().toISOString(),
    wsEndpoint,
    selectedRoute,
    captureScreenshotUsed: false,
    forbiddenActionsUsed: [],
    error: error && error.message ? error.message : String(error)
  }
  const manifestPath = path.join(outDir, selectedRoute ? `${safeId(selectedRoute)}.json` : 'manifest.json')
  fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  console.error(JSON.stringify(manifest, null, 2))
  process.exit(1)
})
