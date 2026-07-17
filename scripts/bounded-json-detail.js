'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { randomUUID } = require('node:crypto')

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
  const resolved = path.resolve(filePath)
  const descriptor = fs.openSync(resolved, 'r')
  try {
    const bytesBeforeRead = fs.fstatSync(descriptor).size
    if (bytesBeforeRead <= 0 || bytesBeforeRead > maxStructuredDetailBytes) {
      throw new Error(`${label} exceeds bounded byte policy before read`)
    }

    const buffer = Buffer.allocUnsafe(maxStructuredDetailBytes + 1)
    let bytesRead = 0
    while (bytesRead < buffer.length) {
      const currentRead = fs.readSync(descriptor, buffer, bytesRead, buffer.length - bytesRead, null)
      if (currentRead === 0) break
      bytesRead += currentRead
    }
    if (bytesRead <= 0 || bytesRead > maxStructuredDetailBytes) {
      throw new Error(`${label} exceeds bounded byte policy during read`)
    }
    if (fs.fstatSync(descriptor).size !== bytesBeforeRead) {
      throw new Error(`${label} changed during bounded read`)
    }
    return JSON.parse(buffer.subarray(0, bytesRead).toString('utf8'))
  } finally {
    fs.closeSync(descriptor)
  }
}

module.exports = { maxStructuredDetailBytes, readBoundedJson, writeBoundedJsonAtomic }
