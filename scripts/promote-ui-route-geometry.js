#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const contract = require('../docs/design/current-ui/route-geometry-contract.json')
const { readBoundedJson } = require('./bounded-json-detail')

const root = path.resolve(__dirname, '..')
const contractPath = path.join(root, 'docs/design/current-ui/route-geometry-contract.json')
const contractSha256 = crypto.createHash('sha256').update(fs.readFileSync(contractPath)).digest('hex')

function readDetails(value) {
  const paths = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (paths.length === 0) throw new Error('GEOMETRY_DETAIL_PATHS is required')
  return paths.map((detailPath) => readBoundedJson(detailPath, 'route geometry detail'))
}

function combineDetails(details) {
  const first = details[0]
  if (details.some((detail) => detail.schemaVersion !== 'wechat-route-geometry-detail-v1')) throw new Error('unsupported route geometry detail schema')
  if (first.contractSha256 !== contractSha256 || details.some((detail) => detail.contractSha256 !== contractSha256)) throw new Error('route geometry detail contract SHA-256 is stale or mismatched')
  if (!/^[a-f\d]{12}$/u.test(first.commit ?? '') || details.some((detail) => detail.commit !== first.commit)) throw new Error('route geometry detail commits must match')
  const viewportKey = JSON.stringify(first.viewport)
  const viewportValues = [first.viewport?.width, first.viewport?.height, first.viewport?.dpr, first.viewport?.safeAreaBottom, first.viewport?.safeBottomInset]
  if (!viewportValues.every((value) => Number.isFinite(value) && value >= 0) || first.viewport.width <= 0 || first.viewport.height <= 0 || first.viewport.dpr <= 0 || details.some((detail) => JSON.stringify(detail.viewport) !== viewportKey)) throw new Error('route geometry detail viewports must match')

  const routes = details.flatMap((detail) => detail.routes ?? [])
  const routeNames = routes.map((route) => route.route)
  if (new Set(routeNames).size !== routeNames.length) throw new Error('route geometry detail routes must not repeat')
  const expectedRoutes = contract.routes.map((route) => route.route)
  if (expectedRoutes.some((route) => !routeNames.includes(route)) || routeNames.some((route) => !expectedRoutes.includes(route))) throw new Error('route geometry details must cover the exact 14-route contract')

  const contractByRoute = new Map(contract.routes.map((route) => [route.route, route]))
  for (const route of routes) {
    const summary = route.summary
    if (!summary || summary.route !== route.route) throw new Error(`route geometry summary missing: ${route.route}`)
    if (summary.status === 'pass' && summary.violationCount === 0 && summary.regionCount >= 1) continue
    const allowed = contractByRoute.get(route.route)?.unavailableRouteStates ?? []
    if (summary.status !== 'unavailable' || !allowed.includes(summary.routeState)) throw new Error(`route geometry result is not promotable: ${route.route}`)
  }

  const byRoute = new Map(routes.map((route) => [route.route, route]))
  return {
    schemaVersion: 'wechat-route-geometry-evidence-v1',
    contractSha256,
    commit: first.commit,
    viewport: first.viewport,
    routes: expectedRoutes.map((route) => byRoute.get(route)),
  }
}

function main() {
  const evidence = combineDetails(readDetails(process.env.GEOMETRY_DETAIL_PATHS))
  const serialized = `${JSON.stringify(evidence, null, 2)}\n`
  const sha256 = crypto.createHash('sha256').update(serialized).digest('hex')
  const viewport = evidence.viewport
  const viewportName = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', evidence.commit, viewportName, 'geometry', `${sha256}.json`)
  const destination = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  if (fs.existsSync(destination)) {
    const existingSha = crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex')
    if (existingSha !== sha256) throw new Error(`immutable route geometry evidence collision: ${relativePath}`)
  } else {
    fs.writeFileSync(destination, serialized, { flag: 'wx' })
  }
  console.log(JSON.stringify({
    status: 'pass',
    commit: evidence.commit,
    viewport: viewportName,
    safeAreaBottom: viewport.safeAreaBottom,
    safeBottomInset: viewport.safeBottomInset,
    routeCount: evidence.routes.length,
    passed: evidence.routes.filter((route) => route.summary.status === 'pass').length,
    unavailable: evidence.routes.filter((route) => route.summary.status === 'unavailable').length,
    sha256,
    evidencePath: relativePath.split(path.sep).join('/'),
  }))
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { combineDetails, readDetails }
