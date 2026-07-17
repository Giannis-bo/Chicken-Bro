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
const maxCaptureBytes = 8 * 1024 * 1024
const maxCaptureScale = 4
const maxManifestBytes = 1024 * 1024

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

function validCaptureBounds(buffer, dimensions, viewport) {
  return buffer.length > 0
    && buffer.length <= maxCaptureBytes
    && dimensions.width >= viewport.width
    && dimensions.height >= viewport.height
    && dimensions.width <= viewport.width * maxCaptureScale
    && dimensions.height <= viewport.height * maxCaptureScale
    && dimensions.width * viewport.height === dimensions.height * viewport.width
}

function inspectCachedCapture(capture, viewport) {
  if (!capture?.artifactPath || !fs.existsSync(capture.artifactPath)) return false
  const artifactBytes = fs.statSync(capture.artifactPath).size
  if (artifactBytes <= 0 || artifactBytes > maxCaptureBytes) return false
  const buffer = fs.readFileSync(capture.artifactPath)
  const dimensions = pngSize(buffer)
  return capture.bytes === buffer.length
    && capture.width === dimensions.width
    && capture.height === dimensions.height
    && capture.sha256 === crypto.createHash('sha256').update(buffer).digest('hex')
    && validCaptureBounds(buffer, dimensions, viewport)
    && capture.rendererEvidence?.path === capture.path.split('?')[0].replace(/^\//u, '')
    && capture.rendererEvidence?.shellWidth > 0
    && capture.rendererEvidence?.shellHeight > 0
    && capture.rendererEvidence?.regionCount > 0
}

function writeManifest(manifestPath, manifest) {
  const temporaryManifestPath = `${manifestPath}.tmp`
  fs.writeFileSync(temporaryManifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
  fs.renameSync(temporaryManifestPath, manifestPath)
}

async function captureWithRetry(miniProgram, artifactPath, route) {
  let lastError
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await timeout(miniProgram.screenshot({ path: artifactPath }), 5000, `capture ${route} attempt ${attempt}`)
      return
    } catch (error) {
      lastError = error
      if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 400))
    }
  }
  throw lastError
}

async function inspectRenderer(page, route) {
  const [shell, regions] = await Promise.all([
    timeout(page.$('.wx-style-shell'), 3000, `query shell ${route.route}`),
    timeout(page.$$('.wx-style-routeregion'), 3000, `query regions ${route.route}`),
  ])
  const expectedPath = route.path.split('?')[0].replace(/^\//u, '')
  if (page.path !== expectedPath) throw new Error(`route path mismatch: expected ${expectedPath}, actual ${page.path}`)
  if (!shell) throw new Error(`renderer shell missing: ${route.route}`)
  if (regions.length === 0) throw new Error(`renderer regions missing: ${route.route}`)
  const size = await timeout(shell.size(), 2500, `read shell size ${route.route}`)
  if (!(size.width > 0 && size.height > 0)) throw new Error(`renderer shell is empty: ${route.route}`)
  return { path: page.path, shellWidth: size.width, shellHeight: size.height, regionCount: regions.length }
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
    const manifestPath = path.join(outputRoot, 'manifest.json')
    let existing = null
    if (fs.existsSync(manifestPath) && fs.statSync(manifestPath).size <= maxManifestBytes) {
      try { existing = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) } catch {}
    }
    const existingCaptures = existing?.schemaVersion === 'wechat-ui-review-cache-v3'
      && existing.commit === commit
      && JSON.stringify(existing.viewport) === JSON.stringify(viewport)
      && Array.isArray(existing.captures)
      && existing.captures.length <= 14
      ? existing.captures ?? []
      : []
    const capturesByRoute = new Map(existingCaptures.filter((capture) => inspectCachedCapture(capture, viewport)).map((capture) => [capture.route, capture]))
    const failures = []
    const manifest = {
      schemaVersion: 'wechat-ui-review-cache-v3',
      commit,
      viewport,
      captureMethod: 'reused_existing_wechat_devtools_process',
      routeNavigationMethod: 'mini_program_relaunch',
      captures: [...capturesByRoute.values()],
      failures,
    }
    writeManifest(manifestPath, manifest)
    for (const route of routes) {
      if (capturesByRoute.has(route.route)) continue
      try {
        const page = await timeout(miniProgram.reLaunch(route.path), operationTimeoutMs, `open ${route.route}`)
        await new Promise((resolve) => setTimeout(resolve, settleMs))
        const rendererEvidence = await inspectRenderer(page, route)
        const artifactPath = path.join(outputRoot, `${safeName(route.route)}.png`)
        await captureWithRetry(miniProgram, artifactPath, route.route)
        const artifactBytes = fs.statSync(artifactPath).size
        if (artifactBytes <= 0 || artifactBytes > maxCaptureBytes) throw new Error(`capture exceeds bounded byte policy before read: ${route.route}`)
        const buffer = fs.readFileSync(artifactPath)
        const dimensions = pngSize(buffer)
        if (!validCaptureBounds(buffer, dimensions, viewport)) throw new Error(`capture exceeds bounded viewport artifact policy: ${route.route}`)
        capturesByRoute.set(route.route, {
          route: route.route,
          path: route.path,
          artifactPath,
          bytes: buffer.length,
          sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
          ...dimensions,
          rendererEvidence,
        })
        manifest.captures = [...capturesByRoute.values()]
        writeManifest(manifestPath, manifest)
      } catch (error) {
        failures.push({ route: route.route, error: String(error instanceof Error ? error.message : error).slice(0, 240) })
        writeManifest(manifestPath, manifest)
        break
      }
    }
    const selectedRouteNames = new Set(routes.map((route) => route.route))
    const captures = [...capturesByRoute.values()].filter((capture) => selectedRouteNames.has(capture.route))
    const pendingRoutes = routes.map((route) => route.route).filter((route) => !capturesByRoute.has(route))
    console.log(JSON.stringify({
      status: pendingRoutes.length === 0 ? 'pass' : captures.length > 0 ? 'partial' : 'fail',
      cacheRoot: outputRoot,
      manifestPath,
      captureCount: captures.length,
      routes: captures.map((capture) => capture.route),
      failedRoutes: failures.map((failure) => failure.route),
      pendingRoutes,
    }))
    if (pendingRoutes.length > 0) process.exitCode = 1
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

module.exports = { captureWithRetry, inspectCachedCapture, inspectRenderer, maxCaptureBytes, maxManifestBytes, pngSize, selectedRoutes, validCaptureBounds, writeManifest }
