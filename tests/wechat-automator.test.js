'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const {
  hasRenderedRoot,
  readSemanticValue,
} = require('../scripts/wechat-automator')

test('hasRenderedRoot rejects the transient empty Taro root', () => {
  assert.equal(hasRenderedRoot({ root: { cn: [] } }), false)
  assert.equal(hasRenderedRoot({ root: { cn: [{ type: 'view' }] } }), true)
})

test('readSemanticValue prefers a rendered data attribute', async () => {
  const element = {
    attribute: async (name) => name === 'data-selected' ? 'true' : 'wx-data-selected-false',
  }
  assert.equal(await readSemanticValue(element, 'selected'), 'true')
})

test('readSemanticValue falls back to the WeChat selector marker class', async () => {
  const element = {
    attribute: async (name) => name === 'class'
      ? 'control wx-data-material-owner-css wx-data-leading-boundary-active'
      : null,
  }
  assert.equal(await readSemanticValue(element, 'material-owner'), 'css')
  assert.equal(await readSemanticValue(element, 'data-leading-boundary'), 'active')
})
