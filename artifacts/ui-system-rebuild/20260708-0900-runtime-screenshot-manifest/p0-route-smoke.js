#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram } = require('../../ui-v2-1-strict-restoration/connect-miniprogram-automator')

const artifactDir = __dirname
const repoRoot = path.resolve(artifactDir, '../../..')
const automatorPort = Number(process.env.WECHAT_AUTOMATOR_PORT || 9854)
const wsEndpoint = `ws://127.0.0.1:${automatorPort}`
const appJson = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app.json'), 'utf8'))
const tabRoutes = new Set(((appJson.tabBar && appJson.tabBar.list) || []).map((item) => item.pagePath))

const p0Routes = [
  'pages/news/news',
  'pages/builds/builds',
  'pages/builds/workbench',
  'pages/builds/talent-simulator',
  'pages/builds/detail',
  'pages/simulator/simulator',
  'pages/simulator/simc',
  'pages/profile/profile'
]

const primaryActions = [
  {
    name: 'builds.openWorkbench',
    start: 'pages/builds/builds',
    method: 'openWorkbench',
    expectedRoute: 'pages/builds/workbench'
  },
  {
    name: 'workbench.openPrimaryAction',
    start: 'pages/builds/workbench',
    query: 'spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C',
    method: 'openPrimaryAction',
    expectedOneOf: [
      'pages/simulator/simc',
      'pages/builds/detail',
      'pages/builds/talent-simulator',
      'pages/simulator/chickenbro'
    ]
  },
  {
    name: 'detail.openSimcWithBuildContext',
    start: 'pages/builds/detail',
    query: 'query=gear&spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C',
    method: 'openSimcWithBuildContext',
    expectedRoute: 'pages/simulator/simc'
  }
]

