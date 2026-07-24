#!/usr/bin/env node
'use strict'

const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram, timeout, waitForRenderedPage, waitForSystemInfo } = require('./wechat-automator')
const { gearApplyEvidenceMatches } = require('./gear-apply-evidence')
const { requireOnlineRouteBatch } = require('./online-route-batch')
const { writeBoundedJsonAtomic } = require('./bounded-json-detail')
const coreInteractionContract = require('../docs/design/current-ui/core-interaction-contract.json')

const operationTimeoutMs = 10000
// A case includes a bounded route open plus a bounded precondition/action. Keep
// a small outer margin so the semantic failure can win the timeout race.
const caseTimeoutMs = 25000
const maximumInteractionElements = 32
let requestedRoutes = new Set()

function contractDefinition(route, accept) {
  const interaction = coreInteractionContract.interactions.find((candidate) => candidate.route === route)
  if (!interaction) throw new Error(`missing core interaction contract for ${route}`)
  return {
    output: {
      route,
      interaction: interaction.name,
      expected: interaction.expected,
      unavailableRouteStates: interaction.unavailableRouteStates ?? [],
    },
    accept,
  }
}

function contractPath(route) {
  const interaction = coreInteractionContract.interactions.find((candidate) => candidate.route === route)
  if (!interaction) throw new Error(`missing core interaction contract for ${route}`)
  return interaction.path
}

function contractSelector(route) {
  const interaction = coreInteractionContract.interactions.find((candidate) => candidate.route === route)
  if (!interaction) throw new Error(`missing core interaction contract for ${route}`)
  if (!/^[a-z][a-z\d-]*$/u.test(interaction.selectorAttribute) || !/^[a-z\d-]+$/u.test(interaction.selectorValue)) {
    throw new Error(`invalid core interaction selector for ${route}`)
  }
  return `.wx-${interaction.selectorAttribute}-${interaction.selectorValue}`
}

async function settle(milliseconds = 650) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function requiredElement(page, selector) {
  const deadline = Date.now() + operationTimeoutMs
  while (Date.now() < deadline) {
    try {
      const element = await timeout(page.$(selector), 2000, `query ${selector}`)
      if (element) return element
    } catch {}
    await settle(200)
  }
  throw new Error(`required interaction element missing: ${selector}`)
}

async function requiredElements(page, selector, minimum) {
  const deadline = Date.now() + operationTimeoutMs
  while (Date.now() < deadline) {
    try {
      const elements = await timeout(page.$$(selector), 2000, `query ${selector}`)
      if (elements.length > maximumInteractionElements) throw new Error(`interaction query cap exceeded: ${selector} ${elements.length}/${maximumInteractionElements}`)
      if (elements.length >= minimum) return elements
    } catch (error) {
      if (error instanceof Error && error.message.startsWith('interaction query cap exceeded:')) throw error
    }
    await settle(200)
  }
  throw new Error(`required interaction elements missing: ${selector} expected>=${minimum}`)
}

async function requiredElementsOrUnavailable(page, selector, minimum, unavailableStates) {
  const deadline = Date.now() + operationTimeoutMs
  while (Date.now() < deadline) {
    try {
      const elements = await timeout(page.$$(selector), 2000, `query ${selector}`)
      if (elements.length > maximumInteractionElements) throw new Error(`interaction query cap exceeded: ${selector} ${elements.length}/${maximumInteractionElements}`)
      if (elements.length >= minimum) return elements
      for (const state of unavailableStates) {
        const marker = await timeout(page.$(`.wx-data-route-state-${state}`), 1000, `query route state ${state}`)
        if (marker) throw new Error(`interaction precondition unavailable: ${selector} count=${elements.length}; routeState=${state}`)
      }
    } catch (error) {
      if (error instanceof Error && (error.message.startsWith('interaction precondition unavailable:') || error.message.startsWith('interaction query cap exceeded:'))) throw error
    }
    await settle(200)
  }
  throw new Error(`required interaction elements missing: ${selector} expected>=${minimum}`)
}

async function waitForTextChange(page, selector, before) {
  const deadline = Date.now() + operationTimeoutMs
  let actual = before
  while (Date.now() < deadline) {
    actual = await timeout((await requiredElement(page, selector)).text(), 2000, `read ${selector} text`)
    if (actual !== before) return actual
    await settle(200)
  }
  throw new Error(`${selector} text did not change; actual=${actual}`)
}

