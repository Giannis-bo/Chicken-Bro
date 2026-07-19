'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { finalizeWeappBuild } = require('../scripts/finalize-weapp-build')

test('finalizeWeappBuild emits a file-change event only after app.js exists', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-weapp-finalize-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  const entryPath = path.join(root, 'app.js')
  fs.writeFileSync(entryPath, 'App({})\n')
  const before = fs.statSync(entryPath).mtimeMs
  const result = finalizeWeappBuild(root)
  const after = fs.statSync(entryPath).mtimeMs
  assert.equal(result.entryPath, entryPath)
  assert.ok(after > before)
})

test('finalizeWeappBuild refuses a missing build entry', (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-weapp-finalize-missing-'))
  t.after(() => fs.rmSync(root, { recursive: true, force: true }))
  assert.throws(() => finalizeWeappBuild(root), /ENOENT/u)
})
