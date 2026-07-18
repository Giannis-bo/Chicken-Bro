'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { normalizeSystemViewport } = require('../scripts/wechat-viewport')

test('normalizes safe-area evidence in window coordinates for every UI verifier', () => {
  assert.deepEqual(normalizeSystemViewport({
    windowWidth: 390,
    windowHeight: 844,
    screenHeight: 900,
    pixelRatio: 3,
    safeArea: { top: 47, bottom: 810 },
  }, { left: 296, top: 51, width: 87, height: 32 }), {
    width: 390,
    height: 844,
    dpr: 3,
    safeTop: 47,
    safeBottom: 34,
    safeAreaBottom: 810,
    safeBottomInset: 34,
    capsuleBounds: [296, 51, 87, 32],
  })
})

test('clamps malformed platform safe-area coordinates to the measured window', () => {
  const viewport = normalizeSystemViewport({
    windowWidth: 375,
    windowHeight: 667,
    pixelRatio: 2,
    safeArea: { top: -4, bottom: 900 },
  }, { left: 280, top: 24, width: 87, height: 32 })
  assert.equal(viewport.safeTop, 0)
  assert.equal(viewport.safeAreaBottom, 667)
  assert.equal(viewport.safeBottom, 0)
  assert.throws(() => normalizeSystemViewport({ windowWidth: 0, windowHeight: 667, pixelRatio: 2 }, {}), /windowWidth/)
  assert.throws(() => normalizeSystemViewport({ windowWidth: 375, windowHeight: 667, pixelRatio: 2 }, {}), /menu button bounds/)
  assert.throws(() => normalizeSystemViewport({ windowWidth: 375, windowHeight: 667, pixelRatio: 2 }, { left: 350, top: 24, width: 87, height: 32 }), /fit the measured window/)
})

test('converts capsule top from screen coordinates to window coordinates', () => {
  const viewport = normalizeSystemViewport({
    windowWidth: 390,
    windowHeight: 844,
    screenTop: 24,
    pixelRatio: 3,
  }, { left: 296, top: 75, width: 87, height: 32 })
  assert.deepEqual(viewport.capsuleBounds, [296, 51, 87, 32])
})
