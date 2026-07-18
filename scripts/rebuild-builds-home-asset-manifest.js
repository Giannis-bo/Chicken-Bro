#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')
const assetRoot = path.join(root, 'packages/design-system/assets/raster/builds-home-v1')
const manifestPath = path.join(assetRoot, 'manifest.json')

const recordNames = {
  evidence: 'evidence-medallions-record.json',
  frames: 'frame-family-record.json',
  support: 'support-ornaments-record.json',
  surface: 'surface-texture-record.json',
}

const slots = [
  ['asset_slot.builds-surface-texture', 'surfaces'],
  ['asset_slot.builds-frame-family', 'frames'],
  ['asset_slot.builds-specialization-medallion', 'specialization'],
  ['asset_slot.builds-evidence-medallions', 'evidence'],
  ['asset_slot.builds-workspace-medallion', 'workspace'],
  ['asset_slot.builds-workflow-medallions', 'workflow'],
  ['asset_slot.builds-workflow-timeline', 'workflow'],
]

const expectedAssetIds = [
  'builds-surface-texture.default',
  'builds-frame.overview',
  'builds-frame.evidence-grid',
  'builds-frame.workspace-gold',
  'builds-frame.evidence-list',
  'builds-frame.workflow',
  'builds-frame.primary-action',
  'builds-specialization-medallion.shell',
  'builds-specialization-medallion.neutral-fallback',
  'builds-specialization-medallion.source-reference-stamp',
  'builds-evidence-medallion.talents',
  'builds-evidence-medallion.gear',
  'builds-evidence-medallion.simc',
  'builds-evidence-medallion.tasks',
  'builds-workspace-medallion.default',
  'builds-workspace-medallion.blocked',
  'builds-workflow-medallion.input',
  'builds-workflow-medallion.validation',
  'builds-workflow-medallion.tracking',
  'builds-workflow-timeline.rail',
  'builds-workflow-timeline.node-active',
  'builds-workflow-timeline.node-pending',
  'builds-workflow-timeline.node-inactive',
]

function readRecord(name) {
  const recordPath = path.join(assetRoot, name)
  if (!fs.existsSync(recordPath)) throw new Error(`Missing record: ${name}`)
  return JSON.parse(fs.readFileSync(recordPath, 'utf8'))
}

function recordStatus(record) {
  return record.reviewStatus ?? record.status
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex')
}

function fileMetadata(relativePath) {
  const absolutePath = path.join(assetRoot, relativePath)
  if (!fs.existsSync(absolutePath)) throw new Error(`Missing asset: ${relativePath}`)
  return {
    bytes: fs.statSync(absolutePath).size,
    sha256: sha256(absolutePath),
  }
}

function slotIdFor(assetId) {
  if (assetId.startsWith('builds-surface-texture.')) return 'asset_slot.builds-surface-texture'
  if (assetId.startsWith('builds-frame.')) return 'asset_slot.builds-frame-family'
  if (assetId.startsWith('builds-specialization-medallion.')) return 'asset_slot.builds-specialization-medallion'
  if (assetId.startsWith('builds-evidence-medallion.')) return 'asset_slot.builds-evidence-medallions'
  if (assetId.startsWith('builds-workspace-medallion.')) return 'asset_slot.builds-workspace-medallion'
  if (assetId.startsWith('builds-workflow-medallion.')) return 'asset_slot.builds-workflow-medallions'
  if (assetId.startsWith('builds-workflow-timeline.')) return 'asset_slot.builds-workflow-timeline'
  throw new Error(`No slot mapping for ${assetId}`)
}

function variantFor(assetId) {
  return assetId.slice(assetId.indexOf('.') + 1)
}

function manifestAsset(assetId, one, two, sourceMaster, extra = {}) {
  const oneActual = fileMetadata(one.path)
  const twoActual = fileMetadata(two.path)
  if (oneActual.bytes !== one.bytes || oneActual.sha256 !== one.sha256) {
    throw new Error(`1x record mismatch: ${assetId}`)
  }
  if (twoActual.bytes !== two.bytes || twoActual.sha256 !== two.sha256) {
    throw new Error(`2x record mismatch: ${assetId}`)
  }
  return {
    assetId,
    slotId: slotIdFor(assetId),
    variant: variantFor(assetId),
    path1x: one.path,
    path2x: two.path,
    dimensions: { '1x': one.dimensions, '2x': two.dimensions },
    bytes: { '1x': one.bytes, '2x': two.bytes },
    hash: { '1x': one.sha256, '2x': two.sha256 },
    sourceClass: 'imagegen_raster',
    sourceMaster,
    reviewStatus: 'generated_pending_isolated_review',
    ...extra,
  }
}

