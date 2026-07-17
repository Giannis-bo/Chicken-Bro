#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')
const crypto = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { requireOnlineRouteBatch } = require('./online-route-batch')
const { writeBoundedJsonAtomic } = require('./bounded-json-detail')
const contract = require('../docs/design/current-ui/route-geometry-contract.json')

const operationTimeoutMs = 10000
const contractPath = path.resolve(__dirname, '../docs/design/current-ui/route-geometry-contract.json')
const contractSha256 = crypto.createHash('sha256').update(fs.readFileSync(contractPath)).digest('hex')
const requestedRoutes = requireOnlineRouteBatch(process.env.GEOMETRY_ROUTES, 'GEOMETRY_ROUTES', contract.routes.map((route) => route.route))

function selectedRoutes() {
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
  const allowedHorizontalButtonRoles = route.allowedHorizontalOverflowButtonRoles ?? []
  const allowedVerticalButtonRoles = route.allowedVerticalOverflowButtonRoles ?? []
  const initialSafeAreaButtonRoles = route.initialSafeAreaButtonRoles ?? []
  const initialSafeAreaRegionIds = route.initialSafeAreaRegionIds ?? []
  const requiredFixedDockControlRoles = route.requiredFixedDockControlRoles ?? []
  const [shell, shellBody, tabBar, regions, nativeButtons, roleButtons, controlCells, nativeDockButtons, roleDockButtons, state] = await Promise.all([
    timeout(page.$('.wx-style-shell'), 4000, 'query route shell'),
    timeout(page.$('.wx-style-shellbody'), 4000, 'query route shell body'),
    timeout(page.$('.wx-style-product-tab-bar'), 4000, 'query product tab bar'),
    timeout(page.$$('.wx-style-routeregion'), 4000, 'query route regions'),
    timeout(page.$$('button'), 4000, 'query native buttons'),
    timeout(page.$$('[role="button"]'), 4000, 'query role buttons'),
    timeout(page.$$('.wx-data-control-cell'), 4000, 'query control layout cells'),
    timeout(page.$$('.wx-style-shelldock button'), 4000, 'query native fixed dock buttons'),
    timeout(page.$$('.wx-style-shelldock [role="button"]'), 4000, 'query role fixed dock buttons'),
    unavailableState(page, route.unavailableRouteStates),
  ])
  const buttons = [...nativeButtons, ...roleButtons]
  const dockButtons = [...nativeDockButtons, ...roleDockButtons]
  if (regions.length === 0 && state) {
    const summary = { route: route.route, status: 'unavailable', routeState: state, regionCount: 0, semanticRegionCount: 0, buttonCount: buttons.length }
    return {
      summary,
      detail: { route: route.route, path: route.path, viewport, summary, routeState: state, regions: [], buttons: [], fixedDockButtons: [] },
    }
  }

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
  const inspectButton = async (element) => {
    const [geometry, className, role, actionId] = await Promise.all([
      bounds(element),
      timeout(element.attribute('class'), 1500, 'read button class'),
      timeout(element.attribute('data-role'), 1500, 'read button role'),
      timeout(element.attribute('data-action-id'), 1500, 'read button action id'),
    ])
    const normalizedClassName = String(className ?? '')
    return {
      ...geometry,
      className: normalizedClassName,
      role: String(role ?? '') || normalizedClassName.match(/(?:^|\s)wx-data-role-([^\s]+)/u)?.[1] || '',
      actionId: String(actionId ?? '') || normalizedClassName.match(/(?:^|\s)wx-data-action-id-([^\s]+)/u)?.[1] || '',
    }
  }
  const [buttonBounds, dockButtonBounds, tabBarBounds, shellBodyMetrics] = await Promise.all([
    Promise.all(buttons.map(inspectButton)),
    Promise.all(dockButtons.map(inspectButton)),
    tabBar ? bounds(tabBar) : null,
    shellBody ? Promise.all([
      bounds(shellBody),
      timeout(shellBody.domProperty('clientHeight'), 2000, 'read shell body client height'),
      timeout(shellBody.domProperty('scrollHeight'), 2000, 'read shell body scroll height'),
      timeout(shellBody.style('padding-bottom'), 2000, 'read shell body bottom padding'),
    ]).then(([geometry, clientHeight, scrollHeight, paddingBottom]) => ({
      ...geometry,
      clientHeight: Number(clientHeight),
      scrollHeight: Number(scrollHeight),
      paddingBottom: Number.parseFloat(String(paddingBottom)) || 0,
    })) : null,
  ])
  const uniqueBounds = (items) => [...new Map(items.map((item) => [
    [item.left, item.top, item.width, item.height, item.role, item.actionId].join(':'),
    item,
  ])).values()]
  const uniqueButtonBounds = uniqueBounds(buttonBounds)
  const uniqueDockButtonBounds = uniqueBounds(dockButtonBounds)
  const controlCellBounds = await Promise.all(controlCells.map(async (element) => {
    const [geometry, roles] = await Promise.all([
      bounds(element),
      timeout(element.attribute('data-control-roles'), 1500, 'read control cell roles'),
    ])
    return { ...geometry, roles: String(roles ?? '').split(',').map((role) => role.trim()).filter(Boolean) }
  }))
  const violations = []
  if (!shellBounds) violations.push({ type: 'missing-shell' })
  else if (shellBounds.left < -tolerance || shellBounds.right > viewport.width + tolerance) violations.push({ type: 'shell-horizontal', left: shellBounds.left, right: shellBounds.right })
  const minimumRegions = route.minimumRegions ?? 1
  if (regionBounds.length < minimumRegions) violations.push({ type: 'missing-route-regions', minimum: minimumRegions, actual: regionBounds.length })
  const presentRegionIds = new Set(regionBounds.map((region) => region.id))
  const duplicateRegionIds = [...presentRegionIds].filter((id) => regionBounds.filter((region) => region.id === id).length > 1)
  for (const id of duplicateRegionIds) violations.push({ type: 'duplicate-semantic-region', id, count: regionBounds.filter((region) => region.id === id).length })
  for (const requiredRegionId of route.requiredRegionIds ?? []) {
    if (!presentRegionIds.has(requiredRegionId)) violations.push({ type: 'missing-semantic-region', id: requiredRegionId })
  }
  for (const region of regionBounds) {
    if (/^region-\d+$/u.test(region.id)) violations.push({ type: 'anonymous-region-id', id: region.id })
    if (region.left < -tolerance || region.right > viewport.width + tolerance) violations.push({ type: 'region-horizontal', id: region.id, left: region.left, right: region.right })
    if (region.visibleSlot && !allowedVertical.has(region.id) && (region.top < -tolerance || region.bottom > viewport.height + tolerance)) violations.push({ type: 'region-vertical', id: region.id, top: region.top, bottom: region.bottom })
  }
  uniqueButtonBounds.forEach((button, index) => {
    const hasRole = (role) => button.role === role || button.className.includes(`wx-data-role-${role}`)
    if (!button.role && !button.actionId) violations.push({ type: 'anonymous-native-button', index })
    const allowedHorizontalScrollContent = allowedHorizontalButtonRoles.some(hasRole)
    const allowedVerticalScrollContent = allowedVerticalButtonRoles.some(hasRole)
    if (button.width > viewport.width + tolerance) {
      violations.push({ type: 'native-button-width', index, role: button.role || null, width: button.width, viewportWidth: viewport.width })
    } else if (!allowedHorizontalScrollContent && (button.left < -tolerance || button.right > viewport.width + tolerance)) {
      violations.push({ type: 'native-button-horizontal', index, left: button.left, right: button.right, width: button.width })
    }
    if (!allowedVerticalScrollContent && (button.top < -tolerance || button.bottom > viewport.height + tolerance || button.height > viewport.height + tolerance)) {
      violations.push({ type: 'native-button-vertical', index, role: button.role || null, actionId: button.actionId || null, top: button.top, bottom: button.bottom, height: button.height })
    }
  })
  for (const cell of controlCellBounds) {
    if (cell.roles.length === 0) violations.push({ type: 'anonymous-control-cell' })
    for (const role of cell.roles) {
      const candidates = uniqueButtonBounds.filter((candidate) => candidate.role === role)
      const contained = candidates.some((button) => button.left >= cell.left - tolerance && button.right <= cell.right + tolerance && button.top >= cell.top - tolerance && button.bottom <= cell.bottom + tolerance)
      if (candidates.length === 0) {
        violations.push({ type: 'missing-control-cell-button', role })
      } else if (!contained) {
        violations.push({ type: 'native-button-cell-overflow', role, buttons: candidates, cell: { left: cell.left, top: cell.top, right: cell.right, bottom: cell.bottom } })
      }
    }
  }
  const safeAreaBottom = viewport.safeAreaBottom
  const safeBottomInset = viewport.safeBottomInset
  for (const regionId of initialSafeAreaRegionIds) {
    const region = regionBounds.find((candidate) => candidate.id === regionId && candidate.visibleSlot)
    if (!region) {
      violations.push({ type: 'missing-initial-safe-area-region', id: regionId })
    } else if (region.bottom > safeAreaBottom + tolerance) {
      violations.push({ type: 'initial-region-safe-area', id: regionId, bottom: region.bottom, safeAreaBottom })
    }
  }
  const bodyCanRevealSafeAreaContent = Boolean(
    shellBodyMetrics
    && shellBodyMetrics.scrollHeight > shellBodyMetrics.clientHeight + tolerance
    && shellBodyMetrics.paddingBottom + tolerance >= safeBottomInset,
  )
  if (tabBarBounds && shellBodyMetrics && shellBodyMetrics.bottom > tabBarBounds.top + tolerance) {
    violations.push({ type: 'tab-root-scroll-viewport-overlap', shellBodyBottom: shellBodyMetrics.bottom, tabBarTop: tabBarBounds.top })
  }
  uniqueDockButtonBounds.forEach((button, index) => {
    if (contract.safeAreaPolicy?.fixedDockControlsMustEndAtSafeBottom && button.bottom > safeAreaBottom + tolerance) {
      violations.push({ type: 'fixed-dock-button-safe-area', index, role: button.role || null, actionId: button.actionId || null, bottom: button.bottom, safeAreaBottom })
    }
  })
  uniqueButtonBounds.forEach((button, index) => {
    const belongsToDock = uniqueDockButtonBounds.some((dockButton) => Math.abs(dockButton.left - button.left) <= tolerance && Math.abs(dockButton.top - button.top) <= tolerance && Math.abs(dockButton.width - button.width) <= tolerance)
    const entersVisibleSafeArea = button.top < viewport.height && button.bottom > safeAreaBottom + tolerance
    if (!belongsToDock && entersVisibleSafeArea && contract.safeAreaPolicy?.scrollContentMayCrossSafeBottomOnlyWithScrollableOverflowAndSafePadding && !bodyCanRevealSafeAreaContent) {
      violations.push({ type: 'scroll-button-safe-area-without-reveal-space', index, role: button.role || null, actionId: button.actionId || null, top: button.top, bottom: button.bottom, safeAreaBottom })
    }
  })
  for (const role of initialSafeAreaButtonRoles) {
    const matches = uniqueButtonBounds.filter((button) => button.role === role)
    if (matches.length === 0) {
      violations.push({ type: 'missing-initial-safe-area-button', role })
    } else {
      matches.forEach((button) => {
        if (button.bottom > safeAreaBottom + tolerance) violations.push({ type: 'initial-button-safe-area', role, bottom: button.bottom, safeAreaBottom })
      })
    }
  }
  for (const role of requiredFixedDockControlRoles) {
    if (!uniqueDockButtonBounds.some((button) => button.role === role)) {
      violations.push({ type: 'missing-fixed-dock-control', role })
    }
  }
  const summary = {
    route: route.route,
    status: violations.length === 0 ? 'pass' : 'fail',
    regionCount: regionBounds.length,
    semanticRegionCount: regionBounds.filter((item) => !/^region-\d+$/u.test(item.id)).length,
    duplicateRegionCount: duplicateRegionIds.length,
    requiredRegionCount: (route.requiredRegionIds ?? []).length,
    missingRequiredRegionCount: (route.requiredRegionIds ?? []).filter((id) => !presentRegionIds.has(id)).length,
    buttonCount: uniqueButtonBounds.length,
    controlCellCount: controlCellBounds.length,
    anonymousButtonCount: uniqueButtonBounds.filter((button) => !button.role && !button.actionId).length,
    maxRegionRight: Math.max(0, ...regionBounds.map((item) => item.right)),
    shellRight: shellBounds?.right ?? null,
    maxBoundRegionBottom: Math.max(0, ...regionBounds.filter((item) => item.visibleSlot && !allowedVertical.has(item.id)).map((item) => item.bottom)),
    maxInitialSafeAreaRegionBottom: Math.max(0, ...regionBounds.filter((item) => initialSafeAreaRegionIds.includes(item.id) && item.visibleSlot).map((item) => item.bottom)),
    missingInitialSafeAreaButtonCount: initialSafeAreaButtonRoles.filter((role) => !uniqueButtonBounds.some((button) => button.role === role)).length,
    missingFixedDockControlCount: requiredFixedDockControlRoles.filter((role) => !uniqueDockButtonBounds.some((button) => button.role === role)).length,
    maxBoundButtonBottom: Math.max(0, ...uniqueButtonBounds.filter((item) => !allowedVerticalButtonRoles.some((role) => item.role === role || item.className.includes(`wx-data-role-${role}`))).map((item) => item.bottom)),
    safeAreaBottom,
    safeBottomInset,
    fixedDockButtonCount: uniqueDockButtonBounds.length,
    maxFixedDockButtonBottom: Math.max(0, ...uniqueDockButtonBounds.map((item) => item.bottom)),
    shellBodyScrollable: Boolean(shellBodyMetrics && shellBodyMetrics.scrollHeight > shellBodyMetrics.clientHeight + tolerance),
    shellBodyPaddingBottom: shellBodyMetrics?.paddingBottom ?? null,
    shellBodyBottom: shellBodyMetrics?.bottom ?? null,
    tabBarTop: tabBarBounds?.top ?? null,
    violationCount: violations.length,
    violations: violations.slice(0, 10),
  }
  return { summary, detail: { route: route.route, path: route.path, viewport, summary, shellBody: shellBodyMetrics, tabBar: tabBarBounds, regions: regionBounds, buttons: uniqueButtonBounds.map(({ className: _className, ...button }) => button), fixedDockButtons: uniqueDockButtonBounds.map(({ className: _className, ...button }) => button) } }
}

