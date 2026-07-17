#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')
const contract = require('../docs/design/current-ui/selected-control-contract.json')

const operationTimeoutMs = 10000
const selectedRoutes = new Set((process.env.SELECTED_STATE_ROUTES ?? '').split(',').map((value) => value.trim()).filter(Boolean))

function selectedGroups() {
  if (selectedRoutes.size === 0) return contract.groups
  const known = new Set(contract.groups.map((group) => group.route))
  const unknown = [...selectedRoutes].filter((route) => !known.has(route))
  if (unknown.length > 0) throw new Error(`unknown SELECTED_STATE_ROUTES: ${unknown.join(', ')}`)
  return contract.groups.filter((group) => selectedRoutes.has(group.route))
}

async function settle(milliseconds = 650) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function open(miniProgram, route) {
  const page = await timeout(miniProgram.reLaunch(route.path), operationTimeoutMs, `open ${route.route}`)
  await settle()
  return page
}

async function routeState(page, states) {
  for (const state of states ?? []) {
    if (await timeout(page.$(`.wx-data-route-state-${state}`), 1500, `query route state ${state}`)) return state
  }
  return null
}

async function inspectGroup(page, group) {
  const selector = `.wx-data-role-${group.role}`
  const controls = await timeout(page.$$(selector), 3000, `query ${group.role}`)
  const state = await routeState(page, group.unavailableRouteStates)
  if (controls.length < group.minimumControls && state) {
    return { route: group.route, role: group.role, status: 'unavailable', routeState: state, controls: controls.length, active: 0 }
  }
  const activeSelector = `${selector}.wx-data-${group.state}-true`
  const inactiveSelector = `${selector}.wx-data-${group.state}-false`
  const materialActiveSelector = `${selector}.wx-data-selection-material-active`
  const materialInactiveSelector = `${selector}.wx-data-selection-material-inactive`
  const [active, inactive, materialActive, materialInactive, activeWithInactiveMaterial, inactiveWithActiveMaterial] = await Promise.all([
    timeout(page.$$(activeSelector), 3000, `query active ${group.role}`),
    timeout(page.$$(inactiveSelector), 3000, `query inactive ${group.role}`),
    timeout(page.$$(materialActiveSelector), 3000, `query active material ${group.role}`),
    timeout(page.$$(materialInactiveSelector), 3000, `query inactive material ${group.role}`),
    timeout(page.$$(`${activeSelector}.wx-data-selection-material-inactive`), 3000, `query active with inactive material ${group.role}`),
    timeout(page.$$(`${inactiveSelector}.wx-data-selection-material-active`), 3000, `query inactive with active material ${group.role}`),
  ])
  const pass = controls.length >= group.minimumControls
    && active.length >= group.minimumActive
    && active.length <= group.maximumActive
    && materialActive.length === active.length
    && materialInactive.length === inactive.length
    && active.length + inactive.length === controls.length
    && activeWithInactiveMaterial.length === 0
    && inactiveWithActiveMaterial.length === 0
  return {
    route: group.route,
    role: group.role,
    status: pass ? 'pass' : 'fail',
    controls: controls.length,
    active: active.length,
    inactive: inactive.length,
    materialOwners: { active: materialActive.length, inactive: materialInactive.length },
    materialMismatches: activeWithInactiveMaterial.length + inactiveWithActiveMaterial.length,
    expected: { controlsAtLeast: group.minimumControls, activeAtLeast: group.minimumActive, activeAtMost: group.maximumActive },
  }
}

async function main() {
  const groups = selectedGroups()
  const routes = [...new Map(groups.map((group) => [group.route, { route: group.route, path: group.path }])).values()]
  const results = []
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    for (const route of routes) {
      const page = await open(miniProgram, route)
      for (const group of groups.filter((group) => group.route === route.route)) results.push(await inspectGroup(page, group))
    }
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
  const failed = results.filter((result) => result.status === 'fail')
  console.log(JSON.stringify({
    status: failed.length === 0 ? 'pass' : 'fail',
    checkedGroups: results.length,
    passed: results.filter((result) => result.status === 'pass').length,
    unavailable: results.filter((result) => result.status === 'unavailable').length,
    failed,
    results,
  }))
  if (failed.length > 0) process.exitCode = 1
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  })
}

module.exports = { selectedGroups }
