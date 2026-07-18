'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { boundedDetailPaths, maxStructuredDetailBytes, readBoundedJson, writeBoundedJsonAtomic } = require('../scripts/bounded-json-detail')

test('structured evidence promotion accepts at most fourteen detail files', () => {
  assert.equal(boundedDetailPaths('a,b', 'DETAIL_PATHS').length, 2)
  assert.throws(() => boundedDetailPaths('', 'DETAIL_PATHS'), /DETAIL_PATHS is required/)
  assert.throws(
    () => boundedDetailPaths(Array.from({ length: 15 }, (_, index) => `detail-${index}`).join(','), 'DETAIL_PATHS'),
    /accepts at most 14 bounded detail files/,
  )
})

test('structured review details write atomically and read within one MiB', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-bounded-detail-'))
  const detailPath = path.join(directory, 'detail.json')
  try {
    writeBoundedJsonAtomic(detailPath, { status: 'pass' }, 'test detail')
    assert.deepEqual(readBoundedJson(detailPath, 'test detail'), { status: 'pass' })
    assert.equal(fs.readdirSync(directory).some((file) => file.includes('.tmp-')), false)
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('stale process-named temporary files do not block the next atomic write', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-bounded-detail-stale-'))
  const detailPath = path.join(directory, 'detail.json')
  const stalePath = `${detailPath}.tmp-${process.pid}`
  try {
    fs.writeFileSync(stalePath, 'stale')
    writeBoundedJsonAtomic(detailPath, { status: 'recovered' }, 'test detail')
    assert.deepEqual(readBoundedJson(detailPath, 'test detail'), { status: 'recovered' })
    assert.equal(fs.readFileSync(stalePath, 'utf8'), 'stale')
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('structured review details reject oversized files before read', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-bounded-detail-read-'))
  const detailPath = path.join(directory, 'oversized.json')
  const descriptor = fs.openSync(detailPath, 'w')
  try { fs.ftruncateSync(descriptor, maxStructuredDetailBytes + 1) } finally { fs.closeSync(descriptor) }
  try {
    assert.throws(() => readBoundedJson(detailPath, 'test detail'), /bounded byte policy before read/)
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})