async function main() {
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const system = await timeout(miniProgram.systemInfo(), 4000, 'read system info')
    const safeAreaBottom = Number(system.safeArea?.bottom ?? system.windowHeight)
    const viewport = {
      width: system.windowWidth,
      height: system.windowHeight,
      dpr: system.pixelRatio,
      safeAreaBottom,
      safeBottomInset: Math.max(0, Number(system.screenHeight ?? system.windowHeight) - safeAreaBottom),
    }
    const results = []
    const details = []
    for (const route of selectedRoutes()) {
      const inspected = await inspect(await open(miniProgram, route), route, viewport)
      results.push(inspected.summary)
      details.push(inspected.detail)
    }
    let detailPath = null
    if (process.env.GEOMETRY_DETAIL_PATH) {
      detailPath = path.resolve(process.env.GEOMETRY_DETAIL_PATH)
      const commit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' }).trim()
      writeBoundedJsonAtomic(detailPath, { schemaVersion: 'wechat-route-geometry-detail-v1', contractSha256, commit, viewport, routes: details }, 'route geometry detail')
    }
    const failures = results.filter((result) => result.status === 'fail')
    console.log(JSON.stringify({
      status: failures.length === 0 ? 'pass' : 'fail',
      viewport,
      checkedRoutes: results.length,
      passed: results.filter((result) => result.status === 'pass').length,
      unavailable: results.filter((result) => result.status === 'unavailable').length,
      failureCount: failures.length,
      failedRoutes: failures.slice(0, 10).map((result) => result.route),
      detailPath,
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
