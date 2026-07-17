#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')
const contract = require('../docs/design/current-ui/route-geometry-contract.json')

const operationTimeoutMs = 10000
const requestedRoutes = new Set((process.env.GEOMETRY_ROUTES ?? '').split(',').map((value) => value.trim()).filter(Boolean))

function selectedRoutes() {
  if (requestedRoutes.size === 0) return contract.routes
  const known = new Set(contract.routes.map((route) => route.route))
  const unknown = [...requestedRoutes].filter((route) => !known.has(route))
  if (unknown.length > 0) throw new Error(`unknown GEOMETRY_ROUTES: ${unknown.join(', ')}`)
  return contract.routes.filter((route) => requestedRoutes.has(route.route))
}

async function settle(milliseconds = 650) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function open(miniProgram, route) {
  try {
    const page = await timeout(miniProgram.reLaunch(route.path), operationTimeoutMs, `open ${route.route}`)
    await settle()
    return page
  } catch (error) {
    const expectedPath = route.path.split('?')[0].replace(/^\//u, '')
    const current = await timeout(miniProgram.currentPage(), 2500, `recover ${route.route}`)
    if (current.path !== expectedPath) throw error
    await settle(200)
    return current
  }
}

async function bounds(element) {
  const [offset, size] = await Promise.all([
    timeout(element.offset(), 2500, 'element offset'),
    timeout(element.size(), 2500, 'element size'),
  ])
  return { left: offset.left, top: offset.top, right: offset.left + size.width, bottom: offset.top + size.height, width: size.width, height: size.height }
}

async function unavailableState(page, states) {
  for (const state of states ?? []) {
    if (await timeout(page.$(`.wx-data-route-state-${state}`), 1000, `query route state ${state}`)) return state
  }
  return null
}

async function inspect(page, route, viewport) {
  const tolerance = contract.tolerancePx
  const allowedVertical = new Set(route.allowedVerticalOverflowRegions ?? [])
  const allowedButtonRoles = route.allowedHorizontalOverflowButtonRoles ?? []
  const [shell, regions, buttons, state] = await Promise.all([
    timeout(page.$('.wx-style-shell'), 4000, 'query route shell'),
    timeout(page.$$('.wx-style-routeregion'), 4000, 'query route regions'),
    timeout(page.$$('button'), 4000, 'query native buttons'),
    unavailableState(page, route.unavailableRouteStates),
  ])
  if (regions.length === 0 && state) return { route: route.route, status: 'unavailable', routeState: state, regionCount: 0, buttonCount: buttons.length }

  const shellBounds = shell ? await bounds(shell) : null
  const regionBounds = await Promise.all(regions.map(async (element, index) => {
    const [regionId, visibleSlot, className, geometry] = await Promise.all([
      timeout(element.attribute('data-region'), 1500, 'read region id'),
      timeout(element.attribute('data-visible-slot'), 1500, 'read visible slot'),
      timeout(element.attribute('class'), 1500, 'read region class'),
      bounds(element),
    ])
    return {
      id: regionId || String(className ?? '').match(/(?:^|\s)wx-data-region-([^\s]+)/u)?.[1] || `region-${index + 1}`,
      visibleSlot: visibleSlot !== 'false' && !String(className ?? '').includes('wx-data-visible-slot-false'),
      ...geometry,
    }
  }))
  const buttonBounds = await Promise.all(buttons.map(async (element) => ({
    ...await bounds(element),
    className: String(await timeout(element.attribute('class'), 1500, 'read button class') ?? ''),
  })))
  const violations = []
  if (!shellBounds) violations.push({ type: 'missing-shell' })
  else if (shellBounds.left < -tolerance || shellBounds.right > viewport.width + tolerance) violations.push({ type: 'shell-horizontal', left: shellBounds.left, right: shellBounds.right })
  for (const region of regionBounds) {
    if (/^region-\d+$/u.test(region.id)) violations.push({ type: 'anonymous-region-id', id: region.id })
    if (region.left < -tolerance || region.right > viewport.width + tolerance) violations.push({ type: 'region-horizontal', id: region.id, left: region.left, right: region.right })
    if (region.visibleSlot && !allowedVertical.has(region.id) && (region.top < -tolerance || region.bottom > viewport.height + tolerance)) violations.push({ type: 'region-vertical', id: region.id, top: region.top, bottom: region.bottom })
  }
  buttonBounds.forEach((button, index) => {
    const allowedScrollContent = allowedButtonRoles.some((role) => button.className.includes(`wx-data-role-${role}`))
    if (!allowedScrollContent && (button.left < -tolerance || button.right > viewport.width + tolerance || button.width > viewport.width + tolerance)) {
      violations.push({ type: 'native-button-horizontal', index, left: button.left, right: button.right, width: button.width })
    }
  })
  return {
    route: route.route,
    status: violations.length === 0 ? 'pass' : 'fail',
    regionCount: regionBounds.length,
    semanticRegionCount: regionBounds.filter((item) => !/^region-\d+$/u.test(item.id)).length,
    buttonCount: buttonBounds.length,
    maxRegionRight: Math.max(0, ...regionBounds.map((item) => item.right)),
    shellRight: shellBounds?.right ?? null,
    maxBoundRegionBottom: Math.max(0, ...regionBounds.filter((item) => item.visibleSlot && !allowedVertical.has(item.id)).map((item) => item.bottom)),
    violationCount: violations.length,
    violations: violations.slice(0, 10),
  }
}

async function main() {
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const system = await timeout(miniProgram.systemInfo(), 4000, 'read system info')
    const viewport = { width: system.windowWidth, height: system.windowHeight, dpr: system.pixelRatio }
    const results = []
    for (const route of selectedRoutes()) results.push(await inspect(await open(miniProgram, route), route, viewport))
    const failures = results.filter((result) => result.status === 'fail')
    console.log(JSON.stringify({
      status: failures.length === 0 ? 'pass' : 'fail',
      viewport,
      checkedRoutes: results.length,
      passed: results.filter((result) => result.status === 'pass').length,
      unavailable: results.filter((result) => result.status === 'unavailable').length,
      failures,
      results,
    }))
    if (failures.length > 0) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  })
}

module.exports = { selectedRoutes }
