'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { randomUUID } = require('node:crypto')
const { readBoundedFile } = require('./bounded-file')

const maxStructuredDetailBytes = 1024 * 1024
const maxStructuredDetailFiles = 14

function boundedDetailPaths(value, environmentName) {
  const paths = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (paths.length === 0) throw new Error(`${environmentName} is required`)
  if (paths.length > maxStructuredDetailFiles) throw new Error(`${environmentName} accepts at most ${maxStructuredDetailFiles} bounded detail files`)
  return paths
}

function serializeBoundedJson(value, label) {
  const serialized = `${JSON.stringify(value, null, 2)}\n`
  if (Buffer.byteLength(serialized) > maxStructuredDetailBytes) throw new Error(`${label} exceeds bounded byte policy`)
  return serialized
}

function writeBoundedJsonAtomic(filePath, value, label) {
  const serialized = serializeBoundedJson(value, label)
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

module.exports = {
  boundedDetailPaths,
  maxStructuredDetailBytes,
  maxStructuredDetailFiles,
  readBoundedJson,
  serializeBoundedJson,
  writeBoundedJsonAtomic,
}
