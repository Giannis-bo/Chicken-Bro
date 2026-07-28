const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  collectManifestV2ReaderAudit,
} = require('../scripts/audit-gear-manifest-v2-readers')

function fixture(files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'manifest-v2-readers-'))
  for (const [relativePath, content] of Object.entries(files)) {
    const target = path.join(root, relativePath)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, content)
  }
  return root
}

test('reports zero prohibited callers when every runtime reader is Manifest-bound', () => {
  const root = fixture({
    'server/runtime.py': [
      'store.get_active_gear_exact_registry()',
      'store.load_active_manifest_public_gear(binding)',
      'store.load_candidate_manifest_binding(revision)',
    ].join('\n'),
  })
  const report = collectManifestV2ReaderAudit({
    root,
    allowlist: ['server/runtime.py'],
  })
  assert.equal(report.status, 'verified')
  assert.equal(report.prohibitedCallerCount, 0)
  assert.deepEqual(report.missingBoundReaders, [])
})

test('blocks latest Exact Registry callers', () => {
  const root = fixture({
    'server/runtime.py': [
      'store.get_latest_gear_exact_registry()',
      'store.get_active_gear_exact_registry()',
      'store.load_active_manifest_public_gear(binding)',
      'store.load_candidate_manifest_binding(revision)',
    ].join('\n'),
  })
  const report = collectManifestV2ReaderAudit({
    root,
    allowlist: ['server/runtime.py'],
  })
  assert.equal(report.status, 'blocked')
  assert.equal(report.prohibitedCallerCount, 1)
  assert.equal(
    report.prohibitedCallers[0].symbol,
    'get_latest_gear_exact_registry',
  )
})
