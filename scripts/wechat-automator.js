'use strict'

const net = require('node:net')
const automator = require('miniprogram-automator')
const projectConfig = require('../apps/mini-taro/project.config.json')

const explicitConnectTimeoutMs = 30000
const reuseConnectTimeoutMs = 2000
const renderedPageTimeoutMs = 30000
const systemInfoTimeoutMs = 30000
const expectedAppId = projectConfig.appid
const minimumAutomatorSdkVersion = '2.7.3'

function parseSdkVersion(value) {
  const raw = String(value ?? '').trim()
  if (!/^\d+(?:\.\d+){2,}$/u.test(raw)) return null
  const parts = raw.split('.').map(Number)
  return parts.every(Number.isSafeInteger) ? parts : null
}

function compareSdkVersions(left, right) {
  const leftParts = parseSdkVersion(left)
  const rightParts = parseSdkVersion(right)
  if (!leftParts || !rightParts) return null
  const length = Math.max(leftParts.length, rightParts.length)
  for (let index = 0; index < length; index += 1) {
    const difference = (leftParts[index] ?? 0) - (rightParts[index] ?? 0)
    if (difference) return Math.sign(difference)
  }
  return 0
}

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

async function queryElementsWithXpathFallback(page, selector, xpath) {
  const elements = await timeout(page.$$(selector), 2000, `query ${selector}`)
  if (elements.length || !xpath) return elements
  const fallback = await timeout(page.getElementByXpath(xpath), 2000, `query xpath fallback for ${selector}`)
  return fallback ? [fallback] : []
}

async function queryElementsByXpathSequentially(page, xpath, maximumElements) {
  if (!Number.isInteger(maximumElements) || maximumElements < 1) {
    throw new Error(`invalid xpath element cap: ${maximumElements}`)
  }
  const elements = []
  for (let index = 1; index <= maximumElements + 1; index += 1) {
    const indexedXpath = `(${xpath})[${index}]`
    const element = await timeout(
      page.getElementByXpath(indexedXpath),
      2000,
      `query xpath element ${index}/${maximumElements}`,
    )
    if (!element) return elements
    try {
      const renderedClass = await timeout(
        element.attribute('class'),
        1500,
        `validate xpath element ${index}/${maximumElements}`,
      )
      if (renderedClass === null || renderedClass === undefined) return elements
    } catch (error) {
      // WeChat DevTools 2.01.2501200 can return an Element wrapper whose
      // protocol payload is undefined when an indexed XPath has no match.
      if (
        error instanceof Error
        && error.message === "Cannot read properties of undefined (reading 'attributes')"
      ) {
        return elements
      }
      throw error
    }
    if (index > maximumElements) {
      throw new Error(`xpath element cap exceeded: ${xpath} >${maximumElements}`)
    }
    elements.push(element)
  }
  return elements
}

async function assertAutomatorRuntimeCompatible(
  miniProgram,
  compatibilityTimeoutMs = reuseConnectTimeoutMs,
) {
  const systemInfo = await timeout(
    miniProgram.callWxMethod('getSystemInfoSync'),
    compatibilityTimeoutMs,
    'read connected mini program runtime SDK',
  )
  const sdkVersion = systemInfo?.SDKVersion
  if (typeof sdkVersion !== 'string' || !sdkVersion.trim()) {
    throw new Error('WeChat runtime SDKVersion is missing; refusing an unverified Automator connection')
  }
  const versionComparison = (
    sdkVersion === 'dev'
      ? 0
      : compareSdkVersions(sdkVersion, minimumAutomatorSdkVersion)
  )
  if (versionComparison === null) {
    throw new Error(
      `WeChat runtime SDKVersion is invalid: ${sdkVersion}`,
    )
  }
  if (versionComparison < 0) {
    throw new Error(
      `WeChat runtime SDKVersion is ${sdkVersion}, while Automator requires at least ${minimumAutomatorSdkVersion}`,
    )
  }
  return systemInfo
}

async function connectAutomatorEndpoint(
  endpoint,
  connectTool = automator.launcher.connectTool.bind(automator.launcher),
  compatibilityTimeoutMs = reuseConnectTimeoutMs,
) {
  // DevTools 2.02.2607161 returns {version} from Tool.getInfo instead of the
  // SDKVersion expected by miniprogram-automator 0.12.1. Connect to the
  // protocol without that broken probe, then validate the real runtime SDK.
  const miniProgram = await connectTool({ wsEndpoint: endpoint })
  try {
    await assertAutomatorRuntimeCompatible(miniProgram, compatibilityTimeoutMs)
    return miniProgram
  } catch (error) {
    miniProgram.disconnect?.()
    throw error
  }
}

async function connectMiniProgram() {
  const endpoint = process.env.WECHAT_AUTOMATOR_ENDPOINT
  if (endpoint) {
    const miniProgram = await timeout(
      connectAutomatorEndpoint(endpoint, undefined, explicitConnectTimeoutMs),
      explicitConnectTimeoutMs,
      `connect ${endpoint}`,
    )
    try {
      await assertExpectedProject(miniProgram)
      return miniProgram
    } catch (error) {
      miniProgram.disconnect()
      throw error
    }
  }

  for (let port = 9420; port <= 9460; port += 1) {
    if (await portIsListening(port)) {
      let miniProgram
      try {
        miniProgram = await timeout(
          connectAutomatorEndpoint(`ws://127.0.0.1:${port}`),
          reuseConnectTimeoutMs,
          `connect automation port ${port}`,
        )
        await assertExpectedProject(miniProgram)
        return miniProgram
      } catch {
        if (miniProgram) miniProgram.disconnect()
        // A listening port in this range is not necessarily a WeChat Automator endpoint.
      }
    }
  }

  throw new Error(`No reusable WeChat automation endpoint for ${expectedAppId} found on ports 9420-9460; refusing to launch or relaunch DevTools. Open and log in to the existing wow-mini-taro project manually, or provide its WECHAT_AUTOMATOR_ENDPOINT.`)
}

async function assertExpectedProject(miniProgram) {
  const accountInfo = await timeout(
    miniProgram.callWxMethod('getAccountInfoSync'),
    reuseConnectTimeoutMs,
    'read connected mini program identity',
  )
  const actualAppId = accountInfo?.miniProgram?.appId
  if (actualAppId !== expectedAppId) {
    throw new Error(`WeChat automation endpoint belongs to ${actualAppId || 'an unknown app'}, expected ${expectedAppId}`)
  }
  return accountInfo
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
  assertAutomatorRuntimeCompatible,
  assertExpectedProject,
  connectAutomatorEndpoint,
  connectMiniProgram,
  expectedAppId,
  hasRenderedRoot,
  queryElementsByXpathSequentially,
  queryElementsWithXpathFallback,
  readSemanticValue,
  timeout,
  waitForRenderedPage,
  waitForSystemInfo,
}