function evidenceAssets(record) {
  const grouped = new Map()
  for (const asset of record.assets) {
    const assetId = asset.assetId.replace(/@(1x|2x)$/, '')
    const density = asset.scale
    const entry = grouped.get(assetId) ?? {}
    entry[density] = asset
    grouped.set(assetId, entry)
  }
  return Array.from(grouped.entries()).map(([assetId, density]) => manifestAsset(
    assetId,
    density['1x'],
    density['2x'],
    record.sourceMaster.path,
    { opticalContentBox2x: density['2x'].opticalBox },
  ))
}

function supportAssets(record) {
  return record.assets.map((asset) => manifestAsset(
    asset.assetId,
    asset.densities['1x'],
    asset.densities['2x'],
    record.sourceMaster.path,
    { opticalContentBox2x: asset.densities['2x'].opticalBox },
  ))
}

function surfaceAssets(record) {
  return [manifestAsset(
    record.assetId,
    {
      path: record.paths['1x'],
      dimensions: record.dimensions['1x'],
      bytes: record.bytes['1x'],
      sha256: record.sha256['1x'],
    },
    {
      path: record.paths['2x'],
      dimensions: record.dimensions['2x'],
      bytes: record.bytes['2x'],
      sha256: record.sha256['2x'],
    },
    record.sourceMaster.path,
  )]
}

function frameDensity(asset, density) {
  if (asset.densities?.[density]) return asset.densities[density]
  const suffix = density === '1x' ? '1x' : '2x'
  const hash = asset.hash?.[suffix] ?? asset.sha256?.[suffix]
  return {
    path: asset[`path${suffix}`] ?? asset[`path${suffix.toUpperCase()}`],
    dimensions: asset.dimensions[suffix],
    bytes: asset.bytes[suffix],
    sha256: hash,
  }
}

function frameAssets(record) {
  return record.assets.map((asset) => manifestAsset(
    asset.assetId,
    frameDensity(asset, '1x'),
    frameDensity(asset, '2x'),
    record.master?.path ?? record.sourceMaster?.path,
    { sliceInset: asset.sliceInset ?? { '1x': 32, '2x': 64 } },
  ))
}

function masterEntry(record, sourceGeneration) {
  const master = record.master ?? record.sourceMaster
  const actual = fileMetadata(master.path)
  if (actual.bytes !== master.bytes || actual.sha256 !== master.sha256) {
    throw new Error(`Master record mismatch: ${master.path}`)
  }
  return {
    path: master.path,
    sourceGeneration,
    dimensions: master.dimensions,
    bytes: master.bytes,
    sha256: master.sha256,
  }
}

const records = {
  evidence: readRecord(recordNames.evidence),
  frames: readRecord(recordNames.frames),
  support: readRecord(recordNames.support),
  surface: readRecord(recordNames.surface),
}

for (const [name, record] of Object.entries(records)) {
  if (recordStatus(record) !== 'generated_pending_isolated_review') {
    throw new Error(`${name} record is not reviewable: ${recordStatus(record)}`)
  }
}

const assets = [
  ...surfaceAssets(records.surface),
  ...frameAssets(records.frames),
  ...supportAssets(records.support),
  ...evidenceAssets(records.evidence),
]

const actualIds = assets.map((asset) => asset.assetId).sort()
const expectedIds = [...expectedAssetIds].sort()
if (JSON.stringify(actualIds) !== JSON.stringify(expectedIds)) {
  throw new Error(`Asset inventory mismatch: ${actualIds.join(', ')}`)
}

const masters = [
  masterEntry({
    master: {
      path: records.surface.sourceMaster.path,
      dimensions: records.surface.dimensions.sourceMaster,
      bytes: records.surface.bytes.sourceMaster,
      sha256: records.surface.sha256.sourceMaster,
    },
  }, records.surface.sourceGeneration.generatedPath),
  masterEntry(records.frames, records.frames.sourcePath ?? records.frames.sourceGeneration?.generatedPath),
  masterEntry(records.support, records.support.provenance.generatedPath),
  masterEntry(records.evidence, records.evidence.sourceGeneration.generatedPath),
]

const manifest = {
  schemaVersion: 1,
  route: 'specialization_home/builds_home',
  status: 'generated_pending_isolated_review',
  assetCount: assets.length,
  masterCount: masters.length,
  slots: slots.map(([slotId]) => ({
    slotId,
    packageLocation: 'packages/design-system/assets/raster/builds-home-v1/runtime',
    reviewStatus: 'generated_pending_isolated_review',
  })),
  masters,
  assets,
}

fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
process.stdout.write(`${JSON.stringify({
  status: 'pass',
  manifest: path.relative(root, manifestPath),
  assetCount: manifest.assetCount,
  masterCount: manifest.masterCount,
  slotCount: manifest.slots.length,
})}\n`)
