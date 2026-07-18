#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const { randomUUID } = require('node:crypto')

const { maxCaptureBytes, pngSize } = require('./capture-ui-review-cache')
const { readBoundedFile } = require('./bounded-file')
const { maxStructuredDetailBytes, readBoundedJson } = require('./bounded-json-detail')
const { inspectCapture, selectedRoutes, validateManifestCacheIdentity } = require('./promote-ui-review-cache')
const targetRegistry = require('../docs/design/current-ui/target-registry.json')

const repositoryRoot = path.resolve(__dirname, '..')

function required(value, name) {
  if (!value) throw new Error(`${name} is required`)
  return value
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function inspectTarget(route) {
  const target = targetRegistry.canonicalTargets.find((candidate) => candidate.route === route)
  if (!target) throw new Error(`canonical target is missing: ${route}`)
  const targetPath = path.join(repositoryRoot, target.path)
  const buffer = readBoundedFile(targetPath, maxCaptureBytes, `canonical target ${route}`)
  const dimensions = pngSize(buffer)
  const sha256 = crypto.createHash('sha256').update(buffer).digest('hex')
  if (buffer.length !== target.bytes || dimensions.width !== target.width || dimensions.height !== target.height || sha256 !== target.sha256) {
    throw new Error(`canonical target no longer matches registry: ${route}`)
  }
  return { ...target, absolutePath: targetPath }
}

function buildReviewIndex(manifest, captures) {
  const viewportKey = `${manifest.viewport.width}x${manifest.viewport.height}@${manifest.viewport.dpr}`
  const cards = captures.map(({ capture, target }) => `
    <article class="card">
      <header><h2>${escapeHtml(capture.route)}</h2><code>${escapeHtml(capture.path)}</code></header>
      <div class="compare">
        <figure><figcaption>Canonical target · ${target.width}×${target.height}</figcaption><img loading="lazy" src="${escapeHtml(pathToFileURL(target.absolutePath).href)}" alt="${escapeHtml(capture.route)} canonical target"></figure>
        <figure><figcaption>WeChat runtime · ${capture.width}×${capture.height}</figcaption><img loading="lazy" src="${escapeHtml(pathToFileURL(capture.artifactPath).href)}" alt="${escapeHtml(capture.route)} runtime capture"></figure>
      </div>
      <footer><code>runtime ${escapeHtml(capture.sha256)}</code><code>${capture.bytes} bytes · regions ${capture.rendererEvidence.regionCount}</code></footer>
    </article>`).join('')
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>UI Review ${escapeHtml(manifest.commit)}</title>
<style>html{color-scheme:dark}body{margin:0;padding:24px;background:#090b0e;color:#ddd;font:14px/1.45 system-ui,sans-serif}main{display:grid;gap:20px;max-width:1440px;margin:auto}.summary,.card{border:1px solid #50452f;background:#111419}.summary,header,footer{padding:12px 16px}.summary h1,h2{margin:0;color:#dfbd73}.summary p{margin:6px 0 0}.compare{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1px;background:#50452f}figure{min-width:0;margin:0;padding:12px;background:#080a0d}figcaption{margin-bottom:8px;color:#a99b7d}img{display:block;width:100%;height:auto;background:#050608}footer{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;color:#a9b6c3}code{overflow-wrap:anywhere}@media(max-width:760px){body{padding:8px}.compare{grid-template-columns:1fr}}</style></head>
<body><main><section class="summary"><h1>WeChat UI Review</h1><p>commit ${escapeHtml(manifest.commit)} · viewport ${escapeHtml(viewportKey)} · ${captures.length} routes</p><p>本页只引用本地、有界、SHA-256 已复核的 PNG；不把图片载荷写入终端或会话。</p></section>${cards}</main></body></html>
`
}

function writeIndexAtomic(filePath, html) {
  const buffer = Buffer.from(html)
  if (buffer.length <= 0 || buffer.length > maxStructuredDetailBytes) throw new Error('UI review index exceeds bounded byte policy')
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const temporaryPath = `${filePath}.tmp-${process.pid}-${randomUUID()}`
  try {
    fs.writeFileSync(temporaryPath, buffer, { flag: 'wx' })
    fs.renameSync(temporaryPath, filePath)
  } finally {
    fs.rmSync(temporaryPath, { force: true })
  }
  return buffer.length
}

function main() {
  const manifestPath = path.resolve(required(process.env.UI_REVIEW_MANIFEST, 'UI_REVIEW_MANIFEST'))
  const outputPath = path.resolve(required(process.env.UI_REVIEW_INDEX, 'UI_REVIEW_INDEX'))
  const manifest = readBoundedJson(manifestPath, 'UI review cache manifest')
  if (manifest.schemaVersion !== 'wechat-ui-review-cache-v4' || !Array.isArray(manifest.captures) || manifest.captures.length > 14) {
    throw new Error('unsupported UI review cache manifest')
  }
  if (manifest.captureMethod !== 'reused_existing_wechat_devtools_process' || manifest.routeNavigationMethod !== 'mini_program_relaunch') {
    throw new Error('cache capture and route navigation methods are inaccurate or unsupported')
  }
  const { manifestDirectory, viewport } = validateManifestCacheIdentity(manifestPath, manifest)
  const selected = selectedRoutes(process.env.UI_REVIEW_ROUTES || 'all', manifest.captures)
  if (selected.length === 0) throw new Error('UI review index requires at least one verified capture')
  const captures = selected.map((capture) => {
    inspectCapture(capture, viewport, manifestDirectory)
    return { capture, target: inspectTarget(capture.route) }
  })
  const bytes = writeIndexAtomic(outputPath, buildReviewIndex(manifest, captures))
  console.log(JSON.stringify({ status: 'pass', commit: manifest.commit, routeCount: captures.length, bytes, indexPath: outputPath }))
}

if (require.main === module) {
  try {
    main()
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  }
}

module.exports = { buildReviewIndex, escapeHtml, inspectTarget, writeIndexAtomic }
