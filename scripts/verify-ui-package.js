#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { readBoundedFile } = require('./bounded-file')
const {
  isProductionAssetRuntimeRoot,
  isProductionBackendOrigin,
  isProductionRuntimeMediaRoot,
  releaseDomainBlockers,
} = require('./release-domain-policy')

const root = path.resolve(__dirname, '..')
const appRoot = path.join(root, 'apps/mini-taro')
const taroCliEntry = path.join(root, 'node_modules', '@tarojs', 'cli', 'bin', 'taro')
const auditRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-mini-package-'))
const defaultAssetRuntimeRoot = '/assets/ui-v2'
const placeholderRemoteAssetRuntimeRoot = 'https://assets.example.invalid/wow-assets/releases/2026-07-18-ui-v2'
const remoteAssetRuntimeRoot = process.env.WOW_ASSET_RUNTIME_ROOT || placeholderRemoteAssetRuntimeRoot
const runtimeMediaRoot = process.env.WOW_RUNTIME_MEDIA_ROOT || ''
const backendApiBaseUrl = process.env.WOW_BACKEND_API_BASE_URL || ''
const wechatRequestDomainApproved = process.env.WOW_WECHAT_REQUEST_DOMAIN_APPROVED === 'yes'
const requireProductionReady = process.argv.includes('--require-production-ready')
const maximumWalkFiles = 4096
const maximumPackageTextFileBytes = 1024 * 1024
const maximumPackageTextBytes = 4 * 1024 * 1024
const maximumRuntimeMediaManifestBytes = 2 * 1024 * 1024
const limits = {
  remoteTotalBytes: 2 * 1024 * 1024,
  commonJsBytes: 420 * 1024,
  commonWxssBytes: 400 * 1024,
}
const localAssetSources = [
  ['vector-runtime', 'packages/design-system/assets/vector-runtime'],
  ['raster/news-home-v1/runtime/2x', 'packages/design-system/assets/raster/news-home-v1/runtime/2x'],
  ['raster/builds-home-v1/runtime/2x', 'packages/design-system/assets/raster/builds-home-v1/runtime/2x'],
  ['raster/shared-chrome-v1/runtime/2x', 'packages/design-system/assets/raster/shared-chrome-v1/runtime/2x'],
  ['raster/news-list-v1/runtime/2x', 'packages/design-system/assets/raster/news-list-v1/runtime/2x'],
  ['raster/news-detail-v1/runtime/2x', 'packages/design-system/assets/raster/news-detail-v1/runtime/2x'],
  ['raster/build-intel-v1/runtime/2x', 'packages/design-system/assets/raster/build-intel-v1/runtime/2x'],
]

function walk(directory) {
  if (!fs.existsSync(directory)) return []
  const files = []
  const visit = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const target = path.join(current, entry.name)
      if (entry.isDirectory()) visit(target)
      else files.push(target)
      if (files.length > maximumWalkFiles) throw new Error(`package file query cap exceeded: ${files.length}/${maximumWalkFiles}`)
    }
  }
  visit(directory)
  return files
}

function countStringLiteral(source, value) {
  return source.split(JSON.stringify(value)).length - 1
    + source.split(`'${value}'`).length - 1
}

function verifyRuntimeMediaReleaseRoot(value) {
  if (!value) return { status: 'not_configured' }
  if (!isProductionRuntimeMediaRoot(value)) {
    return { status: 'failed', reason: 'root is not an approved named HTTPS immutable release' }
  }
  const rootUrl = new URL(value)
  const releaseId = rootUrl.pathname.replace(/\/+$/u, '').split('/').pop()
  const manifestUrl = `${value.replace(/\/+$/u, '')}/release-manifest.json`
  const response = spawnSync('curl', [
    '--fail', '--silent', '--show-error', '--max-time', '20', manifestUrl,
  ], {
    encoding: 'utf8',
    maxBuffer: maximumRuntimeMediaManifestBytes,
  })
  if (response.status !== 0) {
    const reason = (response.error?.message || response.stderr || response.stdout || 'request failed').trim().slice(-500)
    return { status: 'failed', releaseId, manifestUrl, reason }
  }
  let manifest
  try {
    manifest = JSON.parse(response.stdout)
  } catch {
    return { status: 'failed', releaseId, manifestUrl, reason: 'release manifest is not valid JSON' }
  }
  const files = Array.isArray(manifest?.files) ? manifest.files : []
  const valid = manifest?.schemaVersion === 1
    && manifest?.releaseId === releaseId
    && manifest?.immutableRoot === value.replace(/\/+$/u, '')
    && Number.isInteger(manifest?.fileCount)
    && manifest.fileCount > 0
    && files.length === manifest.fileCount
    && Number.isInteger(manifest?.totalBytes)
    && manifest.totalBytes > 0
  return valid
    ? { status: 'pass', releaseId, manifestUrl, fileCount: manifest.fileCount, totalBytes: manifest.totalBytes }
    : { status: 'failed', releaseId, manifestUrl, reason: 'release manifest identity or file inventory is invalid' }
}

