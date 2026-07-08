#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram } = require('../../ui-v2-1-strict-restoration/connect-miniprogram-automator')

const repoRoot = path.resolve(__dirname, '../../..')
const artifactDir = path.resolve(__dirname, 'page-captures')
const automatorPort = Number(process.env.WECHAT_AUTOMATOR_PORT || 9854)
const wsEndpoint = `ws://127.0.0.1:${automatorPort}`
const appJson = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app.json'), 'utf8'))
const tabRoutes = new Set((appJson.tabBar && appJson.tabBar.list || []).map((item) => item.pagePath))

const pageSpecs = [
  { path: 'pages/news/news', tier: 'P0', name: '首页资讯' },
  { path: 'pages/news/list', tier: 'P1', name: '资讯列表' },
  { path: 'pages/news/detail', tier: 'P1', name: '资讯详情', query: 'id=blizzard-midnight-revelations-2026-06-03', settleMs: 1800 },
  { path: 'pages/builds/builds', tier: 'P0', name: '职业专精' },
  { path: 'pages/builds/workbench', tier: 'P0', name: '当前专精工作台', query: 'spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C', settleMs: 4200, waitReadyMs: 7000, postReadySettleMs: 800 },
  { path: 'pages/builds/intel', tier: 'P2', name: '智能构筑信息' },
  { path: 'pages/builds/talent-simulator', tier: 'P0', name: '天赋模拟' },
  { path: 'pages/builds/detail', tier: 'P0', name: '装备详情', query: 'query=gear&spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C', settleMs: 4200 },
  { path: 'pages/simulator/simulator', tier: 'P0', name: '智能分析' },
  { path: 'pages/simulator/simc', tier: 'P0', name: 'SimC' },
  { path: 'pages/simulator/chickenbro', tier: 'P1', name: '炸鸡队长' },
  { path: 'pages/simulator/tasks', tier: 'P1', name: '任务' },
  { path: 'pages/simulator/task-detail', tier: 'P1', name: '任务详情' },
  { path: 'pages/profile/profile', tier: 'P0', name: '我的' }
]

const selectedPathSet = process.env.WOW_0900_CAPTURE_PAGES
  ? new Set(process.env.WOW_0900_CAPTURE_PAGES.split(',').map((item) => item.trim()).filter(Boolean))
  : null
const selectedPageSpecs = selectedPathSet
  ? pageSpecs.filter((item) => selectedPathSet.has(item.path))
  : pageSpecs
const allowBatchCapture = process.env.WOW_0900_ALLOW_BATCH === '1'

