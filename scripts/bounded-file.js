'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { randomUUID } = require('node:crypto')

function readBoundedFile(filePath, maxBytes, label) {
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) throw new Error(`${label} has an invalid byte limit`)
  const resolvedPath = path.resolve(filePath)
  if (fs.lstatSync(resolvedPath).isSymbolicLink()) throw new Error(`${label} refuses symbolic links`)
  let descriptor
  try {
    descriptor = fs.openSync(resolvedPath, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0))
  } catch (error) {
    if (error?.code === 'ELOOP') throw new Error(`${label} refuses symbolic links`)
    throw error
  }
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

function writeBoundedFileImmutable(filePath, buffer, maxBytes, label) {
  if (!Buffer.isBuffer(buffer) || buffer.length <= 0 || buffer.length > maxBytes) {
    throw new Error(`${label} exceeds bounded immutable byte policy`)
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  const assertExisting = () => {
    const existing = readBoundedFile(filePath, maxBytes, label)
    if (!existing.equals(buffer)) throw new Error(`${label} immutable collision`)
  }
  if (fs.existsSync(filePath)) {
    assertExisting()
    return
  }

  const temporaryPath = `${filePath}.tmp-${process.pid}-${randomUUID()}`
  try {
    fs.writeFileSync(temporaryPath, buffer, { flag: 'wx' })
    try {
      fs.linkSync(temporaryPath, filePath)
    } catch (error) {
      if (error?.code !== 'EEXIST') throw error
      assertExisting()
    }
  } finally {
    fs.rmSync(temporaryPath, { force: true })
  }
}

module.exports = { readBoundedFile, writeBoundedFileImmutable }
