'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { buildReviewIndex, escapeHtml, inspectTarget, writeIndexAtomic } = require('../scripts/build-ui-review-index')

test('review index escapes metadata and references local images without embedding payloads', () => {
  const html = buildReviewIndex(
    { commit: '123456789abc', viewport: { width: 390, height: 844, dpr: 3 } },
    [{
      capture: { route: 'route<script>', path: '/pages/test?a=<b>', artifactPath: '/tmp/runtime.png', width: 390, height: 844, bytes: 42, sha256: 'a'.repeat(64), rendererEvidence: { regionCount: 4 } },
      target: { absolutePath: '/tmp/target.png', width: 889, height: 1770 },
    }],
  )
  assert.match(html, /route&lt;script&gt;/)
  assert.match(html, /file:\/\/\/tmp\/runtime\.png/)
  assert.match(html, /file:\/\/\/tmp\/target\.png/)
  assert.doesNotMatch(html, /data:image\//)
  assert.equal(escapeHtml('"<&'), '&quot;&lt;&amp;')
})

test('review index writes atomically within the structured output budget', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-review-index-'))
  const output = path.join(directory, 'review.html')
  assert.equal(writeIndexAtomic(output, '<!doctype html>ok'), 17)
  assert.equal(fs.readFileSync(output, 'utf8'), '<!doctype html>ok')
  assert.throws(() => writeIndexAtomic(output, 'x'.repeat((1024 * 1024) + 1)), /bounded byte policy/)
})

test('review index revalidates canonical target bytes and digest', () => {
  const target = inspectTarget('news_home')
  assert.equal(target.route, 'news_home')
  assert.equal(target.sha256.length, 64)
})
