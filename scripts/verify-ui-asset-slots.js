#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { connectMiniProgram, timeout } = require('./wechat-automator')
const { requireOnlineRouteBatch } = require('./online-route-batch')
const contract = require('../docs/design/current-ui/runtime-asset-slot-mapping-contract.json')

const root = path.resolve(__dirname, '..')
const operationTimeoutMs = 10000
const maxAssetSlotDetailBytes = 1024 * 1024

function classToken(slotId) {
  return slotId.replace(/[^a-zA-Z0-9_-]+/gu, '-')
}

function selectedRoutes() {
  const requestedRoutes = requireOnlineRouteBatch(process.env.ASSET_SLOT_ROUTES, 'ASSET_SLOT_ROUTES', contract.routes.map((route) => route.route))
  return contract.routes.filter((route) => requestedRoutes.has(route.route))
}

async function inspect(miniProgram, route) {
  const page = await timeout(miniProgram.reLaunch(route.path), operationTimeoutMs, `open ${route.route}`)
  await new Promise((resolve) => setTimeout(resolve, 650))
  const [elements, materialOwnerElements] = await Promise.all([
    timeout(page.$$('[class*="wx-data-slot-id-"]'), 5000, `query slots ${route.route}`),
    timeout(page.$$('[class*="wx-data-material-owner-"]'), 5000, `query material owners ${route.route}`),
  ])
  const observations = await Promise.all(elements.map(async (element) => ({
    className: await timeout(element.attribute('class'), 1500, 'read slot class'),
    assetId: await timeout(element.attribute('data-asset-id'), 1500, 'read asset id'),
    promotionStatus: await timeout(element.attribute('data-promotion-status'), 1500, 'read promotion status'),
  })))
  const classes = observations.map((observation) => observation.className)
  const observedTokens = [...new Set(classes.flatMap((className) => (
    [...String(className ?? '').matchAll(/(?:^|\s)wx-data-slot-id-([^\s]+)/gu)].map((match) => match[1])
  )))].sort()
  const configuredByToken = new Map(Object.keys(route.runtimeSlots).map((slotId) => [classToken(slotId), slotId]))
  const unknown = observedTokens.filter((token) => !configuredByToken.has(token))
  const missingAssetElements = classes.filter((className) => String(className ?? '').includes('wx-data-asset-missing-true')).length
  const assetObservations = observations.filter((observation) => Boolean(observation.assetId))
  const validPromotionStatuses = new Set(['production_promoted', 'candidate_pending_review', 'missing'])
  const missingPromotionStatusElements = assetObservations.filter((observation) => !validPromotionStatuses.has(observation.promotionStatus)).length
  const promotionCounts = Object.fromEntries([...validPromotionStatuses].map((status) => [status, assetObservations.filter((observation) => observation.promotionStatus === status).length]))
  const materialOwners = await Promise.all(materialOwnerElements.map((element) => timeout(element.attribute('data-material-owner'), 1500, 'read material owner')))
  const validMaterialOwners = new Set(['asset', 'css'])
  const invalidMaterialOwnerElements = materialOwners.filter((owner) => !validMaterialOwners.has(owner)).length
  const materialOwnerCounts = Object.fromEntries([...validMaterialOwners].map((owner) => [owner, materialOwners.filter((value) => value === owner).length]))
  const semanticMappings = observedTokens.filter((token) => configuredByToken.has(token)).map((token) => {
    const runtimeSlot = configuredByToken.get(token)
    return { runtimeSlot, contractSlot: route.runtimeSlots[runtimeSlot] }
  })
  const failures = [
    ...(elements.length === 0 ? ['no visible asset elements'] : []),
    ...(observedTokens.length === 0 ? ['no visible runtime slots'] : []),
    ...unknown.map((token) => `unregistered runtime slot ${token}`),
    ...(missingAssetElements ? [`${missingAssetElements} visible asset elements report missing=true`] : []),
    ...(missingPromotionStatusElements ? [`${missingPromotionStatusElements} visible asset elements lack a valid promotion status`] : []),
    ...(invalidMaterialOwnerElements ? [`${invalidMaterialOwnerElements} controls declare an invalid material owner`] : []),
  ]
  return { route: route.route, status: failures.length === 0 ? 'pass' : 'fail', elementCount: elements.length, assetElementCount: assetObservations.length, slotCount: observedTokens.length, missingAssetElements, missingPromotionStatusElements, materialOwnerElementCount: materialOwnerElements.length, invalidMaterialOwnerElements, materialOwnerCounts, promotionCounts, semanticMappings, failures }
}

