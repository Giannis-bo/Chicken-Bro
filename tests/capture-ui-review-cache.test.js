'use strict'

const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { inspectCachedCapture, maxRoutesPerCaptureRun, selectedRoutes, writeManifest } = require('../scripts/capture-ui-review-cache')

function pngHeader(width, height) {
  const buffer = Buffer.alloc(24)
  Buffer.from('89504e470d0a1a0a', 'hex').copy(buffer)
  buffer.writeUInt32BE(width, 16)
  buffer.writeUInt32BE(height, 20)
  return buffer
}

test('capture cache resumes only from a byte-identical PNG', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-capture-resume-test-'))
  const artifactPath = path.join(directory, 'route.png')
  const buffer = pngHeader(780, 1688)
  fs.writeFileSync(artifactPath, buffer)
  const viewport = { width: 390, height: 844, dpr: 3 }
  const capture = {
    artifactPath,
    path: '/pages/news/detail?id=architecture-preflight',
    bytes: buffer.length,
    width: 780,
    height: 1688,
    sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
    rendererEvidence: { path: 'pages/news/detail', shellWidth: 390, shellHeight: 844, regionCount: 6 },
  }
  assert.equal(inspectCachedCapture(capture, viewport), true)
  assert.equal(inspectCachedCapture({ ...capture, bytes: buffer.length + 1 }, viewport), false)
  assert.equal(inspectCachedCapture({ ...capture, rendererEvidence: { ...capture.rendererEvidence, regionCount: 0 } }, viewport), false)
})

test('capture manifest checkpoint replaces the previous file atomically', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-capture-manifest-test-'))
  const manifestPath = path.join(directory, 'manifest.json')
  writeManifest(manifestPath, { schemaVersion: 'first' })
  writeManifest(manifestPath, { schemaVersion: 'second', captures: [] })
  assert.equal(JSON.parse(fs.readFileSync(manifestPath, 'utf8')).schemaVersion, 'second')
  assert.equal(fs.existsSync(`${manifestPath}.tmp`), false)
})

test('online capture is restricted to resumable two-route batches', () => {
  assert.equal(maxRoutesPerCaptureRun, 2)
  assert.equal(selectedRoutes('news_home,news_detail').length, 2)
  assert.throws(() => selectedRoutes('all'), /rejects "all"/)
  assert.throws(() => selectedRoutes('news_home,news_detail,build_intel'), /limited to 2 routes/)
})
