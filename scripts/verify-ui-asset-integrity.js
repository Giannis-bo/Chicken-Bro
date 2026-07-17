#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const rasterRoot = path.join(root, 'packages/design-system/assets/raster')

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
    .map((entry) => ({ collection: entry.name, root: path.join(rasterRoot, entry.name), manifest: JSON.parse(fs.readFileSync(path.join(rasterRoot, entry.name, 'manifest.json'), 'utf8')) }))
  const failures = []
  let assetCount = 0
  let fileCount = 0
  let totalBytes = 0
  for (const collection of manifests) {
    for (const asset of collection.manifest.assets ?? []) {
      assetCount += 1
      const records = runtimeRecords(collection.root, asset)
      if (records.length !== 2) failures.push(`${collection.collection}:${asset.assetId}: expected 1x and 2x runtime records`)
      for (const record of records) {
        fileCount += 1
        if (!fs.existsSync(record.path)) {
          failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset missing`)
          continue
        }
        const content = fs.readFileSync(record.path)
        totalBytes += content.length
        if (content.length !== record.bytes) failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset byte mismatch`)
        const sha256 = crypto.createHash('sha256').update(content).digest('hex')
        if (sha256 !== record.sha256) failures.push(`${collection.collection}:${asset.assetId}:${record.density}: runtime asset hash mismatch`)
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

module.exports = { runtimeRecords }
