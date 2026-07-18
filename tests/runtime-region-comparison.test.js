'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const test = require('node:test')

const { compareRoute } = require('../scripts/compare-ui-runtime-regions')

const contract = JSON.parse(fs.readFileSync('docs/design/current-ui/runtime-region-mapping-contract.json', 'utf8'))

function transformedRuntime(mapping, scaleX = 0.45, scaleY = 0.44, translateX = 0, translateY = 47) {
  const target = JSON.parse(fs.readFileSync(mapping.targetGeometry, 'utf8'))
  return {
    route: mapping.route,
    regions: Object.entries(mapping.regions).map(([targetId, runtimeId]) => {
      const region = target.regions.find((candidate) => candidate.id === targetId)
      const bounds = region.boundsPx ?? region.bounds
      const left = bounds.x * scaleX + translateX
      const top = bounds.y * scaleY + translateY
      const width = bounds.width * scaleX
      const height = bounds.height * scaleY
      return { id: runtimeId, visibleSlot: true, left, top, width, height, right: left + width, bottom: top + height }
    }),
  }
}

test('semantic target/runtime comparison accepts an affine region match', () => {
  const mapping = contract.routes[0]
  const comparison = compareRoute(mapping, transformedRuntime(mapping))
  assert.equal(comparison.status, 'PASS')
  assert.ok(comparison.regions.every((region) => region.status === 'PASS'))
})

test('semantic target/runtime comparison rejects residual drift beyond tolerance', () => {
  const mapping = contract.routes[0]
  const runtime = transformedRuntime(mapping)
  runtime.regions[2].top += contract.tolerance.positionPx + 1
  runtime.regions[2].bottom += contract.tolerance.positionPx + 1
  const comparison = compareRoute(mapping, runtime)
  assert.equal(comparison.status, 'FAIL')
  assert.equal(comparison.regions[2].status, 'FAIL')
})
