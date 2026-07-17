#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const contract = require('../docs/design/current-ui/runtime-asset-slot-mapping-contract.json')

const root = path.resolve(__dirname, '..')

function readDetails(value) {
  const paths = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (paths.length === 0) throw new Error('ASSET_SLOT_DETAIL_PATHS is required')
  return paths.map((detailPath) => JSON.parse(fs.readFileSync(path.resolve(detailPath), 'utf8')))
}

function combineDetails(details) {
  const first = details[0]
  if (details.some((detail) => detail.schemaVersion !== 'wechat-runtime-asset-slot-review-v1')) throw new Error('unsupported asset-slot detail schema')
  if (!/^[a-f\d]{12}$/u.test(first.commit ?? '') || details.some((detail) => detail.commit !== first.commit)) throw new Error('asset-slot detail commits must match')
  const viewportKey = JSON.stringify(first.viewport)
  if (![first.viewport?.width, first.viewport?.height, first.viewport?.dpr].every((value) => Number.isFinite(value) && value > 0) || details.some((detail) => JSON.stringify(detail.viewport) !== viewportKey)) throw new Error('asset-slot detail viewports must match')
  const routes = details.flatMap((detail) => detail.routes ?? [])
  const routeNames = routes.map((route) => route.route)
  if (new Set(routeNames).size !== routeNames.length) throw new Error('asset-slot detail routes must not repeat')
  const expectedRoutes = contract.routes.map((route) => route.route)
  if (expectedRoutes.some((route) => !routeNames.includes(route)) || routeNames.some((route) => !expectedRoutes.includes(route))) throw new Error('asset-slot detail must cover the exact 14-route contract')
  if (routes.some((route) => route.status !== 'pass' || route.missingAssetElements !== 0 || route.failures.length !== 0 || route.semanticMappings.length !== route.slotCount)) throw new Error('only complete passing asset-slot reviews may be promoted')
  const byRoute = new Map(routes.map((route) => [route.route, route]))
  return {
    schemaVersion: 'wechat-runtime-asset-slot-evidence-v1',
    commit: first.commit,
    viewport: first.viewport,
    routes: expectedRoutes.map((route) => byRoute.get(route)),
  }
}

function main() {
  const evidence = combineDetails(readDetails(process.env.ASSET_SLOT_DETAIL_PATHS))
  const serialized = `${JSON.stringify(evidence, null, 2)}\n`
  const sha256 = crypto.createHash('sha256').update(serialized).digest('hex')
  const viewport = evidence.viewport
  const viewportName = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', evidence.commit, viewportName, 'asset-slots', `${sha256}.json`)
  const destination = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  if (fs.existsSync(destination)) {
    const existingSha = crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex')
    if (existingSha !== sha256) throw new Error(`immutable asset-slot evidence collision: ${relativePath}`)
  } else {
    fs.writeFileSync(destination, serialized, { flag: 'wx' })
  }
  console.log(JSON.stringify({ status: 'pass', commit: evidence.commit, viewport: viewportName, routeCount: evidence.routes.length, visibleElements: evidence.routes.reduce((sum, route) => sum + route.elementCount, 0), visibleSlots: evidence.routes.reduce((sum, route) => sum + route.slotCount, 0), sha256, evidencePath: relativePath.split(path.sep).join('/') }))
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { combineDetails, readDetails }
