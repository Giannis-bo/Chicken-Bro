#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { readBoundedFile } = require('./bounded-file')

const root = path.resolve(__dirname, '..')
const rasterRoot = path.join(root, 'packages/design-system/assets/raster')
const maximumCollections = 64
const maximumAssets = 1024
const maximumManifestBytes = 1024 * 1024
const maximumRuntimeAssetBytes = 8 * 1024 * 1024

function hashBoundedFile(filePath, maximumBytes) {
  const descriptor = fs.openSync(filePath, 'r')
  try {
    const before = fs.fstatSync(descriptor)
    if (before.size > maximumBytes) throw new Error(`runtime asset byte cap exceeded: ${before.size}/${maximumBytes}`)
    const hash = crypto.createHash('sha256')
    const buffer = Buffer.allocUnsafe(64 * 1024)
    let bytes = 0
    while (bytes < before.size) {
      const read = fs.readSync(descriptor, buffer, 0, Math.min(buffer.length, before.size - bytes), bytes)
      if (read === 0) break
      hash.update(buffer.subarray(0, read))
      bytes += read
    }
    const after = fs.fstatSync(descriptor)
    if (bytes !== before.size || after.size !== before.size) throw new Error('runtime asset changed while hashing')
    return { bytes, sha256: hash.digest('hex') }
  } finally {
    fs.closeSync(descriptor)
  }
}

function runtimeRecords(collectionRoot, asset) {
  if (asset.runtime && typeof asset.runtime === 'object') {
    return ['1x', '2x'].map((density) => {
      const record = asset.runtime[density]
      return record ? { density, path: path.resolve(root, record.path), bytes: record.bytes, sha256: record.sha256 } : null
    }).filter(Boolean)
  }
  return ['1x', '2x'].map((density) => ({
    density,
    path: path.resolve(collectionRoot, asset[`path${density}`]),
    bytes: asset.bytes?.[density],
    sha256: asset.hash?.[density],
  }))
}

function main() {
  const manifests = fs.readdirSync(rasterRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && fs.existsSync(path.join(rasterRoot, entry.name, 'manifest.json')))
    .map((entry) => ({ collection: entry.name, root: path.join(rasterRoot, entry.name), manifest: JSON.parse(readBoundedFile(path.join(rasterRoot, entry.name, 'manifest.json'), maximumManifestBytes, 'raster manifest').toString('utf8')) }))
  if (manifests.length > maximumCollections) throw new Error(`raster collection cap exceeded: ${manifests.length}/${maximumCollections}`)
  const failures = []
  let assetCount = 0
  let fileCount = 0
  let totalBytes = 0
  for (const collection of manifests) {
    for (const asset of collection.manifest.assets ?? []) {
      assetCount += 1
      if (assetCount > maximumAssets) throw new Error(`raster asset cap exceeded: ${assetCount}/${maximumAssets}`)
      const records = runtimeRecords(collection.root, asset)
      if (records.length !== 2) failures.push(`${collection.collection}:${asset.assetId}: expected 1x and 2x runtime records`)
      for (const record of records) {
        fileCount += 1
        if (!fs.existsSync(record.path)) {
          failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset missing`)
          continue
        }
        const content = hashBoundedFile(record.path, maximumRuntimeAssetBytes)
        totalBytes += content.bytes
        if (content.bytes !== record.bytes) failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset byte mismatch`)
        if (content.sha256 !== record.sha256) failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset hash mismatch`)
      }
    }
  }
  console.log(JSON.stringify({
    status: failures.length === 0 ? 'pass' : 'fail',
    collectionCount: manifests.length,
    assetCount,
    fileCount,
    totalBytes,
    failureCount: failures.length,
    failures: failures.slice(0, 10),
  }))
  if (failures.length > 0) process.exitCode = 1
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { hashBoundedFile, runtimeRecords }
