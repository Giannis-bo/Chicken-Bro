'use strict'

const net = require('node:net')

function isProductionNamedHttps(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:'
      && url.hostname !== 'localhost'
      && !url.hostname.endsWith('.invalid')
      && net.isIP(url.hostname) === 0
  } catch {
    return false
  }
}

function releaseDomainBlockers({ assetRuntimeRoot, backendApiBaseUrl, wechatRequestDomainApproved }) {
  const blockers = []
  if (!isProductionNamedHttps(assetRuntimeRoot)) blockers.push('WOW_ASSET_RUNTIME_ROOT must be an approved HTTPS named origin')
  if (!isProductionNamedHttps(backendApiBaseUrl)) blockers.push('WOW_BACKEND_API_BASE_URL must be an approved HTTPS named origin')
  if (!wechatRequestDomainApproved) blockers.push('WOW_WECHAT_REQUEST_DOMAIN_APPROVED must be explicit yes')
  return blockers
}

module.exports = { isProductionNamedHttps, releaseDomainBlockers }