function build(name, assetRuntimeRoot = '') {
  const outputRoot = path.join(auditRoot, name)
  const result = spawnSync(process.execPath, [taroCliEntry, 'build', '--type', 'weapp'], {
    cwd: appRoot,
    encoding: 'utf8',
    env: {
      ...process.env,
      NODE_ENV: 'production',
      WOW_TARO_ISOLATED_BUILD: '1',
      WOW_TARO_OUTPUT_ROOT: outputRoot,
      WOW_ASSET_RUNTIME_ROOT: assetRuntimeRoot,
    },
    maxBuffer: 2 * 1024 * 1024,
  })
  if (result.status !== 0) {
    const diagnostic = `${result.error?.stack || result.error?.message || ''}\n${result.stderr || ''}\n${result.stdout || ''}`.trim().slice(-4000)
    throw new Error(`${name} production build failed\n${diagnostic}`)
  }
  const files = walk(outputRoot).filter((file) => !file.endsWith('.map'))
  const packageTextFiles = files.filter((file) => /\.(?:js|json|wxml|wxss)$/u.test(file))
  const packageTextBytes = packageTextFiles.reduce((total, file) => total + fs.statSync(file).size, 0)
  if (packageTextBytes > maximumPackageTextBytes) throw new Error(`package text byte cap exceeded: ${packageTextBytes}/${maximumPackageTextBytes}`)
  const packageText = packageTextFiles
    .map((file) => readBoundedFile(file, maximumPackageTextFileBytes, 'package text file').toString('utf8'))
    .join('\n')
  const assetRoot = path.join(outputRoot, 'assets', 'ui-v2')
  const assetFiles = files
    .filter((file) => file.startsWith(assetRoot + path.sep))
    .map((file) => path.relative(assetRoot, file).split(path.sep).join('/'))
    .sort()
  return {
    outputRoot,
    totalBytes: files.reduce((total, file) => total + fs.statSync(file).size, 0),
    fileCount: files.length,
    packageTextBytes,
    assetFileCount: assetFiles.length,
    assetFiles,
    configuredRootReferenceCount: countStringLiteral(packageText, assetRuntimeRoot || defaultAssetRuntimeRoot),
    defaultRootReferenceCount: countStringLiteral(packageText, defaultAssetRuntimeRoot),
    backendOriginReferenceCount: backendApiBaseUrl ? countStringLiteral(packageText, backendApiBaseUrl) : 0,
    runtimeBackendEnvReferenceCount: packageText.split('WOW_BACKEND_API_BASE_URL').length - 1,
    commonJsBytes: fs.statSync(path.join(outputRoot, 'common.js')).size,
    commonWxssBytes: fs.statSync(path.join(outputRoot, 'common.wxss')).size,
  }
}

