'use strict'

const path = require('node:path')
const net = require('node:net')
const automator = require('miniprogram-automator')

const explicitConnectTimeoutMs = 30000
const reuseConnectTimeoutMs = 2000
const renderedPageTimeoutMs = 30000
const systemInfoTimeoutMs = 30000

function timeout(promise, milliseconds, label) {
  let timer
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${milliseconds}ms`)), milliseconds)
  })
  return Promise.race([promise, deadline]).finally(() => clearTimeout(timer))
}

function hasRenderedRoot(data) {
  return Array.isArray(data?.root?.cn) && data.root.cn.length > 0
}

async function waitForRenderedPage(page, label = `render ${page.path}`) {
  const deadline = Date.now() + renderedPageTimeoutMs
  let lastError = null
  while (Date.now() < deadline) {
    try {
      const data = await timeout(page.data(), 2000, `read ${page.path} root data`)
      if (hasRenderedRoot(data)) return page
    } catch (error) {
      lastError = error
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  const detail = lastError instanceof Error ? `; last error: ${lastError.message}` : ''
  throw new Error(`${label} timed out after ${renderedPageTimeoutMs}ms${detail}`)
}

async function waitForSystemInfo(miniProgram, label = 'read WeChat system info') {
  const deadline = Date.now() + systemInfoTimeoutMs
  let lastError = null
  while (Date.now() < deadline) {
    try {
      const info = await timeout(miniProgram.systemInfo(), 5000, label)
      if (Number(info?.windowWidth) > 0 && Number(info?.windowHeight) > 0) return info
      lastError = new Error('system info did not include a positive window size')
    } catch (error) {
      lastError = error
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  const detail = lastError instanceof Error ? `; last error: ${lastError.message}` : ''
  throw new Error(`${label} timed out after ${systemInfoTimeoutMs}ms${detail}`)
}

async function readSemanticValue(element, attribute, label = attribute) {
  const normalizedAttribute = attribute.replace(/^data-/u, '')
  const direct = await timeout(element.attribute(`data-${normalizedAttribute}`), 1500, `read ${label}`)
  if (direct !== null && direct !== undefined && direct !== '') return direct
  const className = String(await timeout(element.attribute('class'), 1500, `read ${label} marker class`) ?? '')
  const marker = className.match(new RegExp(`(?:^|\\s)wx-data-${normalizedAttribute}-([^\\s]+)`, 'u'))
  return marker?.[1] ?? null
}

async function connectMiniProgram() {
  const endpoint = process.env.WECHAT_AUTOMATOR_ENDPOINT
  if (endpoint) {
    return timeout(automator.connect({ wsEndpoint: endpoint }), explicitConnectTimeoutMs, `connect ${endpoint}`)
  }

  for (let port = 9420; port <= 9460; port += 1) {
    if (await portIsListening(port)) {
      try {
        return await timeout(automator.connect({ wsEndpoint: `ws://127.0.0.1:${port}` }), reuseConnectTimeoutMs, `connect automation port ${port}`)
      } catch {
        // A listening port in this range is not necessarily a WeChat Automator endpoint.
      }
    }
  }

  if (process.env.WECHAT_AUTOMATOR_LAUNCH !== '1') {
    throw new Error('No reusable WeChat automation endpoint found on ports 9420-9460; refusing to relaunch DevTools. Start automation once with WECHAT_AUTOMATOR_LAUNCH=1 or provide WECHAT_AUTOMATOR_ENDPOINT.')
  }

  const projectPath = process.env.WECHAT_AUTOMATOR_PROJECT || path.resolve(__dirname, '../apps/mini-taro')
  const cliPath = process.env.WECHAT_DEVTOOLS_CLI
  return timeout(automator.launch({
    projectPath,
    trustProject: true,
    timeout: explicitConnectTimeoutMs,
    ...(cliPath ? { cliPath } : {}),
  }), explicitConnectTimeoutMs + 2000, 'launch automation channel')
}

function portIsListening(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port })
    let settled = false
    const finish = (listening) => {
      if (settled) return
      settled = true
      socket.destroy()
      resolve(listening)
    }
    socket.setTimeout(120)
    socket.once('connect', () => finish(true))
    socket.once('error', () => finish(false))
    socket.once('timeout', () => finish(false))
  })
}

module.exports = {
  connectMiniProgram,
  hasRenderedRoot,
  readSemanticValue,
  timeout,
  waitForRenderedPage,
  waitForSystemInfo,
}