async function currentPath(miniProgram) {
  return (await timeout(miniProgram.currentPage(), operationTimeoutMs, 'read current page')).path
}

async function open(miniProgram, path) {
  let page
  try {
    page = await timeout(miniProgram.reLaunch(path), operationTimeoutMs, `open ${path}`)
  } catch (error) {
    const expectedPath = path.split('?')[0].replace(/^\//u, '')
    const deadline = Date.now() + Math.floor(operationTimeoutMs / 2)
    while (Date.now() < deadline) {
      try {
        const current = await timeout(miniProgram.currentPage(), 2000, `recover open ${path}`)
        if (current.path === expectedPath) {
          page = current
          break
        }
      } catch {}
      await settle(200)
    }
    if (!page) {
      try {
        page = await timeout(miniProgram.navigateTo(path), 4000, `fallback navigate ${path}`)
      } catch {
        throw error
      }
    }
  }
  await waitForRenderedPage(page, `render ${path}`)
  await settle()
  return page
}

async function tapAndReadPath(miniProgram, page, selector, waitForChange = true) {
  const before = await currentPath(miniProgram)
  await timeout((await requiredElement(page, selector)).tap(), operationTimeoutMs, `tap ${selector}`)
  if (!waitForChange) {
    await settle()
    return currentPath(miniProgram)
  }
  const deadline = Date.now() + operationTimeoutMs
  let actual = before
  while (Date.now() < deadline) {
    actual = await currentPath(miniProgram)
    if (actual !== before) return actual
    await settle(200)
  }
  return actual
}

async function runCase(results, definition, action) {
  const route = definition.output.route
  if (requestedRoutes.size > 0 && !requestedRoutes.has(route)) return
  process.stderr.write(`[interaction:start] ${route}\n`)
  try {
    const actual = await timeout(action(), caseTimeoutMs, `interaction ${route}`)
    const passed = definition.accept(actual)
    results.push({ ...definition.output, actual, status: passed ? 'PASS' : 'FAIL' })
  } catch (error) {
    const actual = error instanceof Error ? error.message : String(error)
    const unavailableState = actual.match(/routeState=([a-z]+)/u)?.[1]
    const unavailable = actual.startsWith('interaction precondition unavailable:')
      && unavailableState
      && definition.output.unavailableRouteStates.includes(unavailableState)
    results.push({
      ...definition.output,
      actual,
      ...(unavailable ? { routeState: unavailableState } : {}),
      status: unavailable ? 'UNAVAILABLE' : 'FAIL',
    })
  }
  process.stderr.write(`[interaction:end] ${route} ${results.at(-1)?.status ?? 'FAIL'}\n`)
}

async function runGearDetailCandidateApplyFlow(miniProgram) {
  const page = await open(miniProgram, contractPath('gear_detail'))
  const mainHandSelector = '.wx-data-role-gear-slot-row.wx-data-slot-key-main_hand'
  const workbenchSelector = '.wx-data-owner-gear-slot-workbench'
  const mainHand = await requiredElement(page, mainHandSelector)
  const committedBefore = String(await timeout(
    mainHand.attribute('data-committed-item-id'),
    2000,
    'read committed main hand item id',
  ) ?? '')
  await timeout(mainHand.tap(), 2000, 'open main hand gear candidate editor')
  const workbenchBefore = await requiredElement(page, workbenchSelector)
  const resolvedBefore = String(await timeout(
    workbenchBefore.attribute('data-resolved-slot-item-id'),
    2000,
    'read resolved main hand item id before apply',
  ) ?? '')
  const committedVariantBefore = String(await workbenchBefore.attribute('data-committed-slot-variant-key') ?? '')
  const resolvedVariantBefore = String(await workbenchBefore.attribute('data-resolved-slot-variant-key') ?? '')
  const candidates = await requiredElements(page, '.wx-data-role-gear-candidate-row', 1)
  const candidateRows = await Promise.all(candidates.map(async (element) => ({
    element,
    itemId: String(await element.attribute('data-candidate-item-id') ?? ''),
    state: String(await element.attribute('data-state') ?? ''),
  })))
  const candidate = candidateRows.find((item) => (
    item.itemId
    && item.itemId !== committedBefore
    && item.itemId !== resolvedBefore
    && item.state !== 'blocked'
  ))
  if (!candidate) {
    throw new Error(`no different resolver-eligible main hand candidate; committed=${committedBefore} resolved=${resolvedBefore}`)
  }
  await timeout(candidate.element.tap(), 2000, 'choose gear candidate draft')
  await settle(200)
  const committedAfterCandidate = String(await (await requiredElement(page, mainHandSelector)).attribute('data-committed-item-id') ?? '')
  if (committedAfterCandidate !== committedBefore) {
    throw new Error(`committed id changed before apply: before=${committedBefore} afterCandidate=${committedAfterCandidate}`)
  }
  const variants = await timeout(page.$$('.wx-data-role-gear-candidate-variant'), 3000, 'query returned gear candidate variants')
  if (variants.length > maximumInteractionElements) {
    throw new Error(`interaction query cap exceeded: gear candidate variants ${variants.length}/${maximumInteractionElements}`)
  }
  if (variants.length > 0) {
    const variantRows = await Promise.all(variants.map(async (element) => ({
      element,
      variantKey: String(await element.attribute('data-variant-key') ?? ''),
      state: String(await element.attribute('data-state') ?? ''),
    })))
    const variant = variantRows.find((item) => item.state === 'ready' || item.state === 'partial')
    if (!variant) throw new Error('no resolver-eligible returned gear candidate variant')
    await timeout(variant.element.tap(), 2000, 'choose returned gear candidate variant')
    await settle(200)
    const selectedVariantKey = String(await (
      await requiredElement(page, '.wx-data-role-gear-candidate-detail')
    ).attribute('data-candidate-draft-variant-key') ?? '')
    if (!variant.variantKey || selectedVariantKey !== variant.variantKey) {
      throw new Error(`selected returned variant mismatch: expected=${variant.variantKey} actual=${selectedVariantKey}`)
    }
    const committedAfterVariant = String(await (await requiredElement(page, mainHandSelector)).attribute('data-committed-item-id') ?? '')
    if (committedAfterVariant !== committedBefore) {
      throw new Error(`committed id changed before apply: before=${committedBefore} afterVariant=${committedAfterVariant}`)
    }
  }
  const candidateVariantKey = String(await (
    await requiredElement(page, '.wx-data-role-gear-candidate-detail')
  ).attribute('data-candidate-draft-variant-key') ?? '')
  const applySelector = contractSelector('gear_detail')
  await timeout((await requiredElement(page, applySelector)).tap(), operationTimeoutMs, 'apply gear candidate draft')
  await requiredElement(page, '.wx-data-gear-resolve-state-resolving')
  const sawResolving = true
  const deadline = Date.now() + operationTimeoutMs
  let committedAfterApply = committedBefore
  let committedVariantAfter = committedVariantBefore
  let resolvedAfterApply = resolvedBefore
  let resolvedVariantAfter = resolvedVariantBefore
  let resolveState = 'resolving'
  while (Date.now() < deadline) {
    committedAfterApply = String(await (await requiredElement(page, mainHandSelector)).attribute('data-committed-item-id') ?? '')
    const workbench = await requiredElement(page, workbenchSelector)
    resolveState = String(await workbench.attribute('data-gear-resolve-state') ?? '')
    resolvedAfterApply = String(await workbench.attribute('data-resolved-slot-item-id') ?? '')
    committedVariantAfter = String(await workbench.attribute('data-committed-slot-variant-key') ?? '')
    resolvedVariantAfter = String(await workbench.attribute('data-resolved-slot-variant-key') ?? '')
    if (gearApplyEvidenceMatches({
      candidateItemId: candidate.itemId,
      candidateVariantKey,
      committedBefore,
      committedVariantBefore,
      resolvedBefore,
      resolvedVariantBefore,
      committedAfter: committedAfterApply,
      committedVariantAfter,
      resolvedAfter: resolvedAfterApply,
      resolvedVariantAfter,
      resolveState,
      sawResolving,
    })) return 'candidate_applied_after_verified'
    await settle(200)
  }
  throw new Error(
    `verified resolve did not commit selected candidate: expected=${candidate.itemId}`
    + ` expectedVariant=${candidateVariantKey}`
    + ` committedBefore=${committedBefore} resolvedBefore=${resolvedBefore}`
    + ` committedAfter=${committedAfterApply} committedVariantAfter=${committedVariantAfter}`
    + ` resolvedAfter=${resolvedAfterApply} resolvedVariantAfter=${resolvedVariantAfter} resolveState=${resolveState}`,
  )
}

async function main() {
  requestedRoutes = requireOnlineRouteBatch(
    process.env.INTERACTION_ROUTES,
    'INTERACTION_ROUTES',
    coreInteractionContract.interactions.map((interaction) => interaction.route),
  )

  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const results = []

    await runCase(results, contractDefinition('news_home',
      (actual) => actual === 'pages/news/list',
    ), async () => {
      const page = await open(miniProgram, contractPath('news_home'))
      const metrics = await timeout(page.$$(contractSelector('news_home')), operationTimeoutMs, 'query news metrics')
      if (metrics.length > maximumInteractionElements) throw new Error(`interaction query cap exceeded: news metrics ${metrics.length}/${maximumInteractionElements}`)
      const available = (await Promise.all(metrics.slice(0, maximumInteractionElements).map(async (element) => ({ element, available: await element.attribute('data-available') })))).find((item) => item.available !== 'false')
      if (!available) throw new Error('no available news metric')
      await available.element.tap()
      await settle()
      return currentPath(miniProgram)
    })

    await runCase(results, contractDefinition('specialization_home/builds_home',
      (actual) => actual === 'pages/builds/workbench',
    ), async () => tapAndReadPath(miniProgram, await open(miniProgram, contractPath('specialization_home/builds_home')), contractSelector('specialization_home/builds_home')))

    await runCase(results, contractDefinition('current_spec_workbench',
      (actual) => typeof actual === 'string' && actual !== 'pages/builds/workbench',
    ), async () => tapAndReadPath(
      miniProgram,
      await open(miniProgram, contractPath('current_spec_workbench')),
      `${contractSelector('current_spec_workbench')}.wx-data-disabled-false`,
    ))

    await runCase(results, contractDefinition('news_list',
      (actual) => actual === 'changed',
    ), async () => {
      const page = await open(miniProgram, contractPath('news_list'))
      let sort = await requiredElement(page, contractSelector('news_list'))
      const newestSelector = `${contractSelector('news_list')}.wx-data-sort-direction-newest`
      const oldestSelector = `${contractSelector('news_list')}.wx-data-sort-direction-oldest`
      const wasNewest = Boolean(await timeout(page.$(newestSelector), 2000, 'read initial news sort direction'))
      await timeout(sort.tap(), 2000, 'toggle news sort direction')
      await requiredElement(page, wasNewest ? oldestSelector : newestSelector)
      return 'changed'
    })

    await runCase(results, contractDefinition('news_detail',
      (actual) => actual === 'collapsed',
    ), async () => {
      const page = await open(miniProgram, contractPath('news_detail'))
      await timeout((await requiredElement(page, contractSelector('news_detail'))).tap(), 2000, 'toggle news evidence')
      await requiredElement(page, '.wx-data-role-news-detail-evidence-content.wx-data-expanded-false')
      return 'collapsed'
    })

    await runCase(results, contractDefinition('build_intel',
      (actual) => actual === 'pages/builds/talent-simulator',
    ), async () => tapAndReadPath(miniProgram, await open(miniProgram, contractPath('build_intel')), contractSelector('build_intel')))

    await runCase(results, contractDefinition('talent_simulator',
      (actual) => actual === 'active',
    ), async () => {
      const page = await open(miniProgram, contractPath('talent_simulator'))
      const tabs = await requiredElementsOrUnavailable(
        page,
        contractSelector('talent_simulator'),
        2,
        contractDefinition('talent_simulator', () => true).output.unavailableRouteStates,
      )
      const activeSelector = `${contractSelector('talent_simulator')}.wx-data-active-true`
      const before = await timeout((await requiredElement(page, activeSelector)).text(), 2000, 'read initial talent tab')
      await timeout(tabs[1].tap(), 2000, 'switch talent tab')
      await waitForTextChange(page, activeSelector, before)
      return 'active'
    })

    await runCase(results, contractDefinition('gear_detail',
      (actual) => actual === 'candidate_applied_after_verified',
    ), async () => runGearDetailCandidateApplyFlow(miniProgram))

    await runCase(results, contractDefinition('simulator_home',
      (actual) => typeof actual === 'string' && actual.includes('证据'),
    ), async () => {
      const page = await open(miniProgram, contractPath('simulator_home'))
      await (await requiredElement(page, contractSelector('simulator_home'))).tap()
      await settle()
      return (await requiredElement(page, '.wx-data-role-simulator-prompt')).value()
    })

    await runCase(results, contractDefinition('SimC_submit',
      (actual) => actual === 'pages/simulator/tasks',
    ), async () => tapAndReadPath(miniProgram, await open(miniProgram, contractPath('SimC_submit')), contractSelector('SimC_submit')))

    await runCase(results, contractDefinition('chickenbro_chat',
      (actual) => actual === '',
    ), async () => {
      const page = await open(miniProgram, contractPath('chickenbro_chat'))
      const prompt = await requiredElement(page, '.wx-data-action-id-prompt')
      await timeout(prompt.input('运行态复核草稿'), 2000, 'input chickenbro prompt')
      await timeout((await requiredElement(page, contractSelector('chickenbro_chat'))).tap(), 2000, 'submit chickenbro prompt')
      await settle()
      return timeout((await requiredElement(page, '.wx-data-action-id-prompt')).value(), 2000, 'read cleared chickenbro prompt')
    })

    await runCase(results, contractDefinition('tasks_list',
      (actual) => actual === 'changed',
    ), async () => {
      const page = await open(miniProgram, contractPath('tasks_list'))
      let sort = await requiredElement(page, contractSelector('tasks_list'))
      const before = await sort.text()
      await sort.tap()
      await settle()
      sort = await requiredElement(page, contractSelector('tasks_list'))
      return before !== await sort.text() ? 'changed' : 'unchanged'
    })

    await runCase(results, contractDefinition('task_detail',
      (actual) => actual === 'pages/simulator/task-detail',
    ), async () => tapAndReadPath(miniProgram, await open(miniProgram, contractPath('task_detail')), contractSelector('task_detail'), false))

    await runCase(results, contractDefinition('profile/templates',
      (actual) => actual === 'pages/builds/talent-simulator',
    ), async () => tapAndReadPath(miniProgram, await open(miniProgram, contractPath('profile/templates')), contractSelector('profile/templates')))

    const resultRoutes = results.map((result) => result.route).sort()
    const contractRoutes = coreInteractionContract.interactions
      .map((interaction) => interaction.route)
      .filter((route) => requestedRoutes.size === 0 || requestedRoutes.has(route))
      .sort()
    const coverageMatches = JSON.stringify(resultRoutes) === JSON.stringify(contractRoutes)
    const coverageFailures = coverageMatches ? [] : [{
      route: 'contract_coverage',
      interaction: 'execute every registered core interaction exactly once',
      expected: contractRoutes.join(','),
      actual: resultRoutes.join(','),
      status: 'FAIL',
    }]
    const failures = [...results.filter((result) => result.status === 'FAIL'), ...coverageFailures]
    let detailPath = null
    if (process.env.INTERACTION_DETAIL_PATH) {
      detailPath = path.resolve(process.env.INTERACTION_DETAIL_PATH)
      const commit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' }).trim()
      const system = await waitForSystemInfo(miniProgram, 'read system info for interaction evidence')
      const viewport = { width: system.windowWidth, height: system.windowHeight, dpr: system.pixelRatio }
      const detail = {
        schemaVersion: 'wechat-core-interaction-detail-v1',
        commit,
        viewport,
        scope: 'selected_canonical_routes',
        coverageMatches,
        results,
        failures,
      }
      writeBoundedJsonAtomic(detailPath, detail, 'core interaction detail')
    }
    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'real_wechat_core_interaction',
      scope: 'selected_canonical_routes',
      coverageMatches,
      passed: results.filter((result) => result.status === 'PASS').length,
      unavailable: results.filter((result) => result.status === 'UNAVAILABLE').length,
      failureCount: failures.length,
      failedRoutes: failures.slice(0, 10).map((result) => result.route),
      detailPath,
    }))
    if (failures.length) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
