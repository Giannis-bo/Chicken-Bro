'use strict'

const net = require('node:net')
const { isImmutableRemoteAssetRoot } = require('../packages/assets-manifest/src/runtime-root.cjs')

function parseProductionNamedHttps(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:'
      && url.hostname !== 'localhost'
      && !url.hostname.endsWith('.invalid')
      && net.isIP(url.hostname) === 0
      && !url.username
      && !url.password
      ? url
      : null
  } catch {
    return null
  }
}

function isProductionAssetRuntimeRoot(value) {
  return Boolean(parseProductionNamedHttps(value) && isImmutableRemoteAssetRoot(value))
}

function isProductionBackendOrigin(value) {
  const url = parseProductionNamedHttps(value)
  return Boolean(url && url.pathname === '/' && !url.search && !url.hash)
}

function releaseDomainBlockers({ assetRuntimeRoot, backendApiBaseUrl, wechatRequestDomainApproved }) {
  const blockers = []
  if (!isProductionAssetRuntimeRoot(assetRuntimeRoot)) blockers.push('WOW_ASSET_RUNTIME_ROOT must be an approved named HTTPS immutable /releases/<release-id> path')
  if (!isProductionBackendOrigin(backendApiBaseUrl)) blockers.push('WOW_BACKEND_API_BASE_URL must be an approved HTTPS named origin')
  if (!wechatRequestDomainApproved) blockers.push('WOW_WECHAT_REQUEST_DOMAIN_APPROVED must be explicit yes')
  return blockers
}

module.exports = { isProductionAssetRuntimeRoot, isProductionBackendOrigin, releaseDomainBlockers }