try {
  const local = build('local')
  const remote = build('remote', remoteAssetRuntimeRoot)
  const failures = []
  const expectedLocalAssetFiles = localAssetSources.flatMap(([outputPrefix, sourceRoot]) => {
    const absoluteSourceRoot = path.join(root, sourceRoot)
    return walk(absoluteSourceRoot).map((file) => (
      `${outputPrefix}/${path.relative(absoluteSourceRoot, file).split(path.sep).join('/')}`
    ))
  }).sort()
  const missingLocalAssetFiles = expectedLocalAssetFiles.filter((file) => !local.assetFiles.includes(file))
  const unexpectedLocalAssetFiles = local.assetFiles.filter((file) => !expectedLocalAssetFiles.includes(file))
  const expectedRemoteAssetFiles = expectedLocalAssetFiles.filter((file) => file.startsWith('vector-runtime/'))
  const missingRemoteAssetFiles = expectedRemoteAssetFiles.filter((file) => !remote.assetFiles.includes(file))
  const unexpectedRemoteAssetFiles = remote.assetFiles.filter((file) => !expectedRemoteAssetFiles.includes(file))
  if (missingLocalAssetFiles.length) failures.push(`local build is missing ${missingLocalAssetFiles.length} registered asset files: ${missingLocalAssetFiles.slice(0, 5).join(', ')}`)
  if (unexpectedLocalAssetFiles.length) failures.push(`local build has ${unexpectedLocalAssetFiles.length} unexpected asset files: ${unexpectedLocalAssetFiles.slice(0, 5).join(', ')}`)
  if (missingRemoteAssetFiles.length) failures.push(`remote build is missing ${missingRemoteAssetFiles.length} local vector files: ${missingRemoteAssetFiles.slice(0, 5).join(', ')}`)
  if (unexpectedRemoteAssetFiles.length) failures.push(`remote build copied ${unexpectedRemoteAssetFiles.length} unexpected local asset files: ${unexpectedRemoteAssetFiles.slice(0, 5).join(', ')}`)
  if (local.configuredRootReferenceCount === 0) failures.push('local build does not contain the default asset runtime root')
  if (remote.configuredRootReferenceCount === 0) failures.push('remote build does not contain the configured HTTPS asset runtime root')
  if (remote.defaultRootReferenceCount > 1) failures.push(`remote build contains ${remote.defaultRootReferenceCount} default local asset root references; only the manifest fallback definition is allowed`)
  if (local.runtimeBackendEnvReferenceCount || remote.runtimeBackendEnvReferenceCount) {
    failures.push('weapp package still contains a runtime WOW_BACKEND_API_BASE_URL lookup')
  }
  if (backendApiBaseUrl && (!local.backendOriginReferenceCount || !remote.backendOriginReferenceCount)) {
    failures.push('weapp package does not contain the configured backend API origin')
  }
  if (remote.totalBytes > limits.remoteTotalBytes) failures.push(`remote build is ${remote.totalBytes} bytes`)
  if (remote.commonJsBytes > limits.commonJsBytes) failures.push(`common.js is ${remote.commonJsBytes} bytes`)
  if (remote.commonWxssBytes > limits.commonWxssBytes) failures.push(`common.wxss is ${remote.commonWxssBytes} bytes`)
  const packageMechanicsPass = failures.length === 0
  const runtimeMediaRelease = verifyRuntimeMediaReleaseRoot(runtimeMediaRoot)
  const releaseBlockers = releaseDomainBlockers({
    assetRuntimeRoot: remoteAssetRuntimeRoot,
    runtimeMediaRoot,
    backendApiBaseUrl,
    wechatRequestDomainApproved,
  })
  if (runtimeMediaRelease.status === 'failed') {
    releaseBlockers.push(`WOW_RUNTIME_MEDIA_ROOT is not a readable immutable release: ${runtimeMediaRelease.reason}`)
  }
  const releaseReady = packageMechanicsPass && releaseBlockers.length === 0
  console.log(JSON.stringify({
    status: packageMechanicsPass ? (releaseReady ? 'pass' : 'partial') : 'fail',
    evidence: 'isolated_production_weapp_package',
    packageMechanicsPass,
    releaseReady,
    remoteAssetOrigin: isProductionAssetRuntimeRoot(remoteAssetRuntimeRoot) ? new URL(remoteAssetRuntimeRoot).origin : 'not_configured',
    runtimeMediaOrigin: isProductionRuntimeMediaRoot(runtimeMediaRoot) ? new URL(runtimeMediaRoot).origin : 'not_configured',
    runtimeMediaRelease,
    backendApiOrigin: isProductionBackendOrigin(backendApiBaseUrl) ? new URL(backendApiBaseUrl).origin : 'not_configured',
    wechatRequestDomainApproved,
    releaseBlockers,
    limits,
    local: {
      ...local,
      outputRoot: '<temporary>',
      assetFiles: undefined,
      expectedAssetFileCount: expectedLocalAssetFiles.length,
      missingAssetFileCount: missingLocalAssetFiles.length,
      unexpectedAssetFileCount: unexpectedLocalAssetFiles.length,
    },
    remote: {
      ...remote,
      outputRoot: '<temporary>',
      assetFiles: undefined,
      expectedVectorAssetFileCount: expectedRemoteAssetFiles.length,
      missingVectorAssetFileCount: missingRemoteAssetFiles.length,
      unexpectedLocalAssetFileCount: unexpectedRemoteAssetFiles.length,
    },
    failures,
  }, null, 2))
  if (!packageMechanicsPass || (requireProductionReady && !releaseReady)) process.exitCode = 1
} finally {
  fs.rmSync(auditRoot, { recursive: true, force: true })
}
