#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')
const crypto = require('node:crypto')
const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { requireOnlineRouteBatch } = require('./online-route-batch')
const { writeBoundedJsonAtomic } = require('./bounded-json-detail')
const contract = require('../docs/design/current-ui/selected-control-contract.json')

const operationTimeoutMs = 10000
const maximumControlsPerGroup = 32
const contractPath = path.resolve(__dirname, '../docs/design/current-ui/selected-control-contract.json')
const contractSha256 = crypto.createHash('sha256').update(fs.readFileSync(contractPath)).digest('hex')
function selectedGroups() {
  const selectedRoutes = requireOnlineRouteBatch(process.env.SELECTED_STATE_ROUTES, 'SELECTED_STATE_ROUTES', contract.groups.map((group) => group.route))
  return contract.groups.filter((group) => selectedRoutes.has(group.route))
}

function expectedBoundarySequence(controlStates) {
  return controlStates.map((value, index) => value === 'true' ? 'active' : controlStates[index - 1] === 'true' ? 'suppressed' : 'inactive')
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
  const queriedControls = await timeout(page.$$(selector), 3000, `query ${group.role}`)
  const controls = queriedControls.slice(0, maximumControlsPerGroup)
  const state = await routeState(page, group.unavailableRouteStates)
  if (controls.length < group.minimumControls && state) {
    return { route: group.route, role: group.role, status: 'unavailable', routeState: state, controls: controls.length, active: 0 }
  }
  const activeSelector = `${selector}.wx-data-${group.state}-true`
  const inactiveSelector = `${selector}.wx-data-${group.state}-false`
  const materialActiveSelector = `${selector}.wx-data-selection-material-active`
  const materialInactiveSelector = `${selector}.wx-data-selection-material-inactive`
  const [active, inactive, materialActive, materialInactive, activeWithInactiveMaterial, inactiveWithActiveMaterial, nestedMaterialRenders] = await Promise.all([
    timeout(page.$$(activeSelector), 3000, `query active ${group.role}`),
    timeout(page.$$(inactiveSelector), 3000, `query inactive ${group.role}`),
    timeout(page.$$(materialActiveSelector), 3000, `query active material ${group.role}`),
    timeout(page.$$(materialInactiveSelector), 3000, `query inactive material ${group.role}`),
    timeout(page.$$(`${activeSelector}.wx-data-selection-material-inactive`), 3000, `query active with inactive material ${group.role}`),
    timeout(page.$$(`${inactiveSelector}.wx-data-selection-material-active`), 3000, `query inactive with active material ${group.role}`),
    timeout(page.$$(`${selector} [class*="wx-data-material-render-"]`), 3000, `query nested material renders ${group.role}`),
  ])
  const materialStyleProperties = [
    'background-color', 'background-image', 'box-shadow',
    'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
  ]
  const materialSignature = async (element, label) => {
    if (!element) return null
    const values = await Promise.all(materialStyleProperties.map((property) => timeout(element.style(property), 1500, `read ${label} ${property}`)))
    return Object.fromEntries(materialStyleProperties.map((property, index) => [property, String(values[index] ?? '')]))
  }
  const [activeMaterialStyle, inactiveMaterialStyle] = await Promise.all([
    materialSignature(active[0], `active material ${group.role}`),
    materialSignature(inactive[0], `inactive material ${group.role}`),
  ])
  const visualMaterialDistinct = controls.length < 2
    || Boolean(activeMaterialStyle && inactiveMaterialStyle && JSON.stringify(activeMaterialStyle) !== JSON.stringify(inactiveMaterialStyle))
  const [controlStates, controlMaterialOwners] = await Promise.all([
    Promise.all(controls.map((element) => timeout(element.attribute(`data-${group.state}`), 1500, `read ${group.role} state`))),
    Promise.all(controls.map((element) => timeout(element.attribute('data-material-owner'), 1500, `read ${group.role} material owner`))),
  ])
  const materialOwnerMismatches = controlMaterialOwners.filter((owner) => owner !== contract.materialOwnership.controlMaterialOwner).length
  const leadingBoundaries = group.boundaryMode === 'contiguous'
    ? await Promise.all(controls.map((element) => timeout(element.attribute(contract.materialOwnership.boundaryAttribute), 1500, `read ${group.role} leading boundary`)))
    : []
  const expectedLeadingBoundaries = group.boundaryMode === 'contiguous'
    ? expectedBoundarySequence(controlStates)
    : []
  const boundaryMismatches = leadingBoundaries.filter((value, index) => value !== expectedLeadingBoundaries[index]).length
  const pass = queriedControls.length <= maximumControlsPerGroup
    && controls.length >= group.minimumControls
    && active.length >= group.minimumActive
    && active.length <= group.maximumActive
    && materialActive.length === active.length
    && materialInactive.length === inactive.length
    && active.length + inactive.length === controls.length
    && activeWithInactiveMaterial.length === 0
    && inactiveWithActiveMaterial.length === 0
    && visualMaterialDistinct
    && materialOwnerMismatches === 0
    && nestedMaterialRenders.length === 0
    && boundaryMismatches === 0
  return {
    route: group.route,
    role: group.role,
    status: pass ? 'pass' : 'fail',
    controls: queriedControls.length,
    inspectedControls: controls.length,
    queryCapExceeded: queriedControls.length > maximumControlsPerGroup,
    active: active.length,
    inactive: inactive.length,
    materialOwners: { active: materialActive.length, inactive: materialInactive.length },
    materialMismatches: activeWithInactiveMaterial.length + inactiveWithActiveMaterial.length,
    controlMaterialOwners,
    materialOwnerMismatches,
    nestedMaterialRenderCount: nestedMaterialRenders.length,
    visualMaterialDistinct,
    boundaryMode: group.boundaryMode,
    leadingBoundaries,
    expectedLeadingBoundaries,
    boundaryMismatches,
    materialStyles: { active: activeMaterialStyle, inactive: inactiveMaterialStyle },
    expected: { controlsAtLeast: group.minimumControls, activeAtLeast: group.minimumActive, activeAtMost: group.maximumActive },
  }
}

