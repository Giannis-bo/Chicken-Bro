#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const http = require('node:http')
const https = require('node:https')
const path = require('node:path')
const { isProductionBackendOrigin } = require('./release-domain-policy')

const root = path.resolve(__dirname, '..')
const shouldProbe = process.argv.includes('--probe')
const requireProductionReady = process.argv.includes('--require-production-ready')

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function safeOrigin(value) {
  if (!value) return ''
  try {
    return new URL(value).origin
  } catch {
    return ''
  }
}

function probe(urlString) {
  return new Promise((resolve) => {
    const startedAt = Date.now()
    const url = new URL(urlString)
    const client = url.protocol === 'https:' ? https : http
    const request = client.get(url, {
      timeout: 8000,
      ...(url.protocol === 'https:' ? { rejectUnauthorized: false } : {}),
    }, (response) => {
      response.resume()
      response.once('end', () => resolve({
        url: `${url.origin}${url.pathname}`,
        reachable: Boolean(response.statusCode && response.statusCode < 500),
        statusCode: response.statusCode || 0,
        elapsedMs: Date.now() - startedAt,
        error: '',
      }))
    })
    request.once('timeout', () => request.destroy(new Error('timeout')))
    request.once('error', (error) => resolve({
      url: `${url.origin}${url.pathname}`,
      reachable: false,
      statusCode: 0,
      elapsedMs: Date.now() - startedAt,
      error: error.message,
    }))
  })
}

async function main() {
  const transportSource = read('packages/api-client/src/transport.ts')
  const configSource = read('apps/mini-taro/config/index.ts')
  const projectConfig = JSON.parse(read('apps/mini-taro/project.config.json'))
  const devBaseMatch = transportSource.match(/DEV_API_BASE_URL\s*=\s*'([^']+)'/)
  const proxyTargetMatch = configSource.match(/target:\s*'([^']+)'/)
  const developmentBaseUrl = devBaseMatch?.[1] ?? ''
  const h5ProxyTarget = proxyTargetMatch?.[1] ?? ''
  const productionOrigin = safeOrigin(process.env.WOW_BACKEND_API_BASE_URL || '')
  const productionUrl = productionOrigin ? new URL(productionOrigin) : null
  const approvedInWechatAdmin = process.env.WOW_WECHAT_REQUEST_DOMAIN_APPROVED === 'yes'
  const productionHttpsOrigin = Boolean(productionUrl && isProductionBackendOrigin(productionOrigin))
  const devtoolsDomainBypassCommitted = projectConfig.setting?.urlCheck === false
  const productionReady = productionHttpsOrigin && approvedInWechatAdmin && !devtoolsDomainBypassCommitted
  const probes = shouldProbe && developmentBaseUrl
    ? await Promise.all([probe(`${developmentBaseUrl}/api/data/health`)])
    : []

  const checks = [
    {
      id: 'development_base_is_named_https_origin',
      pass: isProductionBackendOrigin(developmentBaseUrl),
      scope: 'development_fact',
      detail: safeOrigin(developmentBaseUrl),
    },
    {
      id: 'h5_proxy_matches_development_backend',
      pass: h5ProxyTarget === developmentBaseUrl,
      scope: 'development_parity',
      detail: safeOrigin(h5ProxyTarget),
    },
    {
      id: 'insecure_authenticated_requests_fail_closed',
      pass: transportSource.includes('insecure api base url for authenticated request'),
      scope: 'data_trust',
      detail: null,
    },
    {
      id: 'domain_bypass_not_committed_as_release_config',
      pass: !devtoolsDomainBypassCommitted,
      scope: 'release_safety',
      detail: projectConfig.setting?.urlCheck ?? 'not_set',
    },
    {
      id: 'production_backend_is_https_named_origin',
      pass: productionHttpsOrigin,
      scope: 'production_gate',
      detail: productionOrigin || 'not_configured',
    },
    {
      id: 'wechat_admin_request_domain_approval_recorded',
      pass: approvedInWechatAdmin,
      scope: 'production_gate',
      detail: approvedInWechatAdmin ? 'explicit_yes' : 'missing',
    },
  ]
  const report = {
    version: 'current-ui-request-domain-audit-v2',
    authority: 'docs/plans/ui-reconstruction.md',
    checkedAt: new Date().toISOString(),
    status: productionReady ? 'pass' : 'partial',
    productionReady,
    development: {
      baseOrigin: safeOrigin(developmentBaseUrl),
      h5ProxyOrigin: safeOrigin(h5ProxyTarget),
      wechatDomainExpectation: 'allowed_after_api.chickenbro.cloud_is_registered_as_a_request_domain',
      devtoolsDomainBypassCommitted,
      probes,
    },
    production: {
      origin: productionOrigin || '',
      httpsNamedOrigin: productionHttpsOrigin,
      approvedInWechatAdmin,
      requiredEnvironment: {
        WOW_BACKEND_API_BASE_URL: 'https://approved.example',
        WOW_WECHAT_REQUEST_DOMAIN_APPROVED: 'yes',
      },
    },
    checks,
  }
  console.log(JSON.stringify(report, null, 2))
  if (requireProductionReady && !productionReady) process.exitCode = 1
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
