#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { execFileSync } = require('node:child_process')

const { connectMiniProgram, timeout } = require('./wechat-automator')
const interactionContract = require('../docs/design/current-ui/core-interaction-contract.json')

const operationTimeoutMs = 10000
const settleMs = 700

function selectedRoutes(value) {
  const requested = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (requested.length === 0) {
    throw new Error('UI_REVIEW_ROUTES is required; use comma-separated contract route ids or explicit "all"')
  }
  if (requested.length === 1 && requested[0] === 'all') return interactionContract.interactions
  const byRoute = new Map(interactionContract.interactions.map((item) => [item.route, item]))
  const unknown = requested.filter((route) => !byRoute.has(route))
  if (unknown.length > 0) throw new Error(`unknown UI_REVIEW_ROUTES: ${unknown.join(', ')}`)
  return [...new Set(requested)].map((route) => byRoute.get(route))
}

function pngSize(buffer) {
  if (buffer.length < 24 || buffer.toString('hex', 0, 8) !== '89504e470d0a1a0a') {
    throw new Error('captured artifact is not a valid PNG')
  }
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) }
}

function safeName(value) {
  return value.replace(/[^a-zA-Z0-9._-]+/gu, '-')
}

async function main() {
  const routes = selectedRoutes(process.env.UI_REVIEW_ROUTES)
  const commit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { encoding: 'utf8' }).trim()
  const cacheRoot = process.env.UI_REVIEW_CACHE_ROOT || path.join(os.tmpdir(), 'wow-mini-ui-review-cache')
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const system = await timeout(miniProgram.systemInfo(), 4000, 'read WeChat system info')
    const viewport = {
      width: system.windowWidth,
      height: system.windowHeight,
      dpr: system.pixelRatio,
      safeTop: system.safeArea?.top ?? 0,
      safeBottom: Math.max(0, system.windowHeight - (system.safeArea?.bottom ?? system.windowHeight)),
    }
    const viewportKey = `${viewport.width}x${viewport.height}@${viewport.dpr}`
    const outputRoot = path.join(cacheRoot, commit, viewportKey)
    fs.mkdirSync(outputRoot, { recursive: true })
    const captures = []
    for (const route of routes) {
      await timeout(miniProgram.reLaunch(route.path), operationTimeoutMs, `open ${route.route}`)
      await new Promise((resolve) => setTimeout(resolve, settleMs))
      const artifactPath = path.join(outputRoot, `${safeName(route.route)}.png`)
      await timeout(miniProgram.screenshot({ path: artifactPath }), 5000, `capture ${route.route}`)
      const buffer = fs.readFileSync(artifactPath)
      captures.push({
        route: route.route,
        path: route.path,
        artifactPath,
        bytes: buffer.length,
        sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
        ...pngSize(buffer),
      })
    }
    const manifest = {
      schemaVersion: 'wechat-ui-review-cache-v1',
      commit,
      viewport,
      captureMethod: 'reused_wechat_devtools_automator_without_relaunch',
      captures,
    }
    const manifestPath = path.join(outputRoot, 'manifest.json')
    const temporaryManifestPath = `${manifestPath}.tmp`
    fs.writeFileSync(temporaryManifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
    fs.renameSync(temporaryManifestPath, manifestPath)
    console.log(JSON.stringify({
      status: 'pass',
      cacheRoot: outputRoot,
      manifestPath,
      captureCount: captures.length,
      routes: captures.map((capture) => capture.route),
    }))
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  })
}

module.exports = { pngSize, selectedRoutes }
