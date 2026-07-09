#!/usr/bin/env node

const fs = require('node:fs')
const path = require('node:path')

const repoRoot = path.resolve(__dirname, '../../..')
const artifactDir = path.join(__dirname, 'page-captures')
const appJson = JSON.parse(fs.readFileSync(path.join(repoRoot, 'app.json'), 'utf8'))
const tabRoutes = new Set(((appJson.tabBar && appJson.tabBar.list) || []).map((item) => item.pagePath))
const automatorPort = Number(process.env.WECHAT_AUTOMATOR_PORT || 9854)
const wsEndpoint = `ws://127.0.0.1:${automatorPort}`
const selectedPage = String(process.env.WOW_0900_PROOF_PAGE || '').trim()
const routeSettleMs = Number(process.env.WOW_0900_ROUTE_SETTLE_MS || 1200)
const wxCallTimeoutMs = Number(process.env.WOW_0900_WX_CALL_TIMEOUT_MS || 6000)
const captureTimeoutMs = Number(process.env.WOW_0900_CAPTURE_TIMEOUT_MS || 12000)

const pageQueries = {
  'pages/news/detail': 'id=blizzard-midnight-revelations-2026-06-03',
  'pages/builds/workbench': 'spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C',
  'pages/builds/detail': 'query=gear&spec=%E6%B3%95%E5%B8%88-%E5%86%B0%E9%9C%9C'
}

if (!selectedPage) {
  console.error([
    'Refusing to run without WOW_0900_PROOF_PAGE.',
    'Use WOW_0900_PROOF_PAGE=<app.json route> for one route + screenshot proof.',
    'This script does not close, restart, clear cache, switch appid, switch project, or run a 14-page batch.'
  ].join('\n'))
  process.exit(2)
}

if (!appJson.pages.includes(selectedPage)) {
  console.error(`Unknown app.json page: ${selectedPage}`)
  process.exit(2)
}

function safeId(route) {
  return route.replace(/^pages\//, '').replace(/[/?=&]/g, '_')
}

function urlFor(route) {
  const query = pageQueries[route]
  return `/${route}${query ? `?${query}` : ''}`
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

class RawAutomator {
  constructor(endpoint) {
    this.endpoint = endpoint
    this.nextId = 1
    this.pending = new Map()
    this.ws = null
  }

  async connect() {
    this.ws = new WebSocket(this.endpoint)
    this.ws.addEventListener('message', (event) => this.onMessage(event))
    await withTimeout(new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve, { once: true })
      this.ws.addEventListener('error', (event) => reject(new Error(event.message || event.type)), { once: true })
    }), 3000, `connect ${this.endpoint}`)
  }

  send(method, params = {}, timeoutMs = 8000) {
    const id = this.nextId++
    this.ws.send(JSON.stringify({ id, method, params }))
    return withTimeout(new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method })
    }), timeoutMs, method)
  }

  onMessage(event) {
    const message = JSON.parse(String(event.data))
    if (!message.id || !this.pending.has(message.id)) return
    const pending = this.pending.get(message.id)
    this.pending.delete(message.id)
    if (message.error) {
      pending.reject(new Error(JSON.stringify(message.error)))
    } else {
      pending.resolve(message.result !== undefined ? message.result : message)
    }
  }

  async callWxMethod(method, arg = {}, timeoutMs = wxCallTimeoutMs) {
    return this.send('App.callWxMethod', { method, args: [arg] }, timeoutMs)
  }

  async currentPage() {
    return this.send('App.getCurrentPage', {}, 4000)
  }

  async captureScreenshot(filePath) {
    const result = await this.send('App.captureScreenshot', {}, captureTimeoutMs)
    const data = typeof result === 'string' ? result : result && (result.data || result.image)
    if (!data) throw new Error('empty screenshot data')
    const buffer = Buffer.from(String(data).replace(/^data:image\/png;base64,/, ''), 'base64')
    fs.writeFileSync(filePath, buffer)
    return { bytes: buffer.length, dataLength: String(data).length }
  }

  disconnect() {
    if (this.ws) this.ws.close()
  }
}

async function navigate(automator, route) {
  const target = urlFor(route)
  if (tabRoutes.has(route)) {
    return automator.callWxMethod('switchTab', { url: target })
  }

  const warnings = []
  await automator.callWxMethod('switchTab', { url: '/pages/news/news' }).catch((error) => {
    warnings.push(`switchTab('/pages/news/news') warning: ${error.message}`)
  })
  await wait(500)
  let navigateResult = null
  try {
    navigateResult = await automator.callWxMethod('navigateTo', { url: target })
  } catch (error) {
    warnings.push(`navigateTo('${target}') warning: ${error.message}`)
  }
  const errMsg = navigateResult && navigateResult.result && navigateResult.result.errMsg
  if (typeof errMsg === 'string' && errMsg.includes(':fail')) {
    try {
      return {
        result: await automator.callWxMethod('redirectTo', { url: target }),
        warnings
      }
    } catch (error) {
      warnings.push(`redirectTo('${target}') warning: ${error.message}`)
    }
  }
  return { result: navigateResult, warnings }
}

async function main() {
  fs.mkdirSync(artifactDir, { recursive: true })
  const automator = new RawAutomator(wsEndpoint)
  const startedAt = new Date().toISOString()
  await automator.connect()
  try {
    const toolInfo = await automator.send('Tool.getInfo', {}, 4000)
    const navigation = await navigate(automator, selectedPage)
    await wait(routeSettleMs)
    const currentPage = await automator.currentPage()
    const routeMatches = currentPage && currentPage.path === selectedPage
    if (!routeMatches) {
      throw new Error(`route mismatch after navigation: ${JSON.stringify(currentPage)}`)
    }
    const suffix = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*$/, 'Z')
    const screenshot = path.join(artifactDir, `${safeId(selectedPage)}_auto_${suffix}.png`)
    const screenshotInfo = await automator.captureScreenshot(screenshot)
    const result = {
      status: 'auto_route_and_screenshot_passed',
      startedAt,
      finishedAt: new Date().toISOString(),
      wsEndpoint,
      automatorPort,
      toolInfo,
      path: selectedPage,
      targetUrl: urlFor(selectedPage),
      navigation,
      currentPage,
      routeMatches,
      screenshot,
      screenshotInfo,
      timeouts: {
        routeSettleMs,
        wxCallTimeoutMs,
        captureTimeoutMs
      },
      forbiddenActionsUsed: []
    }
    const manifestPath = path.join(artifactDir, `${safeId(selectedPage)}_auto_latest.json`)
    fs.writeFileSync(manifestPath, JSON.stringify(result, null, 2))
    console.log(JSON.stringify(result, null, 2))
  } finally {
    automator.disconnect()
  }
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : String(error))
  process.exit(1)
})
