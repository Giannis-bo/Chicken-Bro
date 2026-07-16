#!/usr/bin/env node
'use strict'

const automator = require('miniprogram-automator')

const endpoint = process.env.WECHAT_AUTOMATOR_ENDPOINT || 'ws://127.0.0.1:9421'
const connectTimeoutMs = 8000
const operationTimeoutMs = 8000

function timeout(promise, milliseconds, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${milliseconds}ms`)), milliseconds)),
  ])
}

async function elementGeometry(page, selector, includeText = false) {
  const element = await timeout(page.$(selector), operationTimeoutMs, `query ${selector}`)
  if (!element) return null
  const [offset, size] = await Promise.all([
    timeout(element.offset(), operationTimeoutMs, `${selector} offset`),
    timeout(element.size(), operationTimeoutMs, `${selector} size`),
  ])
  return {
    offset,
    size,
    ...(includeText ? { text: await timeout(element.text(), operationTimeoutMs, `${selector} text`) } : {}),
  }
}

async function measure(miniProgram, baseline) {
  const page = await timeout(miniProgram.reLaunch(baseline.url), operationTimeoutMs, `reLaunch ${baseline.id}`)
  if (!page) throw new Error(`reLaunch ${baseline.id} returned no page`)
  await new Promise((resolve) => setTimeout(resolve, 600))
  return {
    id: baseline.id,
    path: page.path,
    shell: await elementGeometry(page, '.wx-style-shell'),
    header: await elementGeometry(page, '.wx-style-pageframeheader'),
    title: await elementGeometry(page, '.wx-style-pageframetitletext', true),
    back: await elementGeometry(page, '.wx-style-pageframebackcontrol'),
  }
}

function closeTo(actual, expected, tolerance = 1) {
  return typeof actual === 'number' && Math.abs(actual - expected) <= tolerance
}

async function main() {
  let miniProgram
  try {
    miniProgram = await timeout(automator.connect({ wsEndpoint: endpoint }), connectTimeoutMs, 'connect')
    const systemInfo = await timeout(miniProgram.systemInfo(), operationTimeoutMs, 'systemInfo')
    const baselines = []
    for (const baseline of [
      { id: 'news_home', url: '/pages/news/news', chrome: 'root', headerInset: 0 },
      { id: 'simulator_home', url: '/pages/simulator/simulator', chrome: 'root', headerInset: 0 },
      { id: 'news_detail', url: '/pages/news/detail?id=architecture-preflight', chrome: 'pushed', headerInset: 6.77 },
    ]) {
      baselines.push({ ...baseline, ...await measure(miniProgram, baseline) })
    }

    const failures = []
    for (const baseline of baselines) {
      if (!baseline.shell || !baseline.header || !baseline.title) {
        failures.push(`${baseline.id}: missing shared shell/header/title owner`)
        continue
      }
      if (!closeTo(baseline.shell.size.width, systemInfo.windowWidth)) failures.push(`${baseline.id}: shell width drift`)
      if (!closeTo(baseline.header.offset.left, baseline.headerInset)) failures.push(`${baseline.id}: header leading inset drift`)
      if (!closeTo(baseline.header.size.width, systemInfo.windowWidth - baseline.headerInset * 2)) failures.push(`${baseline.id}: header width drift`)
      if (baseline.header.offset.top < systemInfo.safeArea.top || baseline.header.offset.top > systemInfo.safeArea.top + 5) {
        failures.push(`${baseline.id}: header safe-area origin drift`)
      }
      if (baseline.chrome === 'root') {
        if (baseline.back) failures.push(`${baseline.id}: root page rendered pushed back control`)
        if (!closeTo(baseline.title.offset.left, 16)) failures.push(`${baseline.id}: root title is not on the shared leading edge`)
      } else {
        if (!baseline.back) failures.push(`${baseline.id}: pushed page lost back control`)
        if (baseline.title.offset.left <= 40) failures.push(`${baseline.id}: pushed title fell into the root title slot`)
      }
    }

    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'structured_wechat_runtime_geometry',
      visualPixelReview: 'UNVERIFIED',
      device: {
        model: systemInfo.model,
        windowWidth: systemInfo.windowWidth,
        windowHeight: systemInfo.windowHeight,
        safeTop: systemInfo.safeArea.top,
      },
      baselines,
      failures,
    }, null, 2))
    if (failures.length) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
