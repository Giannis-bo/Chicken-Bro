#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const contract = require('../docs/design/current-ui/runtime-region-mapping-contract.json')

const root = path.resolve(__dirname, '..')

function targetBounds(region) {
  const bounds = region.boundsPx ?? region.bounds
  if (!bounds || !['x', 'y', 'width', 'height'].every((key) => Number.isFinite(bounds[key]))) throw new Error(`invalid target bounds: ${region.id}`)
  return bounds
}

function round(value) {
  return Math.round(value * 1000) / 1000
}

function compareRoute(mapping, runtimeRoute) {
  const target = JSON.parse(fs.readFileSync(path.join(root, mapping.targetGeometry), 'utf8'))
  const targetById = new Map(target.regions.map((region) => [region.id, region]))
  const runtimeById = new Map(runtimeRoute.regions.filter((region) => region.visibleSlot).map((region) => [region.id, region]))
  const pairs = Object.entries(mapping.regions).map(([targetId, runtimeId]) => {
    const targetRegion = targetById.get(targetId)
    const runtimeRegion = runtimeById.get(runtimeId)
    if (!targetRegion || !runtimeRegion) throw new Error(`${mapping.route}: missing region mapping ${targetId} -> ${runtimeId}`)
    return { targetId, runtimeId, target: targetBounds(targetRegion), runtime: runtimeRegion }
  })
  const first = pairs.find((pair) => pair.targetId === mapping.anchorTop)
  const last = pairs.find((pair) => pair.targetId === mapping.anchorBottom)
  if (!first || !last) throw new Error(`${mapping.route}: mapping anchors are absent`)
  const scaleX = first.runtime.width / first.target.width
  const translateX = first.runtime.left - first.target.x * scaleX
  const targetVerticalSpan = last.target.y + last.target.height - first.target.y
  const runtimeVerticalSpan = last.runtime.bottom - first.runtime.top
  const scaleY = runtimeVerticalSpan / targetVerticalSpan
  const translateY = first.runtime.top - first.target.y * scaleY
  const regions = pairs.map((pair) => {
    const expected = {
      left: pair.target.x * scaleX + translateX,
      top: pair.target.y * scaleY + translateY,
      width: pair.target.width * scaleX,
      height: pair.target.height * scaleY,
    }
    const delta = {
      left: round(pair.runtime.left - expected.left),
      top: round(pair.runtime.top - expected.top),
      width: round(pair.runtime.width - expected.width),
      height: round(pair.runtime.height - expected.height),
    }
    const pass = Math.abs(delta.left) <= contract.tolerance.positionPx
      && Math.abs(delta.top) <= contract.tolerance.positionPx
      && Math.abs(delta.width) <= contract.tolerance.sizePx
      && Math.abs(delta.height) <= contract.tolerance.sizePx
    return { id: pair.targetId, runtimeId: pair.runtimeId, targetBounds: pair.target, runtimeBounds: pair.runtime, delta, tolerance: contract.tolerance, status: pass ? 'PASS' : 'FAIL' }
  })
  return {
    route: mapping.route,
    targetGeometry: mapping.targetGeometry,
    targetMapping: { scaleX: round(scaleX), scaleY: round(scaleY), translateX: round(translateX), translateY: round(translateY), contentOrigin: mapping.anchorTop },
    regions,
    status: regions.every((region) => region.status === 'PASS') ? 'PASS' : 'FAIL',
  }
}

function main() {
  const detailPath = path.resolve(process.env.GEOMETRY_DETAIL_PATH ?? '')
  if (!process.env.GEOMETRY_DETAIL_PATH) throw new Error('GEOMETRY_DETAIL_PATH is required')
  const runtime = JSON.parse(fs.readFileSync(detailPath, 'utf8'))
  if (runtime.schemaVersion !== 'wechat-route-geometry-detail-v1') throw new Error('unsupported geometry detail schema')
  if (!/^[a-f\d]{12}$/u.test(runtime.commit ?? '')) throw new Error('runtime geometry detail commit is missing')
  const comparisons = contract.routes.map((mapping) => {
    const runtimeRoute = runtime.routes.find((route) => route.route === mapping.route)
    if (!runtimeRoute) throw new Error(`runtime geometry missing route: ${mapping.route}`)
    return compareRoute(mapping, runtimeRoute)
  })
  const record = { schemaVersion: 'target-runtime-region-comparison-v1', commit: runtime.commit, viewport: runtime.viewport, tolerance: contract.tolerance, routes: comparisons }
  let outputPath = null
  if (process.env.REGION_COMPARISON_OUTPUT) {
    outputPath = path.resolve(process.env.REGION_COMPARISON_OUTPUT)
    fs.mkdirSync(path.dirname(outputPath), { recursive: true })
    fs.writeFileSync(outputPath, `${JSON.stringify(record, null, 2)}\n`)
  }
  const failed = comparisons.filter((comparison) => comparison.status === 'FAIL')
  console.log(JSON.stringify({ status: failed.length === 0 ? 'pass' : 'fail', checkedRoutes: comparisons.length, checkedRegions: comparisons.reduce((sum, item) => sum + item.regions.length, 0), failedRoutes: failed.map((item) => item.route), outputPath }))
  if (failed.length > 0) process.exitCode = 1
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { compareRoute, targetBounds }