function validateContract() {
  for (const route of contract.routes) {
    const assetContract = JSON.parse(fs.readFileSync(path.join(root, route.assetContract), 'utf8'))
    const conceptualSlots = new Set(assetContract.slots.map((slot) => slot.slotId ?? slot.id))
    for (const [runtimeSlot, contractSlot] of Object.entries(route.runtimeSlots)) {
      if (!runtimeSlot.startsWith('asset_slot.')) throw new Error(`${route.route}: invalid runtime slot ${runtimeSlot}`)
      if (contractSlot.startsWith('shared:')) {
        if (!Object.hasOwn(contract.sharedSlots, contractSlot.slice('shared:'.length))) throw new Error(`${route.route}: unknown shared slot ${contractSlot}`)
      } else if (!conceptualSlots.has(contractSlot)) throw new Error(`${route.route}: unknown conceptual slot ${contractSlot}`)
    }
  }
}

async function main() {
  validateContract()
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const system = await timeout(miniProgram.systemInfo(), 4000, 'read system info')
    const viewport = { width: system.windowWidth, height: system.windowHeight, dpr: system.pixelRatio }
    const results = []
    for (const route of selectedRoutes()) results.push(await inspect(miniProgram, route))
    const failures = results.filter((result) => result.status === 'fail')
    let detailPath = null
    if (process.env.ASSET_SLOT_DETAIL_PATH) {
      detailPath = path.resolve(process.env.ASSET_SLOT_DETAIL_PATH)
      fs.mkdirSync(path.dirname(detailPath), { recursive: true })
      const commit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
      const serialized = `${JSON.stringify({ schemaVersion: 'wechat-runtime-asset-slot-review-v3', commit, viewport, routes: results }, null, 2)}\n`
      if (Buffer.byteLength(serialized) > maxAssetSlotDetailBytes) throw new Error('asset-slot detail exceeds bounded byte policy')
      const temporaryPath = `${detailPath}.tmp`
      fs.writeFileSync(temporaryPath, serialized)
      fs.renameSync(temporaryPath, detailPath)
    }
    console.log(JSON.stringify({ status: failures.length === 0 ? 'pass' : 'fail', viewport, checkedRoutes: results.length, visibleElements: results.reduce((sum, result) => sum + result.elementCount, 0), visibleAssetElements: results.reduce((sum, result) => sum + result.assetElementCount, 0), visibleSlots: results.reduce((sum, result) => sum + result.slotCount, 0), visibleMaterialOwners: results.reduce((sum, result) => sum + result.materialOwnerElementCount, 0), invalidMaterialOwnerElements: results.reduce((sum, result) => sum + result.invalidMaterialOwnerElements, 0), missingAssetElements: results.reduce((sum, result) => sum + result.missingAssetElements, 0), missingPromotionStatusElements: results.reduce((sum, result) => sum + result.missingPromotionStatusElements, 0), promotionCounts: { productionPromoted: results.reduce((sum, result) => sum + result.promotionCounts.production_promoted, 0), candidatePendingReview: results.reduce((sum, result) => sum + result.promotionCounts.candidate_pending_review, 0), missing: results.reduce((sum, result) => sum + result.promotionCounts.missing, 0) }, failureCount: failures.length, failedRoutes: failures.slice(0, 10).map((result) => result.route), detailPath }))
    if (failures.length > 0) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

if (require.main === module) {
  main().catch((error) => { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) })
}

module.exports = { classToken, selectedRoutes, validateContract }
