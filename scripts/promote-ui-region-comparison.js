#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const path = require('node:path')
const contract = require('../docs/design/current-ui/runtime-region-mapping-contract.json')
const { readBoundedFile, writeBoundedFileImmutable } = require('./bounded-file')
const { maxStructuredDetailBytes } = require('./bounded-json-detail')

const root = path.resolve(__dirname, '..')

function inspectComparison(comparisonPath) {
  const buffer = readBoundedFile(comparisonPath, maxStructuredDetailBytes, 'target/runtime region comparison')
  const comparison = JSON.parse(buffer.toString('utf8'))
  if (comparison.schemaVersion !== 'target-runtime-region-comparison-v1') throw new Error('unsupported region comparison schema')
  if (!/^[a-f\d]{12}$/u.test(comparison.commit ?? '')) throw new Error('region comparison commit must be a 12-character Git SHA')
  if (![comparison.viewport?.width, comparison.viewport?.height, comparison.viewport?.dpr].every((value) => Number.isFinite(value) && value > 0)) throw new Error('region comparison viewport is incomplete')
  const expectedRoutes = contract.routes.map((route) => route.route)
  const routeNames = Array.isArray(comparison.routes) ? comparison.routes.map((route) => route.route) : []
  if (routeNames.length !== expectedRoutes.length || new Set(routeNames).size !== routeNames.length || expectedRoutes.some((route) => !routeNames.includes(route))) {
    throw new Error('region comparison must cover the exact mapping contract')
  }
  if (comparison.routes.some((route) => route.status !== 'PASS' || !Array.isArray(route.regions) || route.regions.length === 0 || route.regions.some((region) => region.status !== 'PASS'))) {
    throw new Error('only complete passing region comparisons may be promoted')
  }
  return { buffer, comparison, sha256: crypto.createHash('sha256').update(buffer).digest('hex') }
}

function main() {
  if (!process.env.REGION_COMPARISON_PATH) throw new Error('REGION_COMPARISON_PATH is required')
  const sourcePath = path.resolve(process.env.REGION_COMPARISON_PATH)
  const inspected = inspectComparison(sourcePath)
  const viewport = inspected.comparison.viewport
  const viewportKey = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', inspected.comparison.commit, viewportKey, 'comparisons', `${inspected.sha256}.json`)
  const destination = path.join(root, relativePath)
  writeBoundedFileImmutable(destination, inspected.buffer, maxStructuredDetailBytes, `region comparison ${relativePath}`)
  console.log(JSON.stringify({ status: 'pass', commit: inspected.comparison.commit, viewport: viewportKey, routeCount: inspected.comparison.routes.length, regionCount: inspected.comparison.routes.reduce((sum, route) => sum + route.regions.length, 0), sha256: inspected.sha256, comparisonPath: relativePath.split(path.sep).join('/') }))
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { inspectComparison }
