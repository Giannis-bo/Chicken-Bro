'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { isProductionNamedHttps, releaseDomainBlockers } = require('../scripts/release-domain-policy')

test('release domains require a named non-placeholder HTTPS origin', () => {
  assert.equal(isProductionNamedHttps('https://api.example.com'), true)
  for (const value of ['', 'http://api.example.com', 'https://localhost', 'https://124.223.51.33', 'https://api.example.invalid']) {
    assert.equal(isProductionNamedHttps(value), false, value)
  }
})

test('release blockers close asset, backend and WeChat approval independently', () => {
  assert.deepEqual(releaseDomainBlockers({ assetRuntimeRoot: '', backendApiBaseUrl: '', wechatRequestDomainApproved: false }), [
    'WOW_ASSET_RUNTIME_ROOT must be an approved HTTPS named origin',
    'WOW_BACKEND_API_BASE_URL must be an approved HTTPS named origin',
    'WOW_WECHAT_REQUEST_DOMAIN_APPROVED must be explicit yes',
  ])
  assert.deepEqual(releaseDomainBlockers({
    assetRuntimeRoot: 'https://assets.example.com/wow-assets/releases/release-v1',
    backendApiBaseUrl: 'https://api.example.com',
    wechatRequestDomainApproved: true,
  }), [])
})
