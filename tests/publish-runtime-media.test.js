'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const {
  collectIconUrls,
  discoverSelections,
  runtimeMediaFallbackCandidates,
  validateReleaseId,
  validateRemoteManifest,
} = require('../scripts/publish-runtime-media')

test('runtime media discovery collects only trusted icon fields and deduplicates them', () => {
  const result = collectIconUrls({
    iconUrl: 'https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
    nested: [
      { specIconUrl: 'https://render.worldofwarcraft.com/us/icons/56/spell_frost.jpg' },
      { iconUrl: 'https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg' },
      { sourceUrl: 'https://untrusted.example/source.jpg' },
    ],
  })
  assert.deepEqual([...result.found].sort(), [
    'https://render.worldofwarcraft.com/us/icons/56/spell_frost.jpg',
    'https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
  ])
  assert.deepEqual(result.invalid, [])
})

test('runtime media discovery reports an untrusted fact-bearing icon', () => {
  const result = collectIconUrls({ iconUrl: 'https://evil.example/icon.jpg' })
  assert.equal(result.found.size, 0)
  assert.deepEqual(result.invalid, [{ key: 'iconUrl', value: 'https://evil.example/icon.jpg' }])
})

test('class/spec discovery unifies home and bootstrap identities', () => {
  assert.deepEqual(discoverSelections(
    { classOptions: [{ websimClassKey: 'mage', specializations: [{ websimSpecKey: 'frost' }] }] },
    { classes: [{ key: 'mage', specs: [{ key: 'frost' }, { key: 'fire' }] }] },
  ), [
    { classKey: 'mage', specKey: 'fire' },
    { classKey: 'mage', specKey: 'frost' },
  ])
})

test('known missing Wowhead objects resolve through an audited official render fallback', () => {
  assert.deepEqual(runtimeMediaFallbackCandidates(
    'https://wow.zamimg.com/images/wow/icons/large/spell_frostfireorb.jpg',
  ), [
    'https://render.worldofwarcraft.com/us/icons/56/spell_frostfireorb.jpg',
  ])
  assert.deepEqual(runtimeMediaFallbackCandidates(
    'https://wow.zamimg.com/images/wow/icons/large/ability_demonhunter_specdevourer.jpg',
  ), [
    'https://wow.zamimg.com/images/wow/icons/large/classicon_demonhunter_void.jpg',
    'https://render.worldofwarcraft.com/us/icons/56/ability_demonhunter_specdevourer.jpg',
  ])
})

test('runtime media release ids are immutable URL-safe identifiers', () => {
  assert.equal(validateReleaseId('2026-07-19-wow-icons-v1'), '2026-07-19-wow-icons-v1')
  for (const value of ['short', 'Latest-release', '../escape', 'release?x=1']) {
    assert.throws(() => validateReleaseId(value))
  }
})

test('remote manifest validation checks identity, count, bytes, and hash shape', () => {
  const releaseId = '2026-07-19-wow-icons-v1'
  const manifest = {
    schemaVersion: 1,
    releaseId,
    selectionCount: 40,
    fileCount: 1,
    totalBytes: 3,
    files: [{
      path: 'sources/wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
      bytes: 3,
      sha256: 'a'.repeat(64),
    }],
  }
  assert.equal(validateRemoteManifest(manifest, releaseId), manifest)
  assert.throws(() => validateRemoteManifest({ ...manifest, totalBytes: 4 }, releaseId))
  assert.throws(() => validateRemoteManifest({ ...manifest, releaseId: 'other-release' }, releaseId))
})
