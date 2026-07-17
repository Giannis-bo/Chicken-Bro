'use strict'

const fs = require('node:fs')
const path = require('node:path')

function readBoundedFile(filePath, maxBytes, label) {
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) throw new Error(`${label} has an invalid byte limit`)
  const descriptor = fs.openSync(path.resolve(filePath), 'r')
  try {
    const bytesBeforeRead = fs.fstatSync(descriptor).size
    if (bytesBeforeRead <= 0 || bytesBeforeRead > maxBytes) {
      throw new Error(`${label} exceeds bounded byte policy before read`)
    }

    const buffer = Buffer.allocUnsafe(maxBytes + 1)
    let bytesRead = 0
    while (bytesRead < buffer.length) {
      const currentRead = fs.readSync(descriptor, buffer, bytesRead, buffer.length - bytesRead, null)
      if (currentRead === 0) break
      bytesRead += currentRead
    }
    if (bytesRead <= 0 || bytesRead > maxBytes) {
      throw new Error(`${label} exceeds bounded byte policy during read`)
    }
    if (fs.fstatSync(descriptor).size !== bytesBeforeRead) {
      throw new Error(`${label} changed during bounded read`)
    }
    return buffer.subarray(0, bytesRead)
  } finally {
    fs.closeSync(descriptor)
  }
}

module.exports = { readBoundedFile }