if (!selectedPathSet && !allowBatchCapture) {
  console.error([
    'Refusing to run a full 14-page serial capture by default.',
    'Multi-page serial capture is known to trigger currentState timeouts and can overwrite evidence with white frames.',
    'Use WOW_0900_CAPTURE_PAGES=<page> for a safe single-page capture.',
    'Only use WOW_0900_ALLOW_BATCH=1 when the user explicitly accepts the DevTools risk.'
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

function safeId(route) {
  return route.replace(/^pages\//, '').replace(/[/?=&]/g, '_')
}

function urlFor(spec) {
  return `/${spec.path}${spec.query ? `?${spec.query}` : ''}`
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

async function currentState(miniProgram) {
  return withTimeout(
    miniProgram.evaluate(() => {
      const pages = getCurrentPages()
      const page = pages[pages.length - 1]
      return {
        route: page ? page.route : '',
        title: page && page.data ? page.data.navTitle || page.data.title || '' : '',
        pagesLength: pages.length
      }
    }),
    2500,
    'currentState'
  )
}

async function waitForPageReady(miniProgram, spec) {
  return withTimeout(
    miniProgram.evaluate((payload) => new Promise((resolve) => {
      const startedAt = Date.now()
      const deadline = startedAt + payload.waitReadyMs
      const tick = () => {
        const pages = getCurrentPages()
        const page = pages[pages.length - 1]
        const data = page && page.data ? page.data : {}
        const route = page ? page.route : ''
        const loading = data.loading === true
        if (route === payload.path && !loading) {
          resolve({
            ready: true,
            route,
            loading,
            waitedMs: Date.now() - startedAt,
            title: data.navTitle || data.title || ''
          })
          return
        }
        if (Date.now() >= deadline) {
          resolve({
            ready: false,
            route,
            loading,
            waitedMs: Date.now() - startedAt,
            title: data.navTitle || data.title || '',
            warning: `page did not reach non-loading state within ${payload.waitReadyMs}ms`
          })
          return
        }
        setTimeout(tick, 180)
      }
      tick()
    }), { path: spec.path, waitReadyMs: spec.waitReadyMs || 5000 }),
    (spec.waitReadyMs || 5000) + 800,
    `wait ready ${spec.path}`
  ).catch((error) => ({
    ready: false,
    route: '',
    loading: null,
    waitedMs: null,
    warning: error.message
  }))
}

async function navigate(miniProgram, spec) {
  const url = urlFor(spec)
  let navError = ''
  const navWarnings = []
  const runNavigation = async (methodName, targetUrl) => {
    const result = await runtimeCall(miniProgram, methodName, targetUrl).catch((error) => ({
      ok: false,
      error: error.message
    }))
    if (result.warning) navWarnings.push(`${targetUrl}: ${result.warning}`)
    if (result.ok === false) {
      navError = result.error || `${methodName} failed`
      return false
    }
    return true
  }
  if (tabRoutes.has(spec.path)) {
    await runNavigation('switchTab', url)
  } else {
    await runNavigation('switchTab', '/pages/news/news')
    await wait(500)
    const navigated = await runNavigation('navigateTo', url)
    if (!navigated) {
      const firstError = navError
      const redirected = await runNavigation('redirectTo', url)
      if (!redirected) navError = `${firstError}; ${navError}`
    }
  }
  await wait(spec.settleMs || 1200)
  const state = await currentState(miniProgram).catch((error) => ({
    route: '',
    title: '',
    pagesLength: null,
    stateError: error.message
  }))
  return { state, navError, navWarnings }
}

async function capture(miniProgram, spec) {
  const { state, navError, navWarnings } = await navigate(miniProgram, spec)
  const routeMatches = state && state.route === spec.path
  const readyState = routeMatches
    ? await waitForPageReady(miniProgram, spec)
    : { ready: false, warning: 'route did not match before ready wait' }
  await wait(spec.postReadySettleMs || 300)
  const screenshot = await withTimeout(miniProgram.send('App.captureScreenshot'), 10000, `capture ${spec.path}`)
  const data = typeof screenshot === 'string'
    ? screenshot
    : screenshot && typeof screenshot.data === 'string'
      ? screenshot.data
      : screenshot && typeof screenshot.image === 'string'
        ? screenshot.image
        : null
  if (!data) throw new Error(`empty screenshot for ${spec.path}`)
  const file = path.join(artifactDir, `${safeId(spec.path)}.png`)
  const buffer = Buffer.isBuffer(data)
    ? data
    : Buffer.from(String(data).replace(/^data:image\/png;base64,/, ''), 'base64')
  fs.writeFileSync(file, buffer)
  return {
    ...spec,
    routeAfter: state.route,
    routeMatches,
    status: routeMatches && !navError && !state.stateError
      ? 'captured_needs_visual_review'
      : 'captured_with_route_or_state_risk',
    navError,
    navWarnings,
    readyState,
    stateError: state.stateError || '',
    screenshot: file,
    screenshotBytes: buffer.length
  }
}

async function main() {
  fs.mkdirSync(artifactDir, { recursive: true })
  const { mini, toolInfo } = await connectMiniProgram(wsEndpoint, { timeoutMs: 2400, toolInfoTimeoutMs: 3000 })
  const results = []
  try {
    for (const spec of selectedPageSpecs) {
      const startedAt = new Date().toISOString()
      try {
        const result = await capture(mini, spec)
        results.push({ ...result, startedAt, finishedAt: new Date().toISOString() })
      } catch (error) {
        results.push({
          ...spec,
          startedAt,
          finishedAt: new Date().toISOString(),
          status: 'fail_or_risk',
          error: error.message
        })
      }
    }
  } finally {
    mini.disconnect()
  }
  const manifest = {
    status: results.some((item) => item.status === 'fail_or_risk') ? 'risk' : 'captured_needs_visual_review',
    checkedAt: new Date().toISOString(),
    wsEndpoint,
    toolInfo,
    forbiddenActionsUsed: [],
    results
  }
  fs.writeFileSync(path.join(artifactDir, 'manifest.json'), JSON.stringify(manifest, null, 2))
  console.log(JSON.stringify(manifest, null, 2))
  if (manifest.status === 'risk') process.exitCode = 2
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