if (process.env.WOW_0900_RUN_P0_ROUTE_SMOKE !== '1') {
  console.error([
    'Refusing to run P0 route smoke without explicit opt-in.',
    'Set WOW_0900_RUN_P0_ROUTE_SMOKE=1 to run this low-disruption route-only smoke.',
    'This script connects to an existing automator endpoint but does not close, restart, clear cache, switch appid, or capture screenshots.'
  ].join('\n'))
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

function urlFor(route, query = '') {
  return `/${route}${query ? `?${query}` : ''}`
}

async function runtimeCall(miniProgram, methodName, url) {
  return withTimeout(
    miniProgram.evaluate((payload) => new Promise((resolve) => {
      let settled = false
      const done = (result) => {
        if (settled) return
        settled = true
        resolve(result)
      }
      wx[payload.methodName]({
        url: payload.url,
        success: () => done({ ok: true, warning: '' }),
        fail: (error) => done({ ok: false, error: (error && error.errMsg) || `${payload.methodName} failed` })
      })
      setTimeout(() => done({ ok: null, warning: `${payload.methodName} callback not returned within short window` }), 900)
    }), { methodName, url }),
    2400,
    `${methodName} ${url}`
  )
}

async function automatorRouteCall(miniProgram, methodName, url) {
  try {
    await withTimeout(miniProgram[methodName](url), 5200, `automator ${methodName} ${url}`)
    return { ok: true, warning: '' }
  } catch (error) {
    return {
      ok: false,
      error: error && error.message ? error.message : String(error)
    }
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
    2500,
    'currentState'
  )
}

async function waitForRoute(miniProgram, expectedRoute, timeoutMs = 4200) {
  const startedAt = Date.now()
  let lastState = null
  while (Date.now() - startedAt < timeoutMs) {
    lastState = await currentState(miniProgram).catch((error) => ({
      route: '',
      loading: null,
      title: '',
      pagesLength: null,
      error: error.message
    }))
    if (lastState.route === expectedRoute && lastState.loading !== true) {
      return {
        matched: true,
        waitedMs: Date.now() - startedAt,
        state: lastState
      }
    }
    await wait(220)
  }
  return {
    matched: false,
    waitedMs: Date.now() - startedAt,
    state: lastState || { route: '', loading: null, title: '', pagesLength: null }
  }
}

async function navigateToRoute(miniProgram, route, query = '') {
  const url = urlFor(route, query)
  const warnings = []
  let error = ''
  if (tabRoutes.has(route)) {
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
  const waited = await waitForRoute(miniProgram, route)
  const state = waited.state
  return {
    route,
    query,
    routeAfter: state.route,
    routeMatches: state.route === route,
    loading: state.loading,
    title: state.title,
    pagesLength: state.pagesLength,
    waitedMs: waited.waitedMs,
    warnings,
    error: error || state.error || ''
  }
}

async function runAction(miniProgram, action) {
  const before = await navigateToRoute(miniProgram, action.start, action.query || '')
  if (!before.routeMatches) {
    return {
      ...action,
      status: 'risk',
      before,
      routeAfter: before.routeAfter,
      routeMatches: false,
      error: `could not reach start route ${action.start}`
    }
  }
  const invocation = await withTimeout(
    miniProgram.evaluate((payload) => new Promise((resolve) => {
      const pages = getCurrentPages()
      const page = pages[pages.length - 1]
      if (!page || typeof page[payload.method] !== 'function') {
        resolve({ ok: false, error: `missing page method ${payload.method}` })
        return
      }
      try {
        const returned = page[payload.method]({
          currentTarget: { dataset: payload.dataset || {} },
          detail: payload.detail || {}
        })
        if (returned && typeof returned.then === 'function') {
          returned.then(() => resolve({ ok: true })).catch((error) => resolve({ ok: false, error: error && error.message ? error.message : String(error) }))
          return
        }
        resolve({ ok: true })
      } catch (error) {
        resolve({ ok: false, error: error && error.message ? error.message : String(error) })
      }
    }), action),
    3200,
    `invoke ${action.name}`
  ).catch((error) => ({ ok: false, error: error.message }))
  await wait(1300)
  const after = await currentState(miniProgram).catch((error) => ({ route: '', error: error.message }))
  const allowedRoutes = action.expectedOneOf || [action.expectedRoute]
  const routeMatches = allowedRoutes.includes(after.route)
  return {
    ...action,
    before,
    invocation,
    routeAfter: after.route,
    routeMatches,
    loading: after.loading,
    title: after.title,
    pagesLength: after.pagesLength,
    status: invocation.ok && routeMatches ? 'pass' : 'risk',
    error: invocation.error || (routeMatches ? '' : `expected ${allowedRoutes.join(' or ')}, got ${after.route}`)
  }
}

async function main() {
  const { mini, toolInfo } = await connectMiniProgram(wsEndpoint, { timeoutMs: 2400, toolInfoTimeoutMs: 3000 })
  const startedAt = new Date().toISOString()
  const routeResults = []
  const actionResults = []
  try {
    for (const route of p0Routes) {
      routeResults.push(await navigateToRoute(mini, route))
    }
    for (const action of primaryActions) {
      actionResults.push(await runAction(mini, action))
    }
  } finally {
    mini.disconnect()
  }
  const failedRoutes = routeResults.filter((item) => !item.routeMatches || item.error)
  const riskyActions = actionResults.filter((item) => item.status !== 'pass')
  const warningCount = routeResults.reduce((sum, item) => sum + item.warnings.length, 0)
  const manifest = {
    status: failedRoutes.length || riskyActions.length ? 'p0_route_smoke_has_risks' : 'p0_route_smoke_passed_with_callback_warnings',
    startedAt,
    checkedAt: new Date().toISOString(),
    wsEndpoint,
    toolInfo,
    forbiddenActionsUsed: [],
    captureScreenshotUsed: false,
    fullSerialScreenshotUsed: false,
    routeCount: routeResults.length,
    actionCount: actionResults.length,
    warningCount,
    failedRouteCount: failedRoutes.length,
    riskyActionCount: riskyActions.length,
    routeResults,
    actionResults
  }
  const file = path.join(artifactDir, 'p0-route-smoke-manifest.json')
  fs.writeFileSync(file, `${JSON.stringify(manifest, null, 2)}\n`)
  console.log(JSON.stringify({
    status: manifest.status,
    routeCount: manifest.routeCount,
    actionCount: manifest.actionCount,
    warningCount: manifest.warningCount,
    failedRouteCount: manifest.failedRouteCount,
    riskyActionCount: manifest.riskyActionCount
  }, null, 2))
  if (manifest.status !== 'p0_route_smoke_passed_with_callback_warnings') process.exitCode = 2
}

main().catch((error) => {
  const manifest = {
    status: 'p0_route_smoke_not_completed',
    checkedAt: new Date().toISOString(),
    wsEndpoint,
    forbiddenActionsUsed: [],
    captureScreenshotUsed: false,
    fullSerialScreenshotUsed: false,
    error: error && error.message ? error.message : String(error),
    note: 'Low-disruption route smoke could not connect to the existing automator endpoint. No close, restart, cache clear, appid switch, project switch, user-directory deletion, or screenshot capture was attempted.'
  }
  try {
    fs.writeFileSync(path.join(artifactDir, 'p0-route-smoke-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  } catch (writeError) {
    console.error(writeError)
  }
  console.error(error)
  process.exit(1)
})
