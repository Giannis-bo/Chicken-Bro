'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { classToken, validateContract } = require('../scripts/verify-ui-asset-slots')

test('runtime asset-slot mapping resolves every conceptual and shared slot', () => {
  assert.doesNotThrow(() => validateContract())
})

test('runtime asset-slot ids normalize to WeChat data-selector class tokens', () => {
  assert.equal(classToken('asset_slot.news-detail-source-crest'), 'asset_slot-news-detail-source-crest')
  assert.equal(classToken('asset_slot.utility-glyph-family'), 'asset_slot-utility-glyph-family')
})
