#!/usr/bin/env node
'use strict'

const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const appRoot = path.join(root, 'apps/mini-taro')
const auditRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-mini-package-'))
const defaultAssetRuntimeRoot = '/assets/ui-v2'
const placeholderRemoteAssetRuntimeRoot = 'https://assets.example.invalid/wow-assets/releases/2026-07-18-ui-v2'
const remoteAssetRuntimeRoot = process.env.WOW_ASSET_RUNTIME_ROOT || placeholderRemoteAssetRuntimeRoot
const requireProductionReady = process.argv.includes('--require-production-ready')
const limits = {
  remoteTotalBytes: 2 * 1024 * 1024,
  commonJsBytes: 420 * 1024,
  commonWxssBytes: 400 * 1024,
}
const localAssetSources = [
  ['vector', 'packages/design-system/assets/vector'],
  ['raster/news-home-v1/runtime/2x', 'packages/design-system/assets/raster/news-home-v1/runtime/2x'],
  ['raster/builds-home-v1/runtime/2x', 'packages/design-system/assets/raster/builds-home-v1/runtime/2x'],
  ['raster/shared-chrome-v1/runtime/2x', 'packages/design-system/assets/raster/shared-chrome-v1/runtime/2x'],
  ['raster/news-list-v1/runtime/2x', 'packages/design-system/assets/raster/news-list-v1/runtime/2x'],
  ['raster/news-detail-v1/runtime/2x', 'packages/design-system/assets/raster/news-detail-v1/runtime/2x'],
  ['raster/build-intel-v1/runtime/2x', 'packages/design-system/assets/raster/build-intel-v1/runtime/2x'],
]

function walk(directory) {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name)
    return entry.isDirectory() ? walk(target) : [target]
  })
}

function countStringLiteral(source, value) {
  return source.split(JSON.stringify(value)).length - 1
    + source.split(`'${value}'`).length - 1
}

function isProductionAssetRoot(value) {
  try {
    const url = new URL(value)
    return url.protocol === 'https:'
      && url.hostname !== 'localhost'
      && !url.hostname.endsWith('.invalid')
      && !/^\d+(?:\.\d+){3}$/u.test(url.hostname)
  } catch {
    return false
  }
}

function build(name, assetRuntimeRoot = '') {
  const outputRoot = path.join(auditRoot, name)
  const result = spawnSync(path.join(root, 'node_modules/.bin/taro'), ['build', '--type', 'weapp'], {
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
    const diagnostic = `${result.stderr || ''}\n${result.stdout || ''}`.trim().slice(-4000)
    throw new Error(`${name} production build failed\n${diagnostic}`)
  }
  const files = walk(outputRoot).filter((file) => !file.endsWith('.map'))
  const packageText = files
    .filter((file) => /\.(?:js|json|wxml|wxss)$/u.test(file))
    .map((file) => fs.readFileSync(file, 'utf8'))
    .join('\n')
  const assetRoot = path.join(outputRoot, 'assets', 'ui-v2')
  const assetFiles = files
    .filter((file) => file.startsWith(assetRoot + path.sep))
    .map((file) => path.relative(assetRoot, file).split(path.sep).join('/'))
    .sort()
  return {
    outputRoot,
    totalBytes: files.reduce((total, file) => total + fs.statSync(file).size, 0),
    assetFileCount: assetFiles.length,
    assetFiles,
    configuredRootReferenceCount: countStringLiteral(packageText, assetRuntimeRoot || defaultAssetRuntimeRoot),
    defaultRootReferenceCount: countStringLiteral(packageText, defaultAssetRuntimeRoot),
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
  if (missingLocalAssetFiles.length) failures.push(`local build is missing ${missingLocalAssetFiles.length} registered asset files: ${missingLocalAssetFiles.slice(0, 5).join(', ')}`)
  if (unexpectedLocalAssetFiles.length) failures.push(`local build has ${unexpectedLocalAssetFiles.length} unexpected asset files: ${unexpectedLocalAssetFiles.slice(0, 5).join(', ')}`)
  if (remote.assetFileCount !== 0) failures.push(`remote build copied ${remote.assetFileCount} local asset files`)
  if (local.configuredRootReferenceCount === 0) failures.push('local build does not contain the default asset runtime root')
  if (remote.configuredRootReferenceCount === 0) failures.push('remote build does not contain the configured HTTPS asset runtime root')
  if (remote.defaultRootReferenceCount > 1) failures.push(`remote build contains ${remote.defaultRootReferenceCount} default local asset root references; only the manifest fallback definition is allowed`)
  if (remote.totalBytes > limits.remoteTotalBytes) failures.push(`remote build is ${remote.totalBytes} bytes`)
  if (remote.commonJsBytes > limits.commonJsBytes) failures.push(`common.js is ${remote.commonJsBytes} bytes`)
  if (remote.commonWxssBytes > limits.commonWxssBytes) failures.push(`common.wxss is ${remote.commonWxssBytes} bytes`)
  const packageMechanicsPass = failures.length === 0
  const releaseBlockers = []
  if (!isProductionAssetRoot(remoteAssetRuntimeRoot)) releaseBlockers.push('WOW_ASSET_RUNTIME_ROOT must be an approved HTTPS named origin')
  const releaseReady = packageMechanicsPass && releaseBlockers.length === 0
  console.log(JSON.stringify({
    status: packageMechanicsPass ? (releaseReady ? 'pass' : 'partial') : 'fail',
    evidence: 'isolated_production_weapp_package',
    packageMechanicsPass,
    releaseReady,
    remoteAssetOrigin: isProductionAssetRoot(remoteAssetRuntimeRoot) ? new URL(remoteAssetRuntimeRoot).origin : 'not_configured',
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
    remote: { ...remote, outputRoot: '<temporary>', assetFiles: undefined },
    failures,
  }, null, 2))
  if (!packageMechanicsPass || (requireProductionReady && !releaseReady)) process.exitCode = 1
} finally {
  fs.rmSync(auditRoot, { recursive: true, force: true })
}
