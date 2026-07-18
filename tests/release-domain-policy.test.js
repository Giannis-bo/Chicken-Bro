'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { isProductionAssetRuntimeRoot, isProductionBackendOrigin, releaseDomainBlockers } = require('../scripts/release-domain-policy')

test('backend release domain requires a credential-free named HTTPS origin', () => {
  assert.equal(isProductionBackendOrigin('https://api.example.com'), true)
  assert.equal(isProductionBackendOrigin('https://api.example.com/'), true)
  for (const value of ['', 'http://api.example.com', 'https://localhost', 'https://124.223.51.33', 'https://api.example.invalid']) {
    assert.equal(isProductionBackendOrigin(value), false, value)
  }
  for (const value of ['https://user@api.example.com', 'https://api.example.com/v1', 'https://api.example.com?x=1', 'https://api.example.com/#release']) {
    assert.equal(isProductionBackendOrigin(value), false, value)
  }
})

test('asset release domain requires the authoritative immutable release path', () => {
  assert.equal(isProductionAssetRuntimeRoot('https://assets.example.com/wow-assets/releases/release-v1'), true)
  for (const value of ['https://assets.example.com', 'https://assets.example.com/releases/short', 'https://124.223.51.33/releases/release-v1', 'https://assets.example.invalid/releases/release-v1']) {
    assert.equal(isProductionAssetRuntimeRoot(value), false, value)
  }
})

test('release blockers close asset, backend and WeChat approval independently', () => {
  assert.deepEqual(releaseDomainBlockers({ assetRuntimeRoot: '', backendApiBaseUrl: '', wechatRequestDomainApproved: false }), [
    'WOW_ASSET_RUNTIME_ROOT must be an approved named HTTPS immutable /releases/<release-id> path',
    'WOW_BACKEND_API_BASE_URL must be an approved HTTPS named origin',
    'WOW_WECHAT_REQUEST_DOMAIN_APPROVED must be explicit yes',
  ])
  assert.deepEqual(releaseDomainBlockers({
    assetRuntimeRoot: 'https://assets.example.com/wow-assets/releases/release-v1',
    backendApiBaseUrl: 'https://api.example.com',
    wechatRequestDomainApproved: true,
  }), [])
})