async function main() {
  const groups = selectedGroups()
  const routes = [...new Map(groups.map((group) => [group.route, { route: group.route, path: group.path }])).values()]
  const results = []
  let miniProgram
  let system
  try {
    miniProgram = await connectMiniProgram()
    system = await timeout(miniProgram.systemInfo(), 4000, 'read system info')
    for (const route of routes) {
      const page = await open(miniProgram, route)
      for (const group of groups.filter((group) => group.route === route.route)) results.push(await inspectGroup(page, group))
    }
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
  const failed = results.filter((result) => result.status === 'fail')
  const expectedKeys = groups.map((group) => `${group.route}::${group.role}`)
  const resultKeys = results.map((result) => `${result.route}::${result.role}`)
  const detail = {
    schemaVersion: 'wechat-selected-control-detail-v3',
    contractSha256,
    commit: execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' }).trim(),
    viewport: { width: system.windowWidth, height: system.windowHeight, dpr: system.pixelRatio },
    scope: 'selected_routes',
    coverageMatches: expectedKeys.length === resultKeys.length && expectedKeys.every((key) => resultKeys.includes(key)),
    results,
    failures: failed,
  }
  if (process.env.SELECTED_STATE_DETAIL_PATH) {
    const detailPath = path.resolve(process.env.SELECTED_STATE_DETAIL_PATH)
    writeBoundedJsonAtomic(detailPath, detail, 'selected-state detail')
  }
  console.log(JSON.stringify({
    status: failed.length === 0 ? 'pass' : 'fail',
    checkedGroups: results.length,
    passed: results.filter((result) => result.status === 'pass').length,
    unavailable: results.filter((result) => result.status === 'unavailable').length,
    failureCount: failed.length,
    failedGroups: failed.slice(0, 10).map((result) => `${result.route}::${result.role}`),
    detailPath: process.env.SELECTED_STATE_DETAIL_PATH ? path.resolve(process.env.SELECTED_STATE_DETAIL_PATH) : null,
  }))
  if (failed.length > 0) process.exitCode = 1
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  })
}

module.exports = { expectedBoundarySequence, selectedGroups }
