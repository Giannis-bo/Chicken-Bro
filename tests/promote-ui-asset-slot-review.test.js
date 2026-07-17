'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const contract = require('../docs/design/current-ui/runtime-asset-slot-mapping-contract.json')
const { combineDetails, readDetails } = require('../scripts/promote-ui-asset-slot-review')

function routeDetail(route) {
  return { route, status: 'pass', elementCount: 1, assetElementCount: 1, slotCount: 1, missingAssetElements: 0, missingPromotionStatusElements: 0, materialOwnerElementCount: 0, invalidMaterialOwnerElements: 0, materialOwnerCounts: { asset: 0, css: 0 }, promotionCounts: { production_promoted: 0, candidate_pending_review: 1, missing: 0 }, semanticMappings: [{ runtimeSlot: 'asset_slot.test', contractSlot: 'shared:asset_slot.utility-glyph-family' }], failures: [] }
}

function batches() {
  const routes = contract.routes.map((route) => routeDetail(route.route))
  const base = { schemaVersion: 'wechat-runtime-asset-slot-review-v3', commit: 'a'.repeat(12), viewport: { width: 390, height: 844, dpr: 3 } }
  return [{ ...base, routes: routes.slice(0, 7) }, { ...base, routes: routes.slice(7) }]
}

test('asset-slot promotion merges an exact 14-route passing closure', () => {
  const evidence = combineDetails(batches())
  assert.equal(evidence.routes.length, 14)
  assert.deepEqual(evidence.routes.map((route) => route.route), contract.routes.map((route) => route.route))
})

test('asset-slot promotion rejects repeated, mismatched or failing batches', () => {
  const repeated = batches()
  repeated[1].routes[0] = repeated[0].routes[0]
  assert.throws(() => combineDetails(repeated), /must not repeat/)
  const mismatched = batches()
  mismatched[1].commit = 'b'.repeat(12)
  assert.throws(() => combineDetails(mismatched), /commits must match/)
  const failing = batches()
  failing[0].routes[0].missingAssetElements = 1
  assert.throws(() => combineDetails(failing), /only complete passing/)
  const missingPromotion = batches()
  missingPromotion[0].routes[0].missingPromotionStatusElements = 1
  assert.throws(() => combineDetails(missingPromotion), /only complete passing/)
  const invalidOwner = batches()
  invalidOwner[0].routes[0].materialOwnerElementCount = 1
  invalidOwner[0].routes[0].invalidMaterialOwnerElements = 1
  assert.throws(() => combineDetails(invalidOwner), /only complete passing/)
})

test('asset-slot promotion rejects oversized detail before loading JSON', () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'wow-asset-slot-detail-bound-'))
  const detailPath = path.join(directory, 'oversized.json')
  const descriptor = fs.openSync(detailPath, 'w')
  try {
    fs.ftruncateSync(descriptor, 1024 * 1024 + 1)
  } finally {
    fs.closeSync(descriptor)
  }
  try {
    assert.throws(() => readDetails(detailPath), /bounded byte policy before read/)
  } finally {
    fs.rmSync(directory, { recursive: true, force: true })
  }
})
