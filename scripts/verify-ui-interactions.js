#!/usr/bin/env node
'use strict'

const { connectMiniProgram, timeout } = require('./wechat-automator')

const operationTimeoutMs = 10000

async function requiredElement(page, selector) {
  const element = await timeout(page.$(selector), operationTimeoutMs, `query ${selector}`)
  if (!element) throw new Error(`required interaction element missing: ${selector}`)
  return element
}

async function settle(milliseconds = 700) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function main() {
  let miniProgram
  try {
    miniProgram = await connectMiniProgram()
    const results = []

    let page = await timeout(miniProgram.reLaunch('/pages/builds/builds'), operationTimeoutMs, 'open builds_home')
    await settle()
    const workspaceAction = await requiredElement(page, '.wx-data-role-build-workspace-action')
    await timeout(workspaceAction.tap(), operationTimeoutMs, 'enter builds workbench')
    await settle()
    page = await timeout(miniProgram.currentPage(), operationTimeoutMs, 'read builds workbench page')
    results.push({
      route: 'builds_home',
      interaction: 'enter current specialization workbench',
      expected: 'pages/builds/workbench',
      actual: page.path,
      status: page.path === 'pages/builds/workbench' ? 'PASS' : 'FAIL',
    })

    page = await timeout(miniProgram.reLaunch('/pages/builds/detail'), operationTimeoutMs, 'open gear_detail')
    await settle(1000)
    const slot = await requiredElement(page, '.wx-data-role-gear-slot-row')
    const slotKey = await timeout(slot.attribute('data-slot-key'), operationTimeoutMs, 'read gear slot key')
    await timeout(slot.tap(), operationTimeoutMs, `open gear slot ${slotKey}`)
    await settle()
    const candidateCount = await requiredElement(page, '.wx-data-role-gear-candidate-count')
    results.push({
      route: 'gear_detail',
      interaction: 'open a gear slot candidate panel',
      expected: `candidate panel for ${slotKey}`,
      actual: await timeout(candidateCount.text(), operationTimeoutMs, 'read candidate count'),
      status: 'PASS',
    })

    const failures = results.filter((result) => result.status !== 'PASS')
    console.log(JSON.stringify({
      status: failures.length ? 'fail' : 'pass',
      evidence: 'real_wechat_core_interaction',
      scope: 'current_builds_batch',
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
