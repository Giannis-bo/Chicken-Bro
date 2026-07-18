#!/usr/bin/env node
'use strict'

const { createHash } = require('node:crypto')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const bucket = process.env.WOW_CDN_COS_BUCKET || 'zhajiduizhang-1257807175'
const region = process.env.WOW_CDN_COS_REGION || 'ap-shanghai'
const publicOrigin = process.env.WOW_CDN_PUBLIC_ORIGIN || 'https://static.chickenbro.cloud'
const releasePrefix = 'wow-assets/releases'
const maximumFiles = 256
const maximumTotalBytes = 8 * 1024 * 1024
const runtimeAssetExtensions = new Set(['.png', '.svg', '.webp'])
const assetSources = [
  ['vector', 'packages/design-system/assets/vector'],
  ['raster/news-home-v1/runtime/2x', 'packages/design-system/assets/raster/news-home-v1/runtime/2x'],
  ['raster/builds-home-v1/runtime/2x', 'packages/design-system/assets/raster/builds-home-v1/runtime/2x'],
  ['raster/shared-chrome-v1/runtime/2x', 'packages/design-system/assets/raster/shared-chrome-v1/runtime/2x'],
  ['raster/news-list-v1/runtime/2x', 'packages/design-system/assets/raster/news-list-v1/runtime/2x'],
  ['raster/news-detail-v1/runtime/2x', 'packages/design-system/assets/raster/news-detail-v1/runtime/2x'],
  ['raster/build-intel-v1/runtime/2x', 'packages/design-system/assets/raster/build-intel-v1/runtime/2x'],
]

function usage() {
  throw new Error('usage: node scripts/publish-ui-cdn-assets.js <prepare|publish|verify> <release-id>')
}

function validateReleaseId(value) {
  if (!/^[a-z0-9][a-z0-9._-]{2,63}$/u.test(value ?? '')) throw new Error('release-id must be 3-64 lowercase URL-safe characters')
  return value
}

function walk(directory) {
  const files = []
  const visit = (current) => {
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const target = path.join(current, entry.name)
      if (entry.isDirectory()) visit(target)
      else files.push(target)
      if (files.length > maximumFiles) throw new Error(`CDN release file cap exceeded: ${files.length}/${maximumFiles}`)
    }
  }
  visit(directory)
  return files
}

function sha256(buffer) {
  return createHash('sha256').update(buffer).digest('hex')
}

function collectAssets() {
  const records = assetSources.flatMap(([prefix, relativeSource]) => {
    const source = path.join(root, relativeSource)
    return walk(source).filter((file) => runtimeAssetExtensions.has(path.extname(file))).map((file) => {
      const bytes = fs.readFileSync(file)
      return {
        path: path.posix.join(prefix, path.relative(source, file).split(path.sep).join('/')),
        bytes: bytes.length,
        sha256: sha256(bytes),
        source: file,
      }
    })
  }).sort((left, right) => left.path.localeCompare(right.path))
  if (records.length > maximumFiles) throw new Error(`CDN release file cap exceeded: ${records.length}/${maximumFiles}`)
  const totalBytes = records.reduce((sum, record) => sum + record.bytes, 0)
  if (totalBytes > maximumTotalBytes) throw new Error(`CDN release byte cap exceeded: ${totalBytes}/${maximumTotalBytes}`)
  return { records, totalBytes }
}

function releaseManifest(releaseId) {
  const { records, totalBytes } = collectAssets()
  return {
    records,
    manifest: {
      schemaVersion: 1,
      releaseId,
      immutableRoot: `${publicOrigin}/${releasePrefix}/${releaseId}`,
      fileCount: records.length,
      totalBytes,
      files: records.map(({ path: filePath, bytes, sha256: hash }) => ({ path: filePath, bytes, sha256: hash })),
    },
  }
}

function buildRelease(releaseId) {
  const { records, manifest } = releaseManifest(releaseId)
  const stagingRoot = fs.mkdtempSync(path.join(os.tmpdir(), `wow-cdn-${releaseId}-`))
  for (const record of records) {
    const destination = path.join(stagingRoot, ...record.path.split('/'))
    fs.mkdirSync(path.dirname(destination), { recursive: true })
    fs.copyFileSync(record.source, destination, fs.constants.COPYFILE_EXCL)
  }
  fs.writeFileSync(path.join(stagingRoot, 'release-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' })
  return { stagingRoot, manifest }
}

async function verifyRelease(releaseId, localManifest) {
  const manifestUrl = `${publicOrigin}/${releasePrefix}/${releaseId}/release-manifest.json`
  const response = await fetch(manifestUrl, { cache: 'no-store', signal: AbortSignal.timeout(10_000) })
  if (!response.ok) throw new Error(`remote manifest request failed: ${response.status} ${manifestUrl}`)
  const remoteManifest = await response.json()
  const expected = localManifest ?? releaseManifest(releaseId).manifest
  if (remoteManifest.releaseId !== releaseId || remoteManifest.fileCount !== expected.fileCount || remoteManifest.totalBytes !== expected.totalBytes) {
    throw new Error('remote CDN release manifest does not match the local release')
  }
  for (const record of expected.files) {
    const assetResponse = await fetch(`${publicOrigin}/${releasePrefix}/${releaseId}/${record.path}`, { signal: AbortSignal.timeout(10_000) })
    if (!assetResponse.ok) throw new Error(`remote asset request failed: ${assetResponse.status} ${record.path}`)
    const bytes = Buffer.from(await assetResponse.arrayBuffer())
    if (bytes.length !== record.bytes || sha256(bytes) !== record.sha256) throw new Error(`remote asset integrity mismatch: ${record.path}`)
  }
  return { status: 'pass', releaseId, publicRoot: expected.immutableRoot, fileCount: expected.fileCount, totalBytes: expected.totalBytes }
}

async function main() {
  const command = process.argv[2]
  const releaseId = validateReleaseId(process.argv[3])
  if (!['prepare', 'publish', 'verify'].includes(command)) usage()
  if (command === 'verify') {
    console.log(JSON.stringify(await verifyRelease(releaseId), null, 2))
    return
  }
  const release = buildRelease(releaseId)
  if (command === 'prepare') {
    console.log(JSON.stringify({ status: 'prepared', releaseId, stagingRoot: release.stagingRoot, publicRoot: release.manifest.immutableRoot, fileCount: release.manifest.fileCount, totalBytes: release.manifest.totalBytes }, null, 2))
    return
  }
  const probe = spawnSync('coscli', ['--version'], { encoding: 'utf8' })
  if (probe.error?.code === 'ENOENT') throw new Error('coscli is required for publish; install and configure it outside the repository, then retry')
  if (probe.status !== 0) throw new Error(`coscli is unavailable: ${(probe.stderr || probe.stdout || '').trim()}`)
  try {
    const target = `cos://${bucket}/${releasePrefix}/${releaseId}/`
    const upload = spawnSync('coscli', ['cp', '-r', `${release.stagingRoot}/`, target, '--region', region], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
    if (upload.status !== 0) throw new Error(`COS upload failed: ${(upload.stderr || upload.stdout || '').trim().slice(-2000)}`)
    console.log(JSON.stringify(await verifyRelease(releaseId, release.manifest), null, 2))
  } finally {
    fs.rmSync(release.stagingRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  console.error(error.message)
  process.exitCode = 1
})
