#!/usr/bin/env node
'use strict'

const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')
const { connectMiniProgram, timeout } = require('./wechat-automator')
const coreInteractionContract = require('../docs/design/current-ui/core-interaction-contract.json')

const operationTimeoutMs = 10000
// A case includes a bounded route open plus a bounded precondition/action. Keep
// a small outer margin so the semantic failure can win the timeout race.
const caseTimeoutMs = 25000
const requestedRoutes = new Set(
  (process.env.INTERACTION_ROUTES ?? '')
    .split(',')
    .map((route) => route.trim())
    .filter(Boolean),
)

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
      if (elements.length >= minimum) return elements
    } catch {}
    await settle(200)
  }
  throw new Error(`required interaction elements missing: ${selector} expected>=${minimum}`)
}

async function requiredElementsOrUnavailable(page, selector, minimum, unavailableStates) {
  const deadline = Date.now() + operationTimeoutMs
  while (Date.now() < deadline) {
    try {
      const elements = await timeout(page.$$(selector), 2000, `query ${selector}`)
      if (elements.length >= minimum) return elements
      for (const state of unavailableStates) {
        const marker = await timeout(page.$(`.wx-data-route-state-${state}`), 1000, `query route state ${state}`)
        if (marker) throw new Error(`interaction precondition unavailable: ${selector} count=${elements.length}; routeState=${state}`)
      }
    } catch (error) {
      if (error instanceof Error && error.message.startsWith('interaction precondition unavailable:')) throw error
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

async function main() {
  const knownRouteIds = new Set(coreInteractionContract.interactions.map((interaction) => interaction.route))
  const unknownRoutes = [...requestedRoutes].filter((route) => !knownRouteIds.has(route))
  if (unknownRoutes.length > 0) {
    throw new Error(`unknown INTERACTION_ROUTES: ${unknownRoutes.join(', ')}`)
  }

  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const results = []

    await runCase(results, contractDefinition('news_home',
      (actual) => actual === 'pages/news/list',
    ), async () => {
      const page = await open(miniProgram, contractPath('news_home'))
      const metrics = await timeout(page.$$(contractSelector('news_home')), operationTimeoutMs, 'query news metrics')
      const available = (await Promise.all(metrics.map(async (element) => ({ element, available: await element.attribute('data-available') })))).find((item) => item.available !== 'false')
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
      (actual) => typeof actual === 'string' && actual.length > 0,
    ), async () => {
      const page = await open(miniProgram, contractPath('gear_detail'))
      await (await requiredElement(page, contractSelector('gear_detail'))).tap()
      await settle()
      return (await requiredElement(page, '.wx-data-role-gear-candidate-count')).text()
    })

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
      fs.mkdirSync(path.dirname(detailPath), { recursive: true })
      const temporaryPath = `${detailPath}.tmp`
      const commit = execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], { cwd: path.resolve(__dirname, '..'), encoding: 'utf8' }).trim()
      const system = await timeout(miniProgram.systemInfo(), 4000, 'read system info for interaction evidence')
      const viewport = { width: system.windowWidth, height: system.windowHeight, dpr: system.pixelRatio }
      const detail = {
        schemaVersion: 'wechat-core-interaction-detail-v1',
        commit,
        viewport,
        scope: requestedRoutes.size === 0 ? 'all_14_canonical_routes' : 'selected_canonical_routes',
        coverageMatches,
        results,
        failures,
      }
      fs.writeFileSync(temporaryPath, `${JSON.stringify(detail, null, 2)}\n`)
      fs.renameSync(temporaryPath, detailPath)
    }
    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'real_wechat_core_interaction',
      scope: requestedRoutes.size === 0 ? 'all_14_canonical_routes' : 'selected_canonical_routes',
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
