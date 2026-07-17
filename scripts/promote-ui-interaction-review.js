#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const contract = require('../docs/design/current-ui/core-interaction-contract.json')
const { readBoundedJson } = require('./bounded-json-detail')

const root = path.resolve(__dirname, '..')

function readDetails(value) {
  const paths = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (paths.length === 0) throw new Error('INTERACTION_DETAIL_PATHS is required')
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
  const serialized = `${JSON.stringify(evidence, null, 2)}\n`
  const sha256 = crypto.createHash('sha256').update(serialized).digest('hex')
  const viewport = evidence.viewport
  const viewportName = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', evidence.commit, viewportName, 'interactions', `${sha256}.json`)
  const destination = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  if (fs.existsSync(destination)) {
    const existingSha = crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex')
    if (existingSha !== sha256) throw new Error(`immutable interaction evidence collision: ${relativePath}`)
  } else {
    fs.writeFileSync(destination, serialized, { flag: 'wx' })
  }
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
