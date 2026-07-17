#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')

const operationTimeoutMs = 10000

async function settle(milliseconds = 650) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function requiredElement(page, selector) {
  const element = await timeout(page.$(selector), operationTimeoutMs, `query ${selector}`)
  if (!element) throw new Error(`required interaction element missing: ${selector}`)
  return element
}

async function currentPath(miniProgram) {
  return (await timeout(miniProgram.currentPage(), operationTimeoutMs, 'read current page')).path
}

async function open(miniProgram, path) {
  const page = await timeout(miniProgram.reLaunch(path), operationTimeoutMs, `open ${path}`)
  await settle()
  return page
}

async function tapAndReadPath(miniProgram, page, selector) {
  await timeout((await requiredElement(page, selector)).tap(), operationTimeoutMs, `tap ${selector}`)
  await settle()
  return currentPath(miniProgram)
}

async function runCase(results, definition, action) {
  try {
    const actual = await action()
    const passed = definition.accept(actual)
    results.push({ ...definition.output, actual, status: passed ? 'PASS' : 'FAIL' })
  } catch (error) {
    results.push({
      ...definition.output,
      actual: error instanceof Error ? error.message : String(error),
      status: 'FAIL',
    })
  }
}

async function main() {
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const results = []

    await runCase(results, {
      output: { route: 'news_home', interaction: 'open an available news metric', expected: 'pages/news/list' },
      accept: (actual) => actual === 'pages/news/list',
    }, async () => {
      const page = await open(miniProgram, '/pages/news/news')
      const metrics = await timeout(page.$$('.wx-data-role-news-home-metric'), operationTimeoutMs, 'query news metrics')
      const available = (await Promise.all(metrics.map(async (element) => ({ element, available: await element.attribute('data-available') })))).find((item) => item.available !== 'false')
      if (!available) throw new Error('no available news metric')
      await available.element.tap()
      await settle()
      return currentPath(miniProgram)
    })

    await runCase(results, {
      output: { route: 'builds_home', interaction: 'enter current specialization workbench', expected: 'pages/builds/workbench' },
      accept: (actual) => actual === 'pages/builds/workbench',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/builds/builds'), '.wx-data-role-build-workspace-action'))

    await runCase(results, {
      output: { route: 'current_spec_workbench', interaction: 'open the first enabled workbench module', expected: 'a different registered route' },
      accept: (actual) => typeof actual === 'string' && actual !== 'pages/builds/workbench',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/builds/workbench'), '.wx-data-role-workbench-module-card'))

    await runCase(results, {
      output: { route: 'news_list', interaction: 'toggle news ordering', expected: 'sort direction changes' },
      accept: (actual) => actual === 'changed',
    }, async () => {
      const page = await open(miniProgram, '/pages/news/list')
      let sort = await requiredElement(page, '.wx-data-role-news-list-sort')
      const before = await sort.attribute('data-sort-direction')
      await sort.tap()
      await settle()
      sort = await requiredElement(page, '.wx-data-role-news-list-sort')
      return before !== await sort.attribute('data-sort-direction') ? 'changed' : 'unchanged'
    })

    await runCase(results, {
      output: { route: 'news_detail', interaction: 'collapse article evidence', expected: 'evidence body becomes absent' },
      accept: (actual) => actual === 'collapsed',
    }, async () => {
      const page = await open(miniProgram, '/pages/news/detail?id=architecture-preflight')
      await (await requiredElement(page, '.wx-data-role-news-detail-evidence-toggle')).tap()
      await settle()
      return await page.$('.wx-data-role-news-detail-evidence-body') ? 'expanded' : 'collapsed'
    })

    await runCase(results, {
      output: { route: 'build_intel', interaction: 'open a build evidence simulator', expected: 'pages/builds/talent-simulator' },
      accept: (actual) => actual === 'pages/builds/talent-simulator',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/builds/intel'), '.wx-data-role-build-intel-primary-action'))

    await runCase(results, {
      output: { route: 'talent_simulator', interaction: 'switch the visible talent tree', expected: 'second tree tab becomes active' },
      accept: (actual) => actual === 'active',
    }, async () => {
      const page = await open(miniProgram, '/pages/builds/talent-simulator')
      const tabs = await timeout(page.$$('.wx-data-role-talent-tree-tab'), operationTimeoutMs, 'query talent tabs')
      if (tabs.length < 2) throw new Error('fewer than two talent tabs')
      await tabs[1].tap()
      await settle()
      const refreshed = await timeout(page.$$('.wx-data-role-talent-tree-tab'), operationTimeoutMs, 'refresh talent tabs')
      return await refreshed[1].attribute('data-active') === 'true' ? 'active' : 'inactive'
    })

    await runCase(results, {
      output: { route: 'gear_detail', interaction: 'open a gear slot candidate panel', expected: 'candidate count is visible' },
      accept: (actual) => typeof actual === 'string' && actual.length > 0,
    }, async () => {
      const page = await open(miniProgram, '/pages/builds/detail')
      await (await requiredElement(page, '.wx-data-role-gear-slot-row')).tap()
      await settle()
      return (await requiredElement(page, '.wx-data-role-gear-candidate-count')).text()
    })

    await runCase(results, {
      output: { route: 'simulator_home', interaction: 'prepare an evidence-bound follow-up', expected: 'composer contains evidence request' },
      accept: (actual) => typeof actual === 'string' && actual.includes('证据'),
    }, async () => {
      const page = await open(miniProgram, '/pages/simulator/simulator')
      await (await requiredElement(page, '.wx-data-action-id-manage-evidence')).tap()
      await settle()
      return (await requiredElement(page, '.wx-style-simulatorPrompt')).value()
    })

    await runCase(results, {
      output: { route: 'SimC_submit', interaction: 'open SimC submission records', expected: 'pages/simulator/tasks' },
      accept: (actual) => actual === 'pages/simulator/tasks',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/simulator/simc'), '.wx-data-action-id-submission-records'))

    await runCase(results, {
      output: { route: 'chickenbro_chat', interaction: 'reset the current assistant topic', expected: 'draft becomes empty' },
      accept: (actual) => actual === '',
    }, async () => {
      const page = await open(miniProgram, '/pages/simulator/chickenbro')
      const prompt = await requiredElement(page, '.wx-data-action-id-prompt')
      await prompt.input('运行态复核草稿')
      await (await requiredElement(page, '.wx-data-action-id-new-topic')).tap()
      await settle()
      return (await requiredElement(page, '.wx-data-action-id-prompt')).value()
    })

    await runCase(results, {
      output: { route: 'tasks_list', interaction: 'toggle owner task ordering', expected: 'sort control label changes' },
      accept: (actual) => actual === 'changed',
    }, async () => {
      const page = await open(miniProgram, '/pages/simulator/tasks')
      let sort = await requiredElement(page, '.wx-data-action-id-toggle-sort')
      const before = await sort.text()
      await sort.tap()
      await settle()
      sort = await requiredElement(page, '.wx-data-action-id-toggle-sort')
      return before !== await sort.text() ? 'changed' : 'unchanged'
    })

    await runCase(results, {
      output: { route: 'task_detail', interaction: 'refresh the same task', expected: 'remain on pages/simulator/task-detail' },
      accept: (actual) => actual === 'pages/simulator/task-detail',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/simulator/task-detail?id=runtime-review'), '.wx-data-action-id-refresh-task'))

    await runCase(results, {
      output: { route: 'profile/templates', interaction: 'open the first template category', expected: 'pages/builds/talent-simulator' },
      accept: (actual) => actual === 'pages/builds/talent-simulator',
    }, async () => tapAndReadPath(miniProgram, await open(miniProgram, '/pages/profile/profile'), '.wx-data-role-profile-category-card'))

    const failures = results.filter((result) => result.status !== 'PASS')
    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'real_wechat_core_interaction',
      scope: 'all_14_canonical_routes',
      results,
      failures,
    }, null, 2))
    if (failures.length) process.exitCode = 1
  } finally {
    if (miniProgram) miniProgram.disconnect()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exit(1)
})
