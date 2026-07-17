'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { inspectComparison } = require('../scripts/promote-ui-region-comparison')

function comparison(status = 'PASS') {
  return {
    schemaVersion: 'target-runtime-region-comparison-v1',
    commit: 'a'.repeat(12),
    viewport: { width: 390, height: 844, dpr: 3 },
    tolerance: { positionPx: 8, sizePx: 4 },
    routes: [{ route: 'news_detail', status, regions: [{ id: 'article_body', status }] }],
  }
}

function writeFixture(value) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-region-promotion-test-'))
  const file = path.join(directory, 'comparison.json')
  fs.writeFileSync(file, `${JSON.stringify(value)}\n`)
  return file
}

test('region comparison promotion validates and hashes complete passing evidence', () => {
  const inspected = inspectComparison(writeFixture(comparison()))
  assert.equal(inspected.comparison.routes[0].status, 'PASS')
  assert.match(inspected.sha256, /^[a-f\d]{64}$/u)
})

test('region comparison promotion rejects failed or unversioned evidence', () => {
  assert.throws(() => inspectComparison(writeFixture(comparison('FAIL'))), /only complete passing/)
  const missingCommit = comparison()
  delete missingCommit.commit
  assert.throws(() => inspectComparison(writeFixture(missingCommit)), /commit must be/)
})
