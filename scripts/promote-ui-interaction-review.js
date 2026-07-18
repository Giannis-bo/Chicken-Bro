#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const path = require('node:path')
const contract = require('../docs/design/current-ui/core-interaction-contract.json')
const { writeBoundedFileImmutable } = require('./bounded-file')
const { boundedDetailPaths, maxStructuredDetailBytes, readBoundedJson, serializeBoundedJson } = require('./bounded-json-detail')

const root = path.resolve(__dirname, '..')

function readDetails(value) {
  const paths = boundedDetailPaths(value, 'INTERACTION_DETAIL_PATHS')
  return paths.map((detailPath) => readBoundedJson(detailPath, 'core interaction detail'))
}

function combineDetails(details) {
  const first = details[0]
  if (details.some((detail) => detail.schemaVersion !== 'wechat-core-interaction-detail-v1')) throw new Error('unsupported interaction detail schema')
  if (!/^[a-f\d]{12}$/u.test(first.commit ?? '') || details.some((detail) => detail.commit !== first.commit)) throw new Error('interaction detail commits must match')
  const viewportKey = JSON.stringify(first.viewport)
  if (![first.viewport?.width, first.viewport?.height, first.viewport?.dpr].every((value) => Number.isFinite(value) && value > 0) || details.some((detail) => JSON.stringify(detail.viewport) !== viewportKey)) throw new Error('interaction detail viewports must match')
  if (details.some((detail) => detail.coverageMatches !== true || !Array.isArray(detail.failures) || detail.failures.length !== 0)) throw new Error('only complete passing interaction batches may be promoted')

  const routes = details.flatMap((detail) => detail.results ?? [])
  const routeNames = routes.map((route) => route.route)
  if (new Set(routeNames).size !== routeNames.length) throw new Error('interaction detail routes must not repeat')
  const expectedRoutes = contract.interactions.map((interaction) => interaction.route)
  if (expectedRoutes.some((route) => !routeNames.includes(route)) || routeNames.some((route) => !expectedRoutes.includes(route))) throw new Error('interaction details must cover the exact 14-route contract')

  const contractByRoute = new Map(contract.interactions.map((interaction) => [interaction.route, interaction]))
  for (const result of routes) {
    if (result.status === 'PASS') continue
    const definition = contractByRoute.get(result.route)
    const allowed = definition?.unavailableRouteStates ?? []
    if (result.status !== 'UNAVAILABLE' || !allowed.includes(result.routeState) || !String(result.actual).startsWith('interaction precondition unavailable:')) {
      throw new Error(`interaction result is not promotable: ${result.route}`)
    }
  }

  const byRoute = new Map(routes.map((route) => [route.route, route]))
  return {
    schemaVersion: 'wechat-core-interaction-evidence-v1',
    commit: first.commit,
    viewport: first.viewport,
    routes: expectedRoutes.map((route) => byRoute.get(route)),
  }
}

function main() {
  const evidence = combineDetails(readDetails(process.env.INTERACTION_DETAIL_PATHS))
  const serialized = serializeBoundedJson(evidence, 'interaction evidence')
  const sha256 = crypto.createHash('sha256').update(serialized).digest('hex')
  const viewport = evidence.viewport
  const viewportName = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', evidence.commit, viewportName, 'interactions', `${sha256}.json`)
  const destination = path.join(root, relativePath)
  writeBoundedFileImmutable(destination, Buffer.from(serialized), maxStructuredDetailBytes, `interaction evidence ${relativePath}`)
  console.log(JSON.stringify({
    status: 'pass',
    commit: evidence.commit,
    viewport: viewportName,
    routeCount: evidence.routes.length,
    passed: evidence.routes.filter((route) => route.status === 'PASS').length,
    unavailable: evidence.routes.filter((route) => route.status === 'UNAVAILABLE').length,
    sha256,
    evidencePath: relativePath.split(path.sep).join('/'),
  }))
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { combineDetails, readDetails }
