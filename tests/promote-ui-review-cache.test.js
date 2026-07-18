'use strict'

const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { inspectCapture, selectedRoutes } = require('../scripts/promote-ui-review-cache')

function pngHeader(width, height) {
  const buffer = Buffer.alloc(24)
  Buffer.from('89504e470d0a1a0a', 'hex').copy(buffer)
  buffer.writeUInt32BE(width, 16)
  buffer.writeUInt32BE(height, 20)
  return buffer
}

test('promotion revalidates cached bytes, dimensions and digest', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-ui-promotion-test-'))
  const artifactPath = path.join(directory, 'news_detail.png')
  const buffer = pngHeader(390, 844)
  fs.writeFileSync(artifactPath, buffer)
  const capture = {
    route: 'news_detail',
    path: '/pages/news/detail?id=architecture-preflight',
    artifactPath,
    bytes: buffer.length,
    width: 390,
    height: 844,
    sha256: crypto.createHash('sha256').update(buffer).digest('hex'),
    rendererEvidence: { path: 'pages/news/detail', shellWidth: 390, shellHeight: 844, regionCount: 6 },
  }
  const viewport = { width: 390, height: 844, dpr: 3 }
  assert.equal(inspectCapture(capture, viewport, directory).sha256, capture.sha256)
  assert.throws(() => inspectCapture({ ...capture, bytes: capture.bytes + 1 }, viewport, directory), /no longer matches manifest/)
  assert.throws(() => inspectCapture({ ...capture, rendererEvidence: { ...capture.rendererEvidence, regionCount: 0 } }, viewport, directory), /renderer evidence is incomplete/)
  assert.throws(() => inspectCapture({ ...capture, path: '/pages/news/list' }, viewport, directory), /route identity mismatch/)
  assert.throws(() => inspectCapture({ ...capture, artifactPath: path.join(directory, '..', 'news_detail.png') }, viewport, directory), /escapes manifest directory/)
})

test('promotion selection is explicit and rejects absent routes', () => {
  const captures = [{ route: 'news_detail' }, { route: 'build_intel' }]
  assert.deepEqual(selectedRoutes('build_intel', captures), [captures[1]])
  assert.deepEqual(selectedRoutes('all', captures), captures)
  assert.throws(() => selectedRoutes('', captures), /UI_REVIEW_ROUTES is required/)
  assert.throws(() => selectedRoutes('unknown', captures), /absent from cache manifest/)
})
