#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const path = require('node:path')

const { capturePathMatches, maxCaptureBytes, pngSize, validCaptureBounds } = require('./capture-ui-review-cache')
const { readBoundedFile, writeBoundedFileImmutable } = require('./bounded-file')
const { maxStructuredDetailBytes, readBoundedJson, serializeBoundedJson } = require('./bounded-json-detail')
const interactionContract = require('../docs/design/current-ui/core-interaction-contract.json')

const repositoryRoot = path.resolve(__dirname, '..')

function required(value, name) {
  if (!value) throw new Error(`${name} is required`)
  return value
}

function safeName(value) {
  return value.replace(/[^a-zA-Z0-9._-]+/gu, '-')
}

function selectedRoutes(value, captures) {
  const requested = required(value, 'UI_REVIEW_ROUTES').split(',').map((item) => item.trim()).filter(Boolean)
  if (requested.length === 1 && requested[0] === 'all') return captures
  const byRoute = new Map(captures.map((capture) => [capture.route, capture]))
  const unknown = requested.filter((route) => !byRoute.has(route))
  if (unknown.length > 0) throw new Error(`routes absent from cache manifest: ${unknown.join(', ')}`)
  return [...new Set(requested)].map((route) => byRoute.get(route))
}

function inspectCapture(capture, viewport, cacheRoot) {
  if (!capturePathMatches(capture, cacheRoot)) throw new Error(`cache artifact escapes manifest directory: ${capture.route}`)
  const buffer = readBoundedFile(capture.artifactPath, maxCaptureBytes, `cache artifact ${capture.route}`)
  const dimensions = pngSize(buffer)
  const sha256 = crypto.createHash('sha256').update(buffer).digest('hex')
  if (capture.bytes !== buffer.length || capture.width !== dimensions.width || capture.height !== dimensions.height || capture.sha256 !== sha256) {
    throw new Error(`cache artifact no longer matches manifest: ${capture.route}`)
  }
  const contractRoute = interactionContract.interactions.find((route) => route.route === capture.route)
  const expectedPath = contractRoute?.path.split('?')[0].replace(/^\//u, '')
  if (!contractRoute || capture.path !== contractRoute.path || capture.rendererEvidence?.path !== expectedPath) throw new Error(`cache route identity mismatch: ${capture.route}`)
  if (!(capture.rendererEvidence?.shellWidth > 0 && capture.rendererEvidence?.shellHeight > 0 && capture.rendererEvidence?.regionCount > 0)) throw new Error(`cache renderer evidence is incomplete: ${capture.route}`)
  if (!validCaptureBounds(buffer, dimensions, viewport)) throw new Error(`cache artifact exceeds bounded viewport policy: ${capture.route}`)
  return { buffer, dimensions, sha256 }
}

function main() {
  const manifestPath = path.resolve(required(process.env.UI_REVIEW_MANIFEST, 'UI_REVIEW_MANIFEST'))
  const manifest = readBoundedJson(manifestPath, 'UI review cache manifest')
  if (manifest.schemaVersion !== 'wechat-ui-review-cache-v3' || !Array.isArray(manifest.captures) || manifest.captures.length > 14) {
    throw new Error('unsupported UI review cache manifest')
  }
  if (!/^[a-f\d]{12}$/u.test(manifest.commit)) throw new Error('cache manifest commit must be a 12-character Git SHA')
  if (manifest.captureMethod !== 'reused_existing_wechat_devtools_process' || manifest.routeNavigationMethod !== 'mini_program_relaunch') {
    throw new Error('cache capture and route navigation methods are inaccurate or unsupported')
  }
  const viewport = manifest.viewport
  if (![viewport?.width, viewport?.height, viewport?.dpr].every((value) => Number.isFinite(value) && value > 0)) {
    throw new Error('cache manifest viewport is incomplete')
  }

  const viewportKey = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const promoted = []
  for (const capture of selectedRoutes(process.env.UI_REVIEW_ROUTES, manifest.captures)) {
    const inspected = inspectCapture(capture, viewport, path.dirname(manifestPath))
    const relativePath = path.join(
      'artifacts', 'ui-runtime-reviews', manifest.commit, viewportKey, inspected.sha256, `${safeName(capture.route)}.png`,
    )
    const destination = path.join(repositoryRoot, relativePath)
    writeBoundedFileImmutable(destination, inspected.buffer, maxCaptureBytes, `promoted artifact ${capture.route}`)
    promoted.push({
      route: capture.route,
      path: capture.path,
      rendererEvidence: capture.rendererEvidence,
      runtimeArtifact: {
        path: relativePath.split(path.sep).join('/'),
        width: inspected.dimensions.width,
        height: inspected.dimensions.height,
        bytes: inspected.buffer.length,
        sha256: inspected.sha256,
        captureMethod: manifest.captureMethod,
      },
    })
  }

  const receiptBody = {
    schemaVersion: 'wechat-ui-runtime-promotion-v3',
    sourceManifest: {
      schemaVersion: manifest.schemaVersion,
      commit: manifest.commit,
      viewport: manifest.viewport,
      captureMethod: manifest.captureMethod,
      routeNavigationMethod: manifest.routeNavigationMethod,
    },
    promoted,
  }
  const serialized = serializeBoundedJson(receiptBody, 'UI review promotion receipt')
  const receiptSha = crypto.createHash('sha256').update(serialized).digest('hex')
  const receiptPath = path.join(
    repositoryRoot, 'artifacts', 'ui-runtime-reviews', manifest.commit, viewportKey, 'receipts', `${receiptSha}.json`,
  )
  writeBoundedFileImmutable(receiptPath, Buffer.from(serialized), maxStructuredDetailBytes, 'UI review promotion receipt')

  console.log(JSON.stringify({
    status: 'pass',
    commit: manifest.commit,
    viewport: viewportKey,
    promotedCount: promoted.length,
    routes: promoted.map((item) => item.route),
    receiptPath: path.relative(repositoryRoot, receiptPath).split(path.sep).join('/'),
  }))
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  }
}

module.exports = { inspectCapture, selectedRoutes }
