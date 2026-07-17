#!/usr/bin/env node
'use strict'

const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const contract = require('../docs/design/current-ui/selected-control-contract.json')

const root = path.resolve(__dirname, '..')

function key(item) {
  return `${item.route}::${item.role}`
}

function readDetails(value) {
  const paths = (value ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  if (paths.length === 0) throw new Error('SELECTED_STATE_DETAIL_PATHS is required')
  return paths.map((detailPath) => JSON.parse(fs.readFileSync(path.resolve(detailPath), 'utf8')))
}

function combineDetails(details) {
  const first = details[0]
  if (details.some((detail) => detail.schemaVersion !== 'wechat-selected-control-detail-v1')) throw new Error('unsupported selected control detail schema')
  if (!/^[a-f\d]{12}$/u.test(first.commit ?? '') || details.some((detail) => detail.commit !== first.commit)) throw new Error('selected control detail commits must match')
  const viewportKey = JSON.stringify(first.viewport)
  if (![first.viewport?.width, first.viewport?.height, first.viewport?.dpr].every((value) => Number.isFinite(value) && value > 0) || details.some((detail) => JSON.stringify(detail.viewport) !== viewportKey)) throw new Error('selected control detail viewports must match')
  if (details.some((detail) => detail.coverageMatches !== true || !Array.isArray(detail.failures) || detail.failures.length !== 0)) throw new Error('only complete passing selected control batches may be promoted')

  const results = details.flatMap((detail) => detail.results ?? [])
  const resultKeys = results.map(key)
  if (new Set(resultKeys).size !== resultKeys.length) throw new Error('selected control detail groups must not repeat')
  const expectedKeys = contract.groups.map(key)
  if (expectedKeys.some((item) => !resultKeys.includes(item)) || resultKeys.some((item) => !expectedKeys.includes(item))) throw new Error('selected control details must cover the exact selected-control contract')

  const contractByKey = new Map(contract.groups.map((group) => [key(group), group]))
  for (const result of results) {
    if (result.status === 'pass' && result.materialMismatches === 0 && result.active >= result.expected.activeAtLeast && result.active <= result.expected.activeAtMost) continue
    const definition = contractByKey.get(key(result))
    if (result.status !== 'unavailable' || !(definition?.unavailableRouteStates ?? []).includes(result.routeState)) throw new Error(`selected control result is not promotable: ${key(result)}`)
  }

  const byKey = new Map(results.map((result) => [key(result), result]))
  return {
    schemaVersion: 'wechat-selected-control-evidence-v1',
    commit: first.commit,
    viewport: first.viewport,
    groups: expectedKeys.map((item) => byKey.get(item)),
  }
}

function main() {
  const evidence = combineDetails(readDetails(process.env.SELECTED_STATE_DETAIL_PATHS))
  const serialized = `${JSON.stringify(evidence, null, 2)}\n`
  const sha256 = crypto.createHash('sha256').update(serialized).digest('hex')
  const viewport = evidence.viewport
  const viewportName = `${viewport.width}x${viewport.height}@${viewport.dpr}`
  const relativePath = path.join('artifacts', 'ui-runtime-reviews', evidence.commit, viewportName, 'selected-controls', `${sha256}.json`)
  const destination = path.join(root, relativePath)
  fs.mkdirSync(path.dirname(destination), { recursive: true })
  if (fs.existsSync(destination)) {
    const existingSha = crypto.createHash('sha256').update(fs.readFileSync(destination)).digest('hex')
    if (existingSha !== sha256) throw new Error(`immutable selected control evidence collision: ${relativePath}`)
  } else {
    fs.writeFileSync(destination, serialized, { flag: 'wx' })
  }
  console.log(JSON.stringify({
    status: 'pass', commit: evidence.commit, viewport: viewportName, groupCount: evidence.groups.length,
    passed: evidence.groups.filter((group) => group.status === 'pass').length,
    unavailable: evidence.groups.filter((group) => group.status === 'unavailable').length,
    sha256, evidencePath: relativePath.split(path.sep).join('/'),
  }))
}

if (require.main === module) {
  try { main() } catch (error) { console.error(error instanceof Error ? error.message : String(error)); process.exit(1) }
}

module.exports = { combineDetails, readDetails }
