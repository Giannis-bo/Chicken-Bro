'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { readBoundedFile, writeBoundedFileImmutable } = require('../scripts/bounded-file')

test('immutable bounded files are idempotent and reject content collisions', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-bounded-immutable-'))
  const destination = path.join(directory, 'evidence.json')
  try {
    writeBoundedFileImmutable(destination, Buffer.from('evidence'), 32, 'test evidence')
    writeBoundedFileImmutable(destination, Buffer.from('evidence'), 32, 'test evidence')
    assert.equal(readBoundedFile(destination, 32, 'test evidence').toString(), 'evidence')
    assert.throws(
      () => writeBoundedFileImmutable(destination, Buffer.from('collision'), 32, 'test evidence'),
      /immutable collision/,
    )
    assert.equal(fs.readdirSync(directory).some((file) => file.includes('.tmp-')), false)
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})

test('immutable bounded files reject oversized payloads before writing', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-bounded-immutable-size-'))
  const destination = path.join(directory, 'evidence.json')
  try {
    assert.throws(
      () => writeBoundedFileImmutable(destination, Buffer.alloc(33), 32, 'test evidence'),
      /bounded immutable byte policy/,
    )
    assert.equal(fs.existsSync(destination), false)
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})
