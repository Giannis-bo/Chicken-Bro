'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { randomUUID } = require('node:crypto')
const { readBoundedFile } = require('./bounded-file')

const maxStructuredDetailBytes = 1024 * 1024

function writeBoundedJsonAtomic(filePath, value, label) {
  const serialized = `${JSON.stringify(value, null, 2)}\n`
  if (Buffer.byteLength(serialized) > maxStructuredDetailBytes) throw new Error(`${label} exceeds bounded byte policy`)
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const temporaryPath = `${filePath}.tmp-${process.pid}-${randomUUID()}`
  try {
    fs.writeFileSync(temporaryPath, serialized, { flag: 'wx' })
    fs.renameSync(temporaryPath, filePath)
  } finally {
    fs.rmSync(temporaryPath, { force: true })
  }
}

function readBoundedJson(filePath, label) {
  return JSON.parse(readBoundedFile(filePath, maxStructuredDetailBytes, label).toString('utf8'))
}

module.exports = { maxStructuredDetailBytes, readBoundedJson, writeBoundedJsonAtomic }
