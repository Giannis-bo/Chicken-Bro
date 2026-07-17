'use strict'

const fs = require('node:fs')
const path = require('node:path')

const maxStructuredDetailBytes = 1024 * 1024

function writeBoundedJsonAtomic(filePath, value, label) {
  const serialized = `${JSON.stringify(value, null, 2)}\n`
  if (Buffer.byteLength(serialized) > maxStructuredDetailBytes) throw new Error(`${label} exceeds bounded byte policy`)
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const temporaryPath = `${filePath}.tmp-${process.pid}`
  try {
    fs.writeFileSync(temporaryPath, serialized, { flag: 'wx' })
    fs.renameSync(temporaryPath, filePath)
  } finally {
    fs.rmSync(temporaryPath, { force: true })
  }
}

function readBoundedJson(filePath, label) {
  const resolved = path.resolve(filePath)
  const bytes = fs.statSync(resolved).size
  if (bytes <= 0 || bytes > maxStructuredDetailBytes) throw new Error(`${label} exceeds bounded byte policy before read`)
  return JSON.parse(fs.readFileSync(resolved, 'utf8'))
}

module.exports = { maxStructuredDetailBytes, readBoundedJson, writeBoundedJsonAtomic }
