#!/usr/bin/env node
'use strict'

const fs = require('node:fs')
const path = require('node:path')
const {
  connectMiniProgram,
  findElementBySemanticValue,
  queryElementsByXpathSequentially,
  readSemanticValue,
  scrollElementIntoView,
  scrollPageElementIntoView,
  timeout,
  waitForRenderedPage,
  waitForSystemInfo,
} = require('./wechat-automator')
const { writeBoundedJsonAtomic } = require('./bounded-json-detail')
const { gearApplyEvidenceMatches } = require('./gear-apply-evidence')
const {
  assertRuntimeBuildIdentity,
  gearSlots,
  normalizeCandidateDisplayRelations,
  normalizeCommittedGearEntries,
  normalizeGearSlotShard,
  normalizeSelectorMarker,
  normalizeSimcPolicy,
  normalizeSpecMatrix,
  normalizeTaskIds,
  requiredActions,
  selectCandidateApplySlot,
  selectCraftedApplyTarget,
  storageValueChanged,
} = require('./wechat-gear-matrix-contract')

const routeReadyTimeoutMs = 45000
const operationTimeoutMs = 15000
const resolveTimeoutMs = 20000
const simcConfirmTimeoutMs = 60000
const simcTaskTimeoutMs = 180000
const maximumCandidatesPerSlot = 64
const maximumVariantsPerItem = 32
const templateStorageKey = 'wow_build_templates_v1'
const variantXpath = '//*[contains(@class, "wx-data-role-gear-candidate-variant")]'
const templateTabXpath = '//*[contains(concat(" ", normalize-space(@class), " "), " wx-style-templatesheettab ")]'
const identityFields = Object.freeze([
  'manifestRevision',
  'gearCatalogRevision',
  'gearExactRegistryRevision',
  'gearCatalogReleaseId',
  'communityTemplateReleaseId',
  'pointerGeneration',
])

function requiredEnvironment(name) {
  const value = String(process.env[name] ?? '').trim()
  if (!value) throw new Error(`${name} is required`)
  return value
}

function settle(milliseconds = 250) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

async function poll(action, accept, timeoutMs, label) {
  const deadline = Date.now() + timeoutMs
  let lastError = null
  let lastValue
  while (Date.now() < deadline) {
    try {
      lastValue = await action()
      if (accept(lastValue)) return lastValue
    } catch (error) {
      lastError = error
    }
    await settle()
  }
  const errorDetail = lastError instanceof Error ? `; lastError=${lastError.message}` : ''
  throw new Error(`${label} timed out after ${timeoutMs}ms; lastValue=${JSON.stringify(lastValue)}${errorDetail}`)
}

async function requiredElement(page, selector, timeoutMs = operationTimeoutMs) {
  return poll(
    () => timeout(page.$(selector), 2500, `query ${selector}`),
    Boolean,
    timeoutMs,
    `required element ${selector}`,
  )
}

async function waitForMissing(page, selector, timeoutMs = operationTimeoutMs) {
  await poll(
    () => timeout(page.$(selector), 2500, `query missing ${selector}`),
    (element) => !element,
    timeoutMs,
    `element remained present ${selector}`,
  )
}

async function waitForRouteReady(page) {
  const terminalStates = ['blocked', 'error', 'stale', 'empty']
  const deadline = Date.now() + routeReadyTimeoutMs
  while (Date.now() < deadline) {
    if (await timeout(page.$('.wx-data-route-state-ready'), 2500, 'query ready route state')) return
    for (const state of terminalStates) {
      if (await timeout(page.$(`.wx-data-route-state-${state}`), 1500, `query route state ${state}`)) {
        throw new Error(`gear route is ${state}`)
      }
    }
    await settle()
  }
  throw new Error(`gear route did not become ready after ${routeReadyTimeoutMs}ms`)
}

async function openRoute(miniProgram, route) {
  const page = await timeout(miniProgram.reLaunch(route), operationTimeoutMs, `open ${route}`)
  await waitForRenderedPage(page, `render ${route}`)
  await waitForRouteReady(page)
  return page
}

function normalizedPagePath(value) {
  return String(value ?? '').replace(/^\/+/u, '')
}

async function waitForCurrentPage(miniProgram, expectedPath) {
  const normalizedExpected = normalizedPagePath(expectedPath)
  const page = await poll(
    () => timeout(miniProgram.currentPage(), 2500, `read current page ${normalizedExpected}`),
    (current) => normalizedPagePath(current?.path) === normalizedExpected,
    operationTimeoutMs,
    `navigate to ${normalizedExpected}`,
  )
  await waitForRenderedPage(page, `render ${normalizedExpected}`)
  await waitForRouteReady(page)
  return page
}

async function openTaskList(miniProgram) {
  const route = '/pages/simulator/tasks'
  const page = await timeout(miniProgram.reLaunch(route), operationTimeoutMs, `open ${route}`)
  await waitForRenderedPage(page, `render ${route}`)
  await poll(
    async () => {
      const list = await timeout(page.$('.wx-data-owner-task-record-list'), 2500, 'query task list owner')
      if (!list) return 'loading'
      if (await timeout(page.$('.wx-data-route-state-ready'), 1500, 'query ready task route')) return 'ready'
      if (await timeout(page.$('.wx-data-route-state-empty'), 1500, 'query empty task route')) return 'empty'
      if (await timeout(page.$('.wx-data-route-state-error'), 1500, 'query error task route')) return 'error'
      if (await timeout(page.$('.wx-data-route-state-blocked'), 1500, 'query blocked task route')) return 'blocked'
      return 'loading'
    },
    (state) => state === 'ready' || state === 'empty',
    routeReadyTimeoutMs,
    'task list route readiness',
  )
  return page
}

async function visibleTaskIds(page) {
  const rows = await timeout(page.$$('.wx-data-role-task-record-row'), 3000, 'query task record rows')
  if (rows.length > 512) throw new Error(`task record row cap exceeded: ${rows.length}/512`)
  const values = await Promise.all(rows.map((row) => readSemanticValue(row, 'task-id')))
  return normalizeTaskIds(values)
}

async function taskRow(page, taskId) {
  const rows = await timeout(page.$$('.wx-data-role-task-record-row'), 3000, 'query task record rows')
  for (const row of rows) {
    if (String(await readSemanticValue(row, 'task-id') ?? '') === taskId) return row
  }
  return null
}

function assertSameTaskIds(before, after, label) {
  if (JSON.stringify([...before].sort()) !== JSON.stringify([...after].sort())) {
    throw new Error(`${label} changed owner-scoped task IDs: before=${before.join(',')} after=${after.join(',')}`)
  }
}

async function fetchJson(url, label) {
  const response = await fetch(url, { signal: AbortSignal.timeout(operationTimeoutMs) })
  const text = await response.text()
  if (!response.ok) throw new Error(`${label} HTTP ${response.status}: ${text.slice(0, 240)}`)
  try {
    return JSON.parse(text)
  } catch {
    throw new Error(`${label} did not return JSON`)
  }
}

function slotUrl(apiBaseUrl, spec, slot) {
  const url = new URL('/api/websim/gear', apiBaseUrl)
  url.searchParams.set('classKey', spec.classKey)
  url.searchParams.set('specKey', spec.specKey)
  url.searchParams.set('compact', 'true')
  url.searchParams.set('mode', 'slot')
  url.searchParams.set('slot', slot)
  return url
}

function identityVector(payload) {
  return Object.fromEntries(identityFields.map((field) => [field, payload?.[field] ?? null]))
}

function assertIdentityVector(expected, actual, label) {
  for (const field of identityFields) {
    if (expected[field] !== actual[field]) {
      throw new Error(`${label} mixed ${field}: expected=${expected[field]} actual=${actual[field]}`)
    }
  }
}

function expectedSlot(payload, slot) {
  const groups = Array.isArray(payload?.replacementCandidates) ? payload.replacementCandidates : []
  if (groups.length !== 1 || groups[0]?.slot !== slot || !Array.isArray(groups[0]?.items)) {
    throw new Error(`compact slot payload did not return exactly ${slot}`)
  }
  return groups[0]
}

function compareStringSets(expectedValues, actualValues, label) {
  const expected = [...new Set(expectedValues)].sort()
  const actual = [...new Set(actualValues)].sort()
  if (JSON.stringify(expected) !== JSON.stringify(actual)) {
    const missing = expected.filter((item) => !actual.includes(item))
    const extra = actual.filter((item) => !expected.includes(item))
    throw new Error(`${label} mismatch: missing=${missing.join(',')} extra=${extra.join(',')}`)
  }
}

function assertVisibleText(text, expectedValues, label) {
  const actual = String(text ?? '')
  const missing = [...new Set(expectedValues.map(String).filter(Boolean))]
    .filter((value) => !actual.includes(value))
  if (missing.length) {
    throw new Error(`${label} visible text is missing ${missing.join(' | ')}; actual=${actual.slice(0, 480)}`)
  }
}

async function trustedCandidateMedia(row, itemId) {
  const media = await poll(
    async () => {
      const element = await timeout(
        row.$('.wx-data-role-gear-candidate-media'),
        2500,
        `query candidate ${itemId} media`,
      )
      if (!element) return { element: null, state: 'missing', visible: 'false' }
      return {
        element,
        state: String(await readSemanticValue(element, 'media-state') ?? ''),
        visible: String(await readSemanticValue(element, 'media-visible') ?? ''),
      }
    },
    (value) => value.state === 'loaded' && value.visible === 'true',
    operationTimeoutMs,
    `candidate ${itemId} trusted image`,
  )
  return {
    mediaState: media.state,
    mediaVisible: media.visible === 'true',
    status: 'PASS',
  }
}

async function visibleCandidateRows(page, expectedCount) {
  return poll(
    async () => {
      const loading = await timeout(page.$('.wx-data-role-gear-candidate-loading'), 1500, 'query candidate loading')
      const rows = await timeout(page.$$('.wx-data-role-gear-candidate-row'), 3000, 'query candidate rows')
      if (rows.length > maximumCandidatesPerSlot) {
        throw new Error(`candidate cap exceeded: ${rows.length}/${maximumCandidatesPerSlot}`)
      }
      return { loading: Boolean(loading), rows }
    },
    ({ loading, rows }) => !loading && rows.length === expectedCount,
    operationTimeoutMs,
    `wait for ${expectedCount} rendered candidates`,
  ).then((result) => result.rows)
}

async function rowIdentityMap(rows) {
  const entries = await Promise.all(rows.map(async (row) => ({
    row,
    itemId: String(await readSemanticValue(row, 'candidate-item-id') ?? ''),
    state: String(await readSemanticValue(row, 'state') ?? ''),
    text: String(await timeout(row.text(), 2500, 'read candidate row visible text') ?? ''),
  })))
  if (entries.some((entry) => !entry.itemId)) throw new Error('rendered candidate is missing item identity')
  if (new Set(entries.map((entry) => entry.itemId)).size !== entries.length) {
    throw new Error('rendered candidate item identities are not unique')
  }
  return new Map(entries.map((entry) => [entry.itemId, entry]))
}

async function inspectCandidateRow(entry, relation) {
  if (entry.state !== relation.uiState) {
    throw new Error(
      `candidate ${relation.itemId} UI state mismatch: expected=${relation.uiState} actual=${entry.state}`,
    )
  }
  assertVisibleText(
    entry.text,
    [
      relation.itemName,
      relation.levelLabel,
      relation.statSummary,
      relation.sourceLabel,
    ],
    `candidate ${relation.itemId} row`,
  )
  return {
    itemId: relation.itemId,
    state: entry.state,
    media: await trustedCandidateMedia(entry.row, relation.itemId),
    status: 'PASS',
  }
}

function candidateDetailExpectedText(relation, variant = null) {
  return [
    relation.itemName,
    variant?.levelLabel ?? relation.levelLabel,
    relation.sourceLabel,
    variant?.statSummary ?? relation.statSummary,
    relation.equipmentTypeLabel,
  ]
}

async function visibleVariantElements(page, relation) {
  const variants = relation.variants.length === 0
    ? []
    : await poll(
        () => queryElementsByXpathSequentially(page, variantXpath, maximumVariantsPerItem),
        (items) => items.length === relation.variants.length,
        operationTimeoutMs,
        `wait for candidate ${relation.itemId} progression variants`,
      )
  return Promise.all(variants.map(async (element) => ({
    element,
    markerKey: String(await readSemanticValue(element, 'variant-key') ?? ''),
    state: String(await readSemanticValue(element, 'state') ?? ''),
    text: String(await timeout(
      element.text(),
      2500,
      `read candidate ${relation.itemId} variant visible text`,
    ) ?? ''),
  })))
}

async function tapGearEditorElement(page, element, label, requery = null) {
  const scrollView = await requiredElement(page, '.wx-data-role-gear-editor-scroll')
  const scrolled = await scrollElementIntoView(scrollView, element, label)
  if (scrolled) await settle()
  const current = requery ? await requery() : element
  await timeout(current.tap(), 3000, label)
}

async function tapPageElement(
  miniProgram,
  page,
  systemInfo,
  element,
  label,
  requery = null,
) {
  const scrolled = await scrollPageElementIntoView(
    miniProgram,
    page,
    element,
    systemInfo.windowHeight,
    label,
  )
  if (scrolled) await settle()
  const current = requery ? await requery() : element
  await timeout(current.tap(), 3000, label)
}

async function inspectCandidateVariants(page, relation) {
  const candidateSelector = `.wx-data-role-gear-candidate-row.wx-data-candidate-item-id-${normalizeSelectorMarker(relation.itemId)}`
  const candidate = await requiredElement(page, candidateSelector)
  await tapGearEditorElement(
    page,
    candidate,
    `open candidate ${relation.itemId}`,
    () => requiredElement(page, candidateSelector),
  )
  const selectedDetail = await poll(
    async () => {
      const element = await timeout(
        page.$('.wx-data-role-gear-candidate-detail'),
        2500,
        `query candidate ${relation.itemId} detail`,
      )
      return {
        element,
        itemId: element
          ? String(await readSemanticValue(element, 'candidate-draft-item-id') ?? '')
          : '',
      }
    },
    (value) => Boolean(value.element) && value.itemId === relation.itemId,
    operationTimeoutMs,
    `wait for candidate ${relation.itemId} detail identity`,
  )
  const detailText = String(await timeout(
    selectedDetail.element.text(),
    2500,
    `read candidate ${relation.itemId} detail visible text`,
  ) ?? '')
  assertVisibleText(
    detailText,
    candidateDetailExpectedText(relation),
    `candidate ${relation.itemId} detail`,
  )
  const actual = await visibleVariantElements(page, relation)
  compareStringSets(
    relation.variants.map((item) => item.markerKey),
    actual.map((item) => item.markerKey),
    `item ${relation.itemId} progression variants`,
  )
  const expectedByKey = new Map(relation.variants.map((item) => [item.markerKey, item]))
  for (const item of actual) {
    const expected = expectedByKey.get(item.markerKey)
    if (!expected) throw new Error(`candidate ${relation.itemId} rendered unexpected variant ${item.markerKey}`)
    if (item.state !== expected.uiState) {
      throw new Error(
        `candidate ${relation.itemId} variant ${expected.variantKey} UI state mismatch: expected=${expected.uiState} actual=${item.state}`,
      )
    }
    assertVisibleText(
      item.text,
      [expected.label, expected.progression, expected.levelLabel],
      `candidate ${relation.itemId} variant ${expected.variantKey}`,
    )
  }
  let selectedVariantFactChecks = 0
  let craftedOptionFactChecks = 0
  let selectedCraftedOptionFactChecks = 0
  const craftedApplyTargets = []
  for (const variant of relation.variants.filter((item) => item.uiState === 'ready' || item.uiState === 'partial')) {
    const current = await poll(
      () => findElementBySemanticValue(
        page,
        variantXpath,
        maximumVariantsPerItem,
        'variant-key',
        variant.markerKey,
      ),
      Boolean,
      operationTimeoutMs,
      `rendered canonical variant ${relation.itemId}/${variant.variantKey}`,
    )
    await tapGearEditorElement(
      page,
      current,
      `select inspected canonical variant ${variant.markerKey}`,
      () => poll(
        () => findElementBySemanticValue(
          page,
          variantXpath,
          maximumVariantsPerItem,
          'variant-key',
          variant.markerKey,
        ),
        Boolean,
        operationTimeoutMs,
        `requery canonical variant ${relation.itemId}/${variant.variantKey}`,
      ),
    )
    const selected = await poll(
      async () => {
        const element = await requiredElement(page, '.wx-data-role-gear-candidate-detail')
        return {
          element,
          markerKey: String(await readSemanticValue(
            element,
            'candidate-draft-variant-key',
          ) ?? ''),
        }
      },
      (value) => value.markerKey === variant.markerKey,
      operationTimeoutMs,
      `wait for candidate ${relation.itemId} selected variant ${variant.variantKey}`,
    )
    const selectedText = String(await timeout(
      selected.element.text(),
      2500,
      `read selected candidate ${relation.itemId}/${variant.variantKey} detail`,
    ) ?? '')
    assertVisibleText(
      selectedText,
      candidateDetailExpectedText(relation, variant),
      `selected candidate ${relation.itemId}/${variant.variantKey} detail`,
    )
    const craftedElements = await timeout(
      page.$$('.wx-data-role-gear-crafted-stat-option'),
      3000,
      `query candidate ${relation.itemId}/${variant.variantKey} crafted stat options`,
    )
    if (craftedElements.length !== variant.craftedStatOptions.length) {
      throw new Error(
        `candidate ${relation.itemId}/${variant.variantKey} crafted option count mismatch: `
        + `expected=${variant.craftedStatOptions.length} actual=${craftedElements.length}`,
      )
    }
    const craftedActual = await Promise.all(craftedElements.map(async (element) => ({
      element,
      optionId: String(await readSemanticValue(element, 'crafted-option-id') ?? ''),
      state: String(await readSemanticValue(element, 'state') ?? ''),
      text: String(await timeout(
        element.text(),
        2500,
        `read candidate ${relation.itemId}/${variant.variantKey} crafted option`,
      ) ?? ''),
    })))
    compareStringSets(
      variant.craftedStatOptions.map((option) => option.optionId),
      craftedActual.map((option) => option.optionId),
      `candidate ${relation.itemId}/${variant.variantKey} crafted options`,
    )
    const craftedById = new Map(
      craftedActual.map((option) => [option.optionId, option]),
    )
    for (const option of variant.craftedStatOptions) {
      const actualOption = craftedById.get(option.optionId)
      if (!actualOption) {
        throw new Error(
          `candidate ${relation.itemId}/${variant.variantKey} crafted option ${option.optionId} disappeared`,
        )
      }
      if (actualOption.state !== option.uiState) {
        throw new Error(
          `candidate ${relation.itemId}/${variant.variantKey} crafted option ${option.optionId} `
          + `state mismatch: expected=${option.uiState} actual=${actualOption.state}`,
        )
      }
      assertVisibleText(
        actualOption.text,
        [option.label, `crafted_stats=${option.craftedStats}`],
        `candidate ${relation.itemId}/${variant.variantKey} crafted option ${option.optionId}`,
      )
      craftedOptionFactChecks += 1
      if (option.uiState !== 'ready') continue
      await tapGearEditorElement(
        page,
        actualOption.element,
        `select crafted option ${option.optionId}`,
        async () => {
          const rendered = await timeout(
            page.$$('.wx-data-role-gear-crafted-stat-option'),
            3000,
            `requery crafted options for ${relation.itemId}/${variant.variantKey}`,
          )
          for (const element of rendered) {
            if (String(await readSemanticValue(element, 'crafted-option-id') ?? '') === option.optionId) {
              return element
            }
          }
          throw new Error(`crafted option ${option.optionId} disappeared after scroll`)
        },
      )
      await poll(
        async () => {
          const detail = await requiredElement(
            page,
            '.wx-data-role-gear-candidate-detail',
          )
          return String(await readSemanticValue(
            detail,
            'candidate-draft-crafted-option-id',
          ) ?? '')
        },
        (selectedOptionId) => selectedOptionId === option.optionId,
        operationTimeoutMs,
        `wait for crafted option ${option.optionId} active`,
      )
      selectedCraftedOptionFactChecks += 1
      craftedApplyTargets.push({
        itemId: relation.itemId,
        variantKey: variant.variantKey,
        craftedOptionId: option.optionId,
      })
    }
    selectedVariantFactChecks += 1
  }
  const actualByKey = new Map(actual.map((item) => [item.markerKey, item]))
  return {
    itemDetailFactCheck: {
      itemId: relation.itemId,
      status: 'PASS',
    },
    selectedVariantFactChecks,
    craftedOptionFactChecks,
    selectedCraftedOptionFactChecks,
    craftedApplyTargets,
    variantRelations: relation.variants.map((variant) => ({
      itemId: relation.itemId,
      itemName: relation.itemName,
      variantKey: variant.variantKey,
      progression: variant.progression,
      progressionKind: variant.progressionKind,
      itemLevel: variant.itemLevel,
      apiStatus: variant.apiStatus,
      uiState: actualByKey.get(variant.markerKey)?.state ?? '',
      craftedStatSelectionRequired: variant.craftedStatSelectionRequired,
      craftedStatOptions: variant.craftedStatOptions,
      displayFactsStatus: 'PASS',
      selectedDetailStatus: variant.uiState === 'blocked' ? 'NOT_SELECTABLE_BLOCKED' : 'PASS',
      status: actualByKey.has(variant.markerKey) ? 'PASS' : 'FAIL',
    })),
  }
}

async function closeCandidateEditor(page) {
  const close = await requiredElement(page, '.wx-data-action-id-gear-candidate-close')
  await timeout(close.tap(), 3000, 'close candidate editor')
  await waitForMissing(page, '.wx-data-owner-gear-candidate-editor-sheet')
}

async function inspectSlot(miniProgram, page, systemInfo, apiBaseUrl, spec, slot, stableIdentity) {
  const payload = await fetchJson(slotUrl(apiBaseUrl, spec, slot), `${spec.specId}/${slot} compact slot`)
  assertIdentityVector(stableIdentity, identityVector(payload), `${spec.specId}/${slot}`)
  const group = expectedSlot(payload, slot)
  const relations = normalizeCandidateDisplayRelations(group)
  const slotControl = await requiredElement(
    page,
    `.wx-data-role-gear-slot-row.wx-data-slot-key-${normalizeSelectorMarker(slot)}`,
  )
  const slotSelector = `.wx-data-role-gear-slot-row.wx-data-slot-key-${normalizeSelectorMarker(slot)}`
  await tapPageElement(
    miniProgram,
    page,
    systemInfo,
    slotControl,
    `open ${slot}`,
    () => requiredElement(page, slotSelector),
  )
  await requiredElement(page, '.wx-data-owner-gear-candidate-editor-sheet')
  const rows = await visibleCandidateRows(page, relations.length)
  const byItem = await rowIdentityMap(rows)
  compareStringSets(relations.map((item) => item.itemId), [...byItem.keys()], `${spec.specId}/${slot} items`)

  const candidateRowFactChecks = []
  for (const relation of relations) {
    const entry = byItem.get(relation.itemId)
    if (!entry) throw new Error(`${spec.specId}/${slot} rendered candidate ${relation.itemId} disappeared`)
    candidateRowFactChecks.push(await inspectCandidateRow(entry, relation))
  }
  const variantRelations = []
  const candidateDetailFactChecks = []
  let selectedVariantFactChecks = 0
  let craftedOptionFactChecks = 0
  let selectedCraftedOptionFactChecks = 0
  const craftedApplyTargets = []
  for (const relation of relations) {
    const inspected = await inspectCandidateVariants(page, relation)
    variantRelations.push(...inspected.variantRelations)
    candidateDetailFactChecks.push(inspected.itemDetailFactCheck)
    selectedVariantFactChecks += inspected.selectedVariantFactChecks
    craftedOptionFactChecks += inspected.craftedOptionFactChecks
    selectedCraftedOptionFactChecks += (
      inspected.selectedCraftedOptionFactChecks
    )
    craftedApplyTargets.push(...inspected.craftedApplyTargets)
  }
  await closeCandidateEditor(page)
  const expectedSelectableVariants = relations.reduce(
    (sum, item) => sum + item.variants.filter(
      (variant) => variant.uiState === 'ready' || variant.uiState === 'partial',
    ).length,
    0,
  )
  return {
    slot,
    status: (
      candidateRowFactChecks.every((item) => item.status === 'PASS')
      && candidateDetailFactChecks.every((item) => item.status === 'PASS')
      && variantRelations.every((item) => (
        item.status === 'PASS'
        && item.displayFactsStatus === 'PASS'
        && (
          item.selectedDetailStatus === 'PASS'
          || item.selectedDetailStatus === 'NOT_SELECTABLE_BLOCKED'
        )
      ))
      && selectedVariantFactChecks === expectedSelectableVariants
      && craftedOptionFactChecks === selectedCraftedOptionFactChecks
    ) ? 'PASS' : 'FAIL',
    expectedItems: relations.length,
    actualItems: byItem.size,
    candidateRowFactChecks: candidateRowFactChecks.length,
    candidateMediaChecks: candidateRowFactChecks.filter(
      (item) => item.media.status === 'PASS' && item.media.mediaVisible,
    ).length,
    candidateDetailFactChecks: candidateDetailFactChecks.length,
    expectedVariants: relations.reduce((sum, item) => sum + item.variants.length, 0),
    actualVariants: variantRelations.filter((item) => item.status === 'PASS').length,
    variantDisplayFactChecks: variantRelations.filter(
      (item) => item.displayFactsStatus === 'PASS',
    ).length,
    expectedSelectableVariants,
    selectedVariantFactChecks,
    craftedOptionFactChecks,
    selectedCraftedOptionFactChecks,
    craftedApplyTargets: craftedApplyTargets.map((target) => ({
      slot,
      ...target,
    })),
    itemRelations: variantRelations,
  }
}

async function readSlotState(page, slot) {
  const row = await requiredElement(page, `.wx-data-role-gear-slot-row.wx-data-slot-key-${normalizeSelectorMarker(slot)}`)
  const workbench = await requiredElement(page, '.wx-data-owner-gear-slot-workbench')
  return {
    row,
    committedItemId: String(await readSemanticValue(row, 'committed-item-id') ?? ''),
    committedVariantKey: String(await readSemanticValue(workbench, 'committed-slot-variant-key') ?? ''),
    resolvedItemId: String(await readSemanticValue(workbench, 'resolved-slot-item-id') ?? ''),
    resolvedVariantKey: String(await readSemanticValue(workbench, 'resolved-slot-variant-key') ?? ''),
    committedCraftedOptionId: String(await readSemanticValue(
      workbench,
      'committed-slot-crafted-option-id',
    ) ?? ''),
    resolvedCraftedOptionId: String(await readSemanticValue(
      workbench,
      'resolved-slot-crafted-option-id',
    ) ?? ''),
    resolveState: String(await readSemanticValue(workbench, 'gear-resolve-state') ?? ''),
  }
}

async function applyCandidateAndResolve(miniProgram, page, systemInfo, slot) {
  const before = await readSlotState(page, slot)
  const slotSelector = `.wx-data-role-gear-slot-row.wx-data-slot-key-${normalizeSelectorMarker(slot)}`
  await tapPageElement(
    miniProgram,
    page,
    systemInfo,
    before.row,
    `open ${slot} for apply`,
    () => requiredElement(page, slotSelector),
  )
  await requiredElement(page, '.wx-data-owner-gear-candidate-editor-sheet')
  const rows = await poll(
    () => timeout(page.$$('.wx-data-role-gear-candidate-row'), 3000, 'query apply candidates'),
    (items) => items.length > 0,
    operationTimeoutMs,
    'wait for apply candidates',
  )
  const candidates = await Promise.all(rows.map(async (row) => ({
    row,
    itemId: String(await readSemanticValue(row, 'candidate-item-id') ?? ''),
    state: String(await readSemanticValue(row, 'state') ?? ''),
  })))
  const candidate = candidates.find((item) => (
    item.itemId
    && item.itemId !== before.committedItemId
    && item.itemId !== before.resolvedItemId
    && item.state !== 'blocked'
  )) ?? candidates.find((item) => item.itemId && item.state !== 'blocked')
  if (!candidate) throw new Error(`${slot} has no resolver-eligible candidate`)
  await timeout(candidate.row.tap(), 3000, `select apply candidate ${candidate.itemId}`)
  await requiredElement(page, '.wx-data-role-gear-candidate-detail')
  const variants = await queryElementsByXpathSequentially(page, variantXpath, maximumVariantsPerItem)
  const variantRows = await Promise.all(variants.map(async (element) => ({
    element,
    variantKey: String(await readSemanticValue(element, 'variant-key') ?? ''),
    state: String(await readSemanticValue(element, 'state') ?? ''),
  })))
  const variant = variantRows.find((item) => item.variantKey && (item.state === 'ready' || item.state === 'partial'))
  if (variant) {
    await timeout(variant.element.tap(), 3000, `select apply variant ${variant.variantKey}`)
    await settle()
  }
  const craftedOptionRows = await timeout(
    page.$$('.wx-data-role-gear-crafted-stat-option'),
    3000,
    `query apply crafted options ${candidate.itemId}`,
  )
  const craftedOptions = await Promise.all(craftedOptionRows.map(async (element) => ({
    element,
    optionId: String(await readSemanticValue(element, 'crafted-option-id') ?? ''),
    state: String(await readSemanticValue(element, 'state') ?? ''),
  })))
  const craftedOption = craftedOptions.find((item) => item.optionId && item.state === 'ready')
  if (craftedOptions.length > 0 && !craftedOption) {
    throw new Error(`candidate ${candidate.itemId} has no ready crafted stat option`)
  }
  if (craftedOption) {
    await timeout(
      craftedOption.element.tap(),
      3000,
      `select apply crafted option ${craftedOption.optionId}`,
    )
    await settle()
  }
  const detail = await requiredElement(page, '.wx-data-role-gear-candidate-detail')
  const candidateVariantKey = String(await readSemanticValue(detail, 'candidate-draft-variant-key') ?? '')
  if (!candidateVariantKey) throw new Error(`candidate ${candidate.itemId} is missing draft variant identity`)
  const apply = await waitForEnabledElement(
    page,
    '.wx-data-action-id-gear-candidate-apply',
    `${slot}/${candidate.itemId} candidate apply`,
    resolveTimeoutMs,
  )
  await timeout(apply.tap(), 3000, 'apply candidate')
  let sawResolving = false
  const after = await poll(
    async () => {
      const state = await readSlotState(page, slot)
      sawResolving = state.resolveState === 'resolving' || sawResolving
      return state
    },
    (state) => gearApplyEvidenceMatches({
        candidateItemId: candidate.itemId,
        candidateVariantKey,
        committedBefore: before.committedItemId,
        committedVariantBefore: before.committedVariantKey,
        resolvedBefore: before.resolvedItemId,
        resolvedVariantBefore: before.resolvedVariantKey,
        committedAfter: state.committedItemId,
        committedVariantAfter: state.committedVariantKey,
        resolvedAfter: state.resolvedItemId,
        resolvedVariantAfter: state.resolvedVariantKey,
        resolveState: state.resolveState,
        sawResolving,
      }),
    resolveTimeoutMs,
    `resolve ${slot}/${candidate.itemId}`,
  )
  return {
    status: 'PASS',
    slot,
    itemId: candidate.itemId,
    variantKey: candidateVariantKey,
    resolveState: after.resolveState,
  }
}

async function applyCraftedCandidateAndResolve(miniProgram, page, systemInfo, target) {
  const {
    slot,
    itemId,
    variantKey,
    craftedOptionId,
  } = target
  const before = await readSlotState(page, slot)
  await tapPageElement(
    miniProgram,
    page,
    systemInfo,
    before.row,
    `open ${slot} for crafted apply`,
    () => requiredElement(
      page,
      `.wx-data-role-gear-slot-row.wx-data-slot-key-${normalizeSelectorMarker(slot)}`,
    ),
  )
  await requiredElement(page, '.wx-data-owner-gear-candidate-editor-sheet')
  const candidate = await requiredElement(
    page,
    `.wx-data-role-gear-candidate-row.wx-data-candidate-item-id-${normalizeSelectorMarker(itemId)}`,
  )
  const candidateSelector = `.wx-data-role-gear-candidate-row.wx-data-candidate-item-id-${normalizeSelectorMarker(itemId)}`
  await tapGearEditorElement(
    page,
    candidate,
    `select crafted candidate ${itemId}`,
    () => requiredElement(page, candidateSelector),
  )
  const variant = await poll(
    () => findElementBySemanticValue(
      page,
      variantXpath,
      maximumVariantsPerItem,
      'variant-key',
      normalizeSelectorMarker(variantKey),
    ),
    Boolean,
    operationTimeoutMs,
    `rendered crafted variant ${itemId}/${variantKey}`,
  )
  const variantState = String(await readSemanticValue(variant, 'state') ?? '')
  if (variantState !== 'ready' && variantState !== 'partial') {
    throw new Error(
      `crafted candidate ${itemId}/${variantKey} is not selectable: ${variantState}`,
    )
  }
  await tapGearEditorElement(
    page,
    variant,
    `select crafted variant ${variantKey}`,
    () => poll(
      () => findElementBySemanticValue(
        page,
        variantXpath,
        maximumVariantsPerItem,
        'variant-key',
        normalizeSelectorMarker(variantKey),
      ),
      Boolean,
      operationTimeoutMs,
      `requery crafted variant ${itemId}/${variantKey}`,
    ),
  )
  const options = await poll(
    () => timeout(
      page.$$('.wx-data-role-gear-crafted-stat-option'),
      3000,
      `query crafted options for ${itemId}/${variantKey}`,
    ),
    (items) => items.length > 0,
    operationTimeoutMs,
    `wait for crafted options ${itemId}/${variantKey}`,
  )
  const optionRows = await Promise.all(options.map(async (element) => ({
    element,
    optionId: String(await readSemanticValue(
      element,
      'crafted-option-id',
    ) ?? ''),
    state: String(await readSemanticValue(element, 'state') ?? ''),
  })))
  const option = optionRows.find((item) => item.optionId === craftedOptionId)
  if (!option || option.state !== 'ready') {
    throw new Error(
      `crafted option ${craftedOptionId} is not ready for ${itemId}/${variantKey}`,
    )
  }
  await tapGearEditorElement(
    page,
    option.element,
    `select crafted option ${craftedOptionId}`,
    async () => {
      const rendered = await timeout(
        page.$$('.wx-data-role-gear-crafted-stat-option'),
        3000,
        `requery crafted options for ${itemId}/${variantKey}`,
      )
      for (const element of rendered) {
        if (String(await readSemanticValue(element, 'crafted-option-id') ?? '') === craftedOptionId) {
          return element
        }
      }
      throw new Error(`crafted option ${craftedOptionId} disappeared after scroll`)
    },
  )
  const detail = await poll(
    async () => {
      const element = await requiredElement(
        page,
        '.wx-data-role-gear-candidate-detail',
      )
      return {
        element,
        itemId: String(await readSemanticValue(
          element,
          'candidate-draft-item-id',
        ) ?? ''),
        variantKey: String(await readSemanticValue(
          element,
          'candidate-draft-variant-key',
        ) ?? ''),
        craftedOptionId: String(await readSemanticValue(
          element,
          'candidate-draft-crafted-option-id',
        ) ?? ''),
      }
    },
    (value) => (
      value.itemId === itemId
      && value.variantKey === variantKey
      && value.craftedOptionId === craftedOptionId
    ),
    operationTimeoutMs,
    `wait for crafted draft identity ${itemId}/${variantKey}/${craftedOptionId}`,
  )
  if (!detail.element) throw new Error('crafted candidate detail disappeared')
  const apply = await waitForEnabledElement(
    page,
    '.wx-data-action-id-gear-candidate-apply',
    `${slot}/${itemId} crafted candidate apply`,
    resolveTimeoutMs,
  )
  await timeout(apply.tap(), 3000, 'apply crafted candidate')
  let sawResolving = false
  const after = await poll(
    async () => {
      const state = await readSlotState(page, slot)
      sawResolving = state.resolveState === 'resolving' || sawResolving
      return state
    },
    (state) => (
      gearApplyEvidenceMatches({
        candidateItemId: itemId,
        candidateVariantKey: variantKey,
        committedBefore: before.committedItemId,
        committedVariantBefore: before.committedVariantKey,
        resolvedBefore: before.resolvedItemId,
        resolvedVariantBefore: before.resolvedVariantKey,
        committedAfter: state.committedItemId,
        committedVariantAfter: state.committedVariantKey,
        resolvedAfter: state.resolvedItemId,
        resolvedVariantAfter: state.resolvedVariantKey,
        resolveState: state.resolveState,
        sawResolving,
      })
      && state.committedCraftedOptionId === craftedOptionId
      && state.resolvedCraftedOptionId === craftedOptionId
    ),
    resolveTimeoutMs,
    `resolve crafted ${slot}/${itemId}/${craftedOptionId}`,
  )
  return {
    status: 'PASS',
    slot,
    itemId,
    variantKey,
    craftedOptionId,
    committedCraftedOptionId: after.committedCraftedOptionId,
    resolvedCraftedOptionId: after.resolvedCraftedOptionId,
    resolveState: after.resolveState,
  }
}

async function storageValue(miniProgram) {
  return timeout(
    miniProgram.callWxMethod('getStorageSync', templateStorageKey),
    5000,
    `read ${templateStorageKey}`,
  )
}

async function restoreStorage(miniProgram, value) {
  if (value === undefined || value === null || value === '') {
    await timeout(miniProgram.callWxMethod('removeStorageSync', templateStorageKey), 5000, `remove ${templateStorageKey}`)
  } else {
    await timeout(miniProgram.callWxMethod('setStorageSync', templateStorageKey, value), 5000, `restore ${templateStorageKey}`)
  }
}

async function committedGear(page) {
  const rows = await timeout(page.$$('.wx-data-role-gear-slot-row'), 3000, 'query committed gear')
  const entries = await Promise.all(rows.map(async (row) => ({
    slot: String(await readSemanticValue(row, 'slot-key') ?? ''),
    itemId: String(await readSemanticValue(row, 'committed-item-id') ?? ''),
    hasCommittedItem: String(
      await readSemanticValue(row, 'has-committed-item') ?? '',
    ),
  })))
  return normalizeCommittedGearEntries(entries)
}

async function importCommunityExact(page) {
  await timeout((await requiredElement(page, '.wx-data-action-id-import')).tap(), 3000, 'open gear import')
  await requiredElement(page, '.wx-data-role-gear-template-import-sheet')
  const tabs = await queryElementsByXpathSequentially(page, templateTabXpath, 2)
  if (tabs.length !== 2) throw new Error(`expected two gear import tabs, received ${tabs.length}`)
  await timeout(tabs[1].tap(), 3000, 'open community gear templates')
  const imports = await poll(
    () => timeout(page.$$('.wx-style-templatesheetcommunityimport'), 3000, 'query community imports'),
    (items) => items.length > 0,
    operationTimeoutMs,
    'wait for community gear templates',
  )
  const available = []
  for (const element of imports) {
    const disabled = String(await readSemanticValue(element, 'disabled') ?? 'false')
    if (disabled !== 'true') available.push(element)
  }
  if (!available.length) throw new Error('community gear templates are present but none are importable')
  await timeout(available[0].tap(), 3000, 'import first community Exact template')
  await waitForMissing(page, '.wx-data-role-gear-template-import-sheet', resolveTimeoutMs)
  const gear = await poll(
    () => committedGear(page),
    (items) => Object.keys(items).length >= 15,
    resolveTimeoutMs,
    'wait for imported Exact gear',
  )
  const workbench = await requiredElement(page, '.wx-data-owner-gear-slot-workbench')
  const resolvedItemId = String(await readSemanticValue(workbench, 'resolved-slot-item-id') ?? '')
  const resolvedVariantKey = String(await readSemanticValue(workbench, 'resolved-slot-variant-key') ?? '')
  const resolveState = String(await readSemanticValue(workbench, 'gear-resolve-state') ?? '')
  if (!resolvedItemId || !resolvedVariantKey || resolveState !== 'verified') {
    throw new Error(`community Exact import lacks verified resolved identity: item=${resolvedItemId} variant=${resolvedVariantKey} state=${resolveState}`)
  }
  return {
    status: 'PASS',
    importedSlots: Object.keys(gear).length,
    selectedResolvedItemId: resolvedItemId,
    selectedResolvedVariantKey: resolvedVariantKey,
    gear,
  }
}

async function chooseEnhancementOption(page, kind) {
  const role = kind === 'socket' ? 'gear-enhancement-socket' : 'gear-enhancement-option'
  let elements = await timeout(page.$$(`.wx-data-role-${role}`), 3000, `query ${kind} options`)
  if (!elements.length) {
    elements = await queryElementsByXpathSequentially(
      page,
      `//*[contains(concat(" ", normalize-space(@class), " "), " wx-data-role-${role} ")]`,
      64,
    )
  }
  for (const element of elements) {
    const optionId = String(await readSemanticValue(element, 'option-id') ?? '')
    const active = String(await readSemanticValue(element, 'active') ?? 'false')
    if (optionId && active !== 'true') return { element, optionId }
  }
  return null
}

async function enhancementEditorDiagnostic(page, kind) {
  const [editor] = await queryElementsByXpathSequentially(
    page,
    '//*[contains(concat(" ", normalize-space(@class), " "), " wx-data-owner-gear-enhancement-editor-sheet ")]',
    1,
  )
  const blockers = await queryElementsByXpathSequentially(
    page,
    '//*[contains(concat(" ", normalize-space(@class), " "), " wx-data-role-gear-enhancement-blockers ")]',
    8,
  )
  const compatibleSlots = await queryElementsByXpathSequentially(
    page,
    '//*[contains(concat(" ", normalize-space(@class), " "), " wx-data-role-gear-enhancement-compatible-slot ")]',
    32,
  )
  const role = kind === 'socket' ? 'gear-enhancement-socket' : 'gear-enhancement-option'
  const options = await queryElementsByXpathSequentially(
    page,
    `//*[contains(concat(" ", normalize-space(@class), " "), " wx-data-role-${role} ")]`,
    64,
  )
  const editorClass = String(await timeout(
    editor.attribute('class'),
    1500,
    `read ${kind} enhancement editor class`,
  ) ?? '')
  const pageTree = JSON.stringify(await timeout(page.data(), 2500, `read ${kind} page tree`))
  const editorMarkerIndex = pageTree.indexOf('wx-data-owner-gear-enhancement-editor-sheet')
  return {
    activeSlot: String(await readSemanticValue(editor, 'active-slot') ?? ''),
    requestedKind: String(await readSemanticValue(editor, 'requested-kind') ?? ''),
    hasItem: String(await readSemanticValue(editor, 'has-item') ?? ''),
    socketCount: String(await readSemanticValue(editor, 'socket-count') ?? ''),
    semanticOptionCount: String(await readSemanticValue(editor, 'option-count') ?? ''),
    blockerCount: String(await readSemanticValue(editor, 'blocker-count') ?? ''),
    editorClass: editorClass.slice(0, 1000),
    editorTreeSnippet: editorMarkerIndex >= 0
      ? pageTree.slice(Math.max(0, editorMarkerIndex - 600), editorMarkerIndex + 1000)
      : '',
    blockerText: (await Promise.all(blockers.map((element) => element.text())))
      .map(String)
      .join(' | ')
      .slice(0, 240),
    compatibleSlotCount: compatibleSlots.length,
    optionCount: options.length,
  }
}

async function waitForEnhancementEditorReady(page, kind) {
  const confirm = await requiredElement(page, '.wx-data-action-id-gear-enhancement-confirm')
  await poll(
    () => timeout(confirm.text(), 2500, `read ${kind} confirm state`),
    (text) => String(text).includes('确认强化'),
    operationTimeoutMs,
    `wait for ${kind} enhancement hydration`,
  )
}

async function editEnhancementAndResolve(page, preferredKind) {
  const order = [preferredKind, ...['socket', 'enchant', 'embellishment'].filter((item) => item !== preferredKind)]
  const diagnostics = []
  const unavailableBeforeApply = []
  for (const kind of order) {
    const open = await timeout(page.$(`.wx-data-action-id-open-${kind}`), 2500, `query open ${kind}`)
    if (!open) {
      unavailableBeforeApply.push({ kind, reason: 'control_missing' })
      continue
    }
    if (await buttonDisabled(open, `${kind} enhancement control disabled`)) {
      unavailableBeforeApply.push({ kind, reason: 'control_disabled' })
      continue
    }
    try {
      await timeout(open.tap(), 3000, `open ${kind}`)
      await requiredElement(page, '.wx-data-owner-gear-enhancement-editor-sheet')
      await waitForEnhancementEditorReady(page, kind)
      const option = await chooseEnhancementOption(page, kind)
      if (!option) {
        diagnostics.push({ kind, ...(await enhancementEditorDiagnostic(page, kind)) })
        await timeout((await requiredElement(page, '.wx-data-action-id-gear-enhancement-cancel')).tap(), 3000, `cancel ${kind}`)
        await waitForMissing(page, '.wx-data-owner-gear-enhancement-editor-sheet')
        throw new Error(`${kind} enhancement control was enabled without a selectable option`)
      }
      await timeout(option.element.tap(), 3000, `select ${kind}/${option.optionId}`)
      await poll(
        async () => String(await readSemanticValue(
          option.element,
          'active',
          `${kind}/${option.optionId} active state`,
        ) ?? 'false'),
        (active) => active === 'true',
        operationTimeoutMs,
        `wait for ${kind} enhancement option ${option.optionId} active`,
      )
      const confirm = await waitForEnabledElement(
        page,
        '.wx-data-action-id-gear-enhancement-confirm',
        `${kind} enhancement confirm`,
      )
      await timeout(confirm.tap(), 3000, `confirm ${kind}`)
      await requiredElement(page, '.wx-data-gear-resolve-state-resolving')
      const outcome = await poll(
        async () => {
          const editor = await timeout(
            page.$('.wx-data-owner-gear-enhancement-editor-sheet'),
            1500,
            `query ${kind} enhancement editor outcome`,
          )
          const workbench = await requiredElement(page, '.wx-data-owner-gear-slot-workbench')
          const resolveState = String(await readSemanticValue(
            workbench,
            'gear-resolve-state',
          ) ?? '')
          const notice = await timeout(
            page.$('.wx-data-role-gear-editor-notice'),
            1500,
            `query ${kind} enhancement outcome notice`,
          )
          return {
            editorPresent: Boolean(editor),
            resolveState,
            notice: notice ? String(await timeout(notice.text(), 1500, `read ${kind} enhancement outcome notice`)) : '',
          }
        },
        (value) => !value.editorPresent || value.resolveState === 'error' || value.resolveState === 'stale',
        resolveTimeoutMs,
        `wait for ${kind} enhancement commit outcome`,
      )
      if (outcome.editorPresent) {
        throw new Error(
          `${kind} enhancement resolve state=${outcome.resolveState}; notice=${outcome.notice || 'none'}`,
        )
      }
      const resolveState = await poll(
        async () => String(await readSemanticValue(
          await requiredElement(page, '.wx-data-owner-gear-slot-workbench'),
          'gear-resolve-state',
        ) ?? ''),
        (state) => state === 'verified' || state === 'error' || state === 'stale',
        resolveTimeoutMs,
        `resolve ${kind} enhancement`,
      )
      if (resolveState !== 'verified') throw new Error(`${kind} enhancement resolve state=${resolveState}`)
      const confirmed = await timeout(page.$$(`.wx-data-enhancement-kind-${kind}.wx-data-state-confirmed`), 3000, `query confirmed ${kind}`)
      if (!confirmed.length) throw new Error(`${kind} enhancement did not publish a confirmed slot marker`)
      return {
        status: 'PASS',
        preferredKind,
        requestedKind: kind,
        appliedKind: kind,
        fallbackUsed: kind !== preferredKind,
        unavailableBeforeApply,
        optionId: option.optionId,
        resolveState,
      }
    } catch (error) {
      diagnostics.push({
        kind,
        error: error instanceof Error ? error.message : String(error),
        ...(await enhancementEditorDiagnostic(page, kind).catch(() => ({}))),
      })
      const editor = await timeout(page.$('.wx-data-owner-gear-enhancement-editor-sheet'), 1500, 'query enhancement editor after error')
      if (editor) {
        const cancel = await timeout(page.$('.wx-data-action-id-gear-enhancement-cancel'), 1500, 'query enhancement cancel')
        if (cancel) await timeout(cancel.tap(), 3000, 'cancel failed enhancement draft')
      }
      throw new Error(`${kind} enhancement failed; diagnostics=${JSON.stringify(diagnostics)}`)
    }
  }
  throw new Error(`no compatible enhancement option across socket/enchant/embellishment; diagnostics=${JSON.stringify(diagnostics)}`)
}

async function saveReloadRecovery(miniProgram, page, spec, expectedGear, expectedEnhancementKind) {
  const beforeStorage = await storageValue(miniProgram)
  await timeout((await requiredElement(page, '.wx-data-action-id-save')).tap(), 3000, 'save gear template')
  await poll(
    () => storageValue(miniProgram),
    (value) => storageValueChanged(beforeStorage, value),
    resolveTimeoutMs,
    `save ${spec.specId} gear template`,
  )
  await timeout((await requiredElement(page, '.wx-data-action-id-reset')).tap(), 3000, 'reset gear')
  await poll(
    () => committedGear(page),
    (items) => Object.keys(items).length === 0,
    operationTimeoutMs,
    'wait for reset gear',
  )
  await timeout((await requiredElement(page, '.wx-data-action-id-import')).tap(), 3000, 'open saved gear templates')
  await requiredElement(page, '.wx-data-role-gear-template-import-sheet')
  const items = await poll(
    () => timeout(page.$$('.wx-style-templatesheetitem'), 3000, 'query saved template rows'),
    (rows) => rows.length > 0,
    operationTimeoutMs,
    'wait for saved gear templates',
  )
  let targetImport = null
  for (const item of items) {
    const text = String(await timeout(item.text(), 2500, 'read saved template text') ?? '')
    if (!text.includes(spec.specName)) continue
    targetImport = await timeout(item.$('.wx-style-templatesheetimport'), 2500, 'query saved template import')
    if (targetImport) break
  }
  if (!targetImport) throw new Error(`saved gear template for ${spec.specId} was not rendered`)
  await timeout(targetImport.tap(), 3000, `reload saved template ${spec.specId}`)
  await waitForMissing(page, '.wx-data-role-gear-template-import-sheet', resolveTimeoutMs)
  const reloaded = await poll(
    () => committedGear(page),
    (gear) => JSON.stringify(gear) === JSON.stringify(expectedGear),
    resolveTimeoutMs,
    `reload exact saved gear ${spec.specId}`,
  )
  const confirmed = await timeout(
    page.$$(`.wx-data-enhancement-kind-${expectedEnhancementKind}.wx-data-state-confirmed`),
    3000,
    `query reloaded ${expectedEnhancementKind}`,
  )
  if (!confirmed.length) throw new Error(`reloaded template lost confirmed ${expectedEnhancementKind}`)
  return {
    status: 'PASS',
    reloadedSlots: Object.keys(reloaded).length,
    enhancementKind: expectedEnhancementKind,
  }
}

async function verifyRouteIdentity(page, spec) {
  const classText = String(await timeout(
    (await requiredElement(page, '.wx-data-role-gear-profession-field')).text(),
    3000,
    'read rendered class',
  ))
  const specText = String(await timeout(
    (await requiredElement(page, '.wx-data-role-gear-specialization-field')).text(),
    3000,
    'read rendered spec',
  ))
  if (!classText.includes(spec.className) || !specText.includes(spec.specName)) {
    throw new Error(`rendered route identity mismatch: expected=${spec.className}/${spec.specName} actual=${classText}/${specText}`)
  }
}

async function verifyRuntimeBuildIdentity(page, build) {
  const pageFrame = await requiredElement(page, '.wx-data-region-page_frame')
  return assertRuntimeBuildIdentity({
    gitHead: await readSemanticValue(pageFrame, 'weapp-runtime-git-head'),
    sourceHash: await readSemanticValue(pageFrame, 'weapp-runtime-source-hash'),
  }, build)
}

async function verifySimcRouteSemantics(page, spec, expectedUnsupported) {
  const region = await requiredElement(page, '.wx-data-region-submission_action')
  const specializationId = String(await readSemanticValue(region, 'simc-specialization-id') ?? '')
  const specializationSupported = String(await readSemanticValue(region, 'simc-specialization-supported') ?? '')
  const blockerCode = String(await readSemanticValue(region, 'simc-specialization-blocker-code') ?? '')
  const optionsState = String(await readSemanticValue(region, 'simc-options-state') ?? '')
  const expectedSpecializationId = `${spec.classKey}:${spec.specKey}`
  if (normalizeSelectorMarker(specializationId) !== normalizeSelectorMarker(expectedSpecializationId)) {
    throw new Error(
      `SimC specialization identity mismatch: expected=${expectedSpecializationId} actual=${specializationId}`,
    )
  }
  if (normalizeSelectorMarker(specializationSupported) !== String(!expectedUnsupported)) {
    throw new Error(
      `SimC specialization support mismatch: expected=${!expectedUnsupported} actual=${specializationSupported}`,
    )
  }
  if (
    expectedUnsupported
    && normalizeSelectorMarker(blockerCode) !== normalizeSelectorMarker('SIMC_SPECIALIZATION_UNSUPPORTED')
  ) {
    throw new Error(`SimC unsupported specialization lost backend blocker code: ${blockerCode}`)
  }
  if (optionsState !== (expectedUnsupported ? 'blocked' : 'ready')) {
    throw new Error(
      `SimC options state mismatch for ${expectedSpecializationId}: expected=${expectedUnsupported ? 'blocked' : 'ready'} actual=${optionsState}`,
    )
  }
  return {
    specializationId: expectedSpecializationId,
    specializationSupported: !expectedUnsupported,
    blockerCode: expectedUnsupported ? 'SIMC_SPECIALIZATION_UNSUPPORTED' : 'none',
    optionsState,
  }
}

async function buttonDisabled(element, label) {
  const semantic = String(await readSemanticValue(element, 'disabled', label) ?? '')
  if (semantic === 'true') return true
  const native = String(await timeout(
    element.attribute('disabled'),
    2500,
    `read ${label} native disabled`,
  ) ?? '')
  return native === 'true'
}

async function waitForEnabledElement(page, selector, label, timeoutMs = operationTimeoutMs) {
  return poll(
    async () => {
      const element = await timeout(page.$(selector), 2500, `query ${label}`)
      if (!element) return null
      return await buttonDisabled(element, `${label} disabled`) ? null : element
    },
    Boolean,
    timeoutMs,
    `wait for enabled ${label}`,
  )
}

async function verifyTalentRouteIdentity(page, spec) {
  const values = await timeout(
    page.$$('.wx-data-role-talent-selector-value'),
    3000,
    `query ${spec.specId} talent selectors`,
  )
  const rendered = (await Promise.all(values.map((value) => value.text())))
    .map((value) => String(value ?? '').trim())
    .filter(Boolean)
  if (
    !rendered.some((value) => value.includes(spec.className))
    || !rendered.some((value) => value.includes(spec.specName))
  ) {
    throw new Error(
      `${spec.specId} talent route identity mismatch: rendered=${rendered.join(' | ')}`,
    )
  }
  return {
    className: spec.className,
    specName: spec.specName,
    renderedSelectors: rendered,
  }
}

async function prepareTalentTemplateForSimc(
  miniProgram,
  spec,
  simcPolicy,
  diagnosticActionOnly,
) {
  if (diagnosticActionOnly) return { status: 'SKIP_DIAGNOSTIC_ONLY' }
  const specializationId = `${spec.classKey}:${spec.specKey}`
  if (simcPolicy.unsupportedSpecializations.has(specializationId)) {
    return {
      status: 'PASS',
      mode: 'policy_not_required',
      specializationUnsupported: true,
      specializationId,
    }
  }

  const route = `/pages/builds/talent-simulator?spec=${encodeURIComponent(spec.specId)}`
  const page = await openRoute(miniProgram, route)
  const routeIdentity = await verifyTalentRouteIdentity(page, spec)
  const importAction = await waitForEnabledElement(
    page,
    '.wx-data-action-id-import',
    `${specializationId} talent import`,
  )
  await timeout(importAction.tap(), 3000, `open ${specializationId} talent import`)
  await requiredElement(page, '.wx-data-role-talent-template-import-sheet')

  const tabs = await queryElementsByXpathSequentially(page, templateTabXpath, 2)
  if (tabs.length !== 2) {
    throw new Error(`expected two talent import tabs for ${specializationId}, received ${tabs.length}`)
  }
  await timeout(tabs[1].tap(), 3000, `open ${specializationId} community talent templates`)
  const communityImport = await waitForEnabledElement(
    page,
    '.wx-style-templatesheetcommunityimport',
    `${specializationId} community talent import`,
  )
  await timeout(
    communityImport.tap(),
    3000,
    `import ${specializationId} community talent template`,
  )
  await waitForMissing(
    page,
    '.wx-data-role-talent-template-import-sheet',
    resolveTimeoutMs,
  )

  const saveAction = await waitForEnabledElement(
    page,
    '.wx-data-action-id-save',
    `${specializationId} talent save`,
    resolveTimeoutMs,
  )
  await timeout(saveAction.tap(), 3000, `open ${specializationId} talent name sheet`)
  await requiredElement(page, '.wx-data-role-talent-template-name-sheet')
  const confirmSave = await waitForEnabledElement(
    page,
    '.wx-style-templatenamesheetconfirm',
    `${specializationId} talent save confirmation`,
  )
  await timeout(confirmSave.tap(), 3000, `save ${specializationId} talent template`)
  await waitForMissing(
    page,
    '.wx-data-role-talent-template-name-sheet',
    resolveTimeoutMs,
  )

  const verifyImportAction = await waitForEnabledElement(
    page,
    '.wx-data-action-id-import',
    `${specializationId} saved talent verification`,
  )
  await timeout(
    verifyImportAction.tap(),
    3000,
    `reopen ${specializationId} saved talent templates`,
  )
  await requiredElement(page, '.wx-data-role-talent-template-import-sheet')
  const persisted = await poll(
    async () => {
      const rows = await timeout(
        page.$$('.wx-style-templatesheetitem'),
        3000,
        `query ${specializationId} saved talent templates`,
      )
      return Promise.all(rows.map(async (row) => String(await row.text() ?? '').trim()))
    },
    (titles) => titles.some(
      (title) => title.includes(spec.className) && title.includes(spec.specName),
    ),
    resolveTimeoutMs,
    `verify ${specializationId} saved talent template through UI`,
  )
  const persistedTitle = persisted.find(
    (title) => title.includes(spec.className) && title.includes(spec.specName),
  )

  return {
    status: 'PASS',
    mode: 'prepared',
    specializationId,
    routeIdentity,
    communityImported: true,
    templatePersisted: true,
    persistedTitle,
  }
}

async function verifyUnsupportedSimc(miniProgram, spec) {
  const beforePage = await openTaskList(miniProgram)
  const taskIdsBefore = await visibleTaskIds(beforePage)
  const route = `/pages/simulator/simc?classKey=${encodeURIComponent(spec.classKey)}&specKey=${encodeURIComponent(spec.specKey)}&spec=${encodeURIComponent(spec.specId)}`
  const page = await openRoute(miniProgram, route)
  const semantics = await verifySimcRouteSemantics(page, spec, true)
  const blockerPanel = await requiredElement(page, '.wx-data-owner-simc-blocker-panel')
  if (String(await readSemanticValue(blockerPanel, 'state') ?? '') !== 'blocked') {
    throw new Error(`${semantics.specializationId} blocker panel did not fail closed`)
  }
  await requiredElement(page, '.wx-data-blocker-id-identity.wx-data-state-blocked')
  const confirm = await requiredElement(page, '.wx-data-action-id-confirm')
  const submit = await requiredElement(page, '.wx-data-action-id-submit')
  if (!await buttonDisabled(confirm, 'unsupported confirm disabled')) {
    throw new Error(`${semantics.specializationId} confirm action remained enabled`)
  }
  if (!await buttonDisabled(submit, 'unsupported submit disabled')) {
    throw new Error(`${semantics.specializationId} submit action remained enabled`)
  }
  const afterPage = await openTaskList(miniProgram)
  const taskIdsAfter = await visibleTaskIds(afterPage)
  assertSameTaskIds(taskIdsBefore, taskIdsAfter, semantics.specializationId)
  return {
    status: 'PASS',
    mode: 'policy_blocked',
    ...semantics,
    taskCreated: false,
    taskCountBefore: taskIdsBefore.length,
    taskCountAfter: taskIdsAfter.length,
  }
}

async function waitForSimcConfirmation(page, spec) {
  return poll(
    async () => {
      const actionBar = await requiredElement(page, '.wx-data-owner-simc-submission-action-bar')
      const submit = await requiredElement(page, '.wx-data-action-id-submit')
      const detail = await requiredElement(page, '.wx-data-role-simc-validation-detail')
      return {
        state: String(await readSemanticValue(actionBar, 'state') ?? ''),
        disabled: await buttonDisabled(submit, 'SimC submit disabled'),
        detail: String(await timeout(detail.text(), 2500, 'read SimC validation detail') ?? ''),
      }
    },
    (value) => value.state === 'ready' && value.disabled === false,
    simcConfirmTimeoutMs,
    `confirm SimC combination ${spec.classKey}:${spec.specKey}`,
  )
}

async function waitForTaskDetailTerminal(miniProgram, taskId) {
  const page = await waitForCurrentPage(miniProgram, 'pages/simulator/task-detail')
  const deadline = Date.now() + simcTaskTimeoutMs
  let lastState = 'loading'
  while (Date.now() < deadline) {
    const result = await requiredElement(page, '.wx-data-owner-task-simc-result')
    lastState = String(await readSemanticValue(result, 'state') ?? '')
    if (['completed', 'failed', 'unsupported', 'blocked'].includes(lastState)) {
      const summary = await requiredElement(page, '.wx-data-owner-task-detail-summary')
      const summaryState = String(await readSemanticValue(summary, 'state') ?? '')
      const attributes = await requiredElement(page, '.wx-data-owner-task-attribute-snapshot')
      const attributeState = String(await readSemanticValue(attributes, 'state') ?? '')
      const metric = await requiredElement(page, '.wx-data-role-result-value')
      const metricValue = String(await timeout(metric.text(), 2500, 'read SimC result value') ?? '').trim()
      if (lastState !== 'completed' || summaryState !== 'completed') {
        throw new Error(`SimC task ${taskId} terminated as result=${lastState} summary=${summaryState}`)
      }
      if (attributeState !== 'verified') {
        throw new Error(`SimC task ${taskId} lost verified attribute snapshot: ${attributeState}`)
      }
      if (!metricValue || metricValue === '未返回') {
        throw new Error(`SimC task ${taskId} completed without a formal metric value`)
      }
      return {
        terminalResult: lastState,
        summaryState,
        attributeState,
        metricValue,
      }
    }
    const refresh = await requiredElement(page, '.wx-data-action-id-refresh-task')
    if (!await buttonDisabled(refresh, 'task refresh disabled')) {
      await timeout(refresh.tap(), 3000, `refresh SimC task ${taskId}`)
    }
    await settle(1250)
  }
  throw new Error(`SimC task ${taskId} did not reach a terminal state after ${simcTaskTimeoutMs}ms; lastState=${lastState}`)
}

async function verifySupportedSimc(miniProgram, spec) {
  const route = `/pages/simulator/simc?classKey=${encodeURIComponent(spec.classKey)}&specKey=${encodeURIComponent(spec.specKey)}&spec=${encodeURIComponent(spec.specId)}`
  const page = await openRoute(miniProgram, route)
  const semantics = await verifySimcRouteSemantics(page, spec, false)
  const confirm = await waitForEnabledElement(
    page,
    '.wx-data-action-id-confirm',
    `${semantics.specializationId} SimC confirm`,
    resolveTimeoutMs,
  )
  await timeout(confirm.tap(), 3000, `confirm ${semantics.specializationId}`)
  await waitForSimcConfirmation(page, spec)
  const submit = await requiredElement(page, '.wx-data-action-id-submit')
  await timeout(submit.tap(), 3000, `submit ${semantics.specializationId}`)
  const viewTask = await poll(
    () => timeout(page.$('.wx-data-action-id-view-task'), 2500, 'query view submitted task'),
    Boolean,
    operationTimeoutMs,
    `wait for ${semantics.specializationId} taskId`,
  )
  const validationDetail = await requiredElement(page, '.wx-data-role-simc-validation-detail')
  const taskId = String(await timeout(validationDetail.text(), 2500, 'read submitted taskId') ?? '').trim()
  if (!taskId) throw new Error(`${semantics.specializationId} submitted without a taskId`)
  await timeout(viewTask.tap(), 3000, `view SimC task ${taskId}`)
  const terminal = await waitForTaskDetailTerminal(miniProgram, taskId)
  const tasksPage = await openTaskList(miniProgram)
  const visible = await taskRow(tasksPage, taskId)
  if (!visible) throw new Error(`completed SimC task ${taskId} is absent from the owner-scoped WeChat task list`)
  const taskListState = String(await readSemanticValue(visible, 'state') ?? '')
  if (taskListState !== 'completed') {
    throw new Error(`completed SimC task ${taskId} is rendered in task list as ${taskListState}`)
  }
  return {
    status: 'PASS',
    mode: 'executed',
    ...semantics,
    taskId,
    ...terminal,
    taskListVisible: true,
    taskListState,
  }
}

async function simcExecutionOrPolicyBlock(
  miniProgram,
  spec,
  simcPolicy,
  diagnosticActionOnly,
  phase,
) {
  if (diagnosticActionOnly) return { status: 'SKIP_DIAGNOSTIC_ONLY' }
  const specializationId = `${spec.classKey}:${spec.specKey}`
  const expectedUnsupported = simcPolicy.unsupportedSpecializations.has(specializationId)
  if (phase === 'preview_catalog_actions' && !expectedUnsupported) {
    return {
      status: 'NOT_RUN_PREVIEW_TRUST_BOUNDARY',
      mode: 'preview_requires_formal_manifest',
      formalActiveManifestRequired: true,
    }
  }
  return expectedUnsupported
    ? verifyUnsupportedSimc(miniProgram, spec)
    : verifySupportedSimc(miniProgram, spec)
}

async function runSpec(
  miniProgram,
  systemInfo,
  apiBaseUrl,
  spec,
  stableIdentity,
  specIndex,
  build,
  simcPolicy,
  phase,
  slotShard,
  diagnosticActionOnly = false,
) {
  const route = `/pages/builds/detail?query=gear&spec=${encodeURIComponent(spec.specId)}`
  process.stderr.write(`[wechat-gear-matrix:spec:start] ${spec.classKey}/${spec.specKey}\n`)
  const page = await openRoute(miniProgram, route)
  const runtimeBuildIdentity = await verifyRuntimeBuildIdentity(page, build)
  await verifyRouteIdentity(page, spec)
  const rows = await timeout(page.$$('.wx-data-role-gear-slot-row'), 3000, 'query gear slots')
  const renderedSlots = await Promise.all(rows.map((row) => readSemanticValue(row, 'slot-key')))
  compareStringSets(gearSlots, renderedSlots.map(String), `${spec.specId} rendered slots`)

  const slots = []
  const slotsToInspect = slotShard ? [slotShard] : gearSlots
  if (!diagnosticActionOnly) {
    for (const slot of slotsToInspect) {
      slots.push(await inspectSlot(
        miniProgram,
        page,
        systemInfo,
        apiBaseUrl,
        spec,
        slot,
        stableIdentity,
      ))
    }
  }
  if (slotShard) {
    const result = {
      classKey: spec.classKey,
      className: spec.className,
      specId: spec.specId,
      specKey: spec.specKey,
      specName: spec.specName,
      status: 'SLOT_SHARD_PASS',
      runtimeBuildIdentity,
      slots,
      actions: Object.fromEntries(
        requiredActions.map((action) => [action, 'NOT_RUN_SLOT_SHARD']),
      ),
      actionEvidence: {},
    }
    process.stderr.write(`[wechat-gear-matrix:spec:end] ${spec.classKey}/${spec.specKey} SLOT_SHARD_PASS\n`)
    return result
  }
  if (phase === 'preview_catalog_only') {
    const result = {
      classKey: spec.classKey,
      className: spec.className,
      specId: spec.specId,
      specKey: spec.specKey,
      specName: spec.specName,
      status: 'CATALOG_ONLY_PASS',
      runtimeBuildIdentity,
      slots,
      actions: Object.fromEntries(
        requiredActions.map((action) => [action, 'NOT_RUN_CATALOG_ONLY']),
      ),
      actionEvidence: {},
    }
    process.stderr.write(`[wechat-gear-matrix:spec:end] ${spec.classKey}/${spec.specKey} CATALOG_ONLY_PASS\n`)
    return result
  }
  const applySlots = ['head', 'main_hand', 'trinket1']
  const applySelection = diagnosticActionOnly
    ? null
    : selectCandidateApplySlot(slots, applySlots[specIndex % applySlots.length])
  const candidateApplyResolve = diagnosticActionOnly
    ? { status: 'SKIP_DIAGNOSTIC_ONLY' }
    : {
        ...await applyCandidateAndResolve(
          miniProgram,
          page,
          systemInfo,
          applySelection.slot,
        ),
        preferredSlot: applySelection.preferredSlot,
        usedFallback: applySelection.usedFallback,
      }
  const craftedTargets = diagnosticActionOnly
    ? []
    : slots
        .flatMap((slot) => slot.craftedApplyTargets ?? [])
  if (!diagnosticActionOnly && craftedTargets.length === 0) {
    throw new Error(
      `${spec.classKey}/${spec.specKey} has no cross-item crafted stat apply target`,
    )
  }
  const craftedTargetSlots = [
    ...new Set(craftedTargets.map((target) => target.slot)),
  ]
  const craftedTargetCurrentBySlot = diagnosticActionOnly
    ? {}
    : Object.fromEntries(await Promise.all(
        craftedTargetSlots.map(async (slot) => [slot, await readSlotState(page, slot)]),
      ))
  const craftedTarget = diagnosticActionOnly
    ? null
    : selectCraftedApplyTarget(
        craftedTargets,
        craftedTargetCurrentBySlot,
        [candidateApplyResolve.itemId],
        specIndex,
      )
  const craftedStatApplyResolve = diagnosticActionOnly
    ? { status: 'SKIP_DIAGNOSTIC_ONLY' }
    : await applyCraftedCandidateAndResolve(
        miniProgram,
        page,
        systemInfo,
        craftedTarget,
      )
  const baselineStorage = await storageValue(miniProgram)
  try {
    const communityExactImport = await importCommunityExact(page)
    const preferredKind = ['socket', 'enchant', 'embellishment'][specIndex % 3]
    const enhancementEditResolve = await editEnhancementAndResolve(page, preferredKind)
    const gearAfterEnhancement = await committedGear(page)
    const saveReload = diagnosticActionOnly
      ? { status: 'SKIP_DIAGNOSTIC_ONLY' }
      : await saveReloadRecovery(
          miniProgram,
          page,
          spec,
          gearAfterEnhancement,
          enhancementEditResolve.appliedKind,
        )
    const talentTemplatePreparation = await prepareTalentTemplateForSimc(
      miniProgram,
      spec,
      simcPolicy,
      diagnosticActionOnly,
    )
    const simcEvidence = await simcExecutionOrPolicyBlock(
      miniProgram,
      spec,
      simcPolicy,
      diagnosticActionOnly,
      phase,
    )
    const resultStatus = phase === 'preview_catalog_actions' ? 'PREVIEW_PASS' : 'PASS'
    const result = {
      classKey: spec.classKey,
      className: spec.className,
      specId: spec.specId,
      specKey: spec.specKey,
      specName: spec.specName,
      status: resultStatus,
      runtimeBuildIdentity,
      slots,
      actions: {
        candidateApplyResolve: candidateApplyResolve.status,
        craftedStatApplyResolve: craftedStatApplyResolve.status,
        communityExactImport: communityExactImport.status,
        enhancementEditResolve: enhancementEditResolve.status,
        saveReloadRecovery: saveReload.status,
        talentTemplatePreparation: talentTemplatePreparation.status,
        simcExecutionOrPolicyBlock: simcEvidence.status,
      },
      actionEvidence: {
        candidateApplyResolve,
        craftedStatApplyResolve,
        communityExactImport: {
          ...communityExactImport,
          gear: undefined,
        },
        enhancementEditResolve,
        saveReloadRecovery: saveReload,
        talentTemplatePreparation,
        simcExecutionOrPolicyBlock: simcEvidence,
      },
    }
    process.stderr.write(`[wechat-gear-matrix:spec:end] ${spec.classKey}/${spec.specKey} ${resultStatus}\n`)
    return result
  } finally {
    await restoreStorage(miniProgram, baselineStorage)
  }
}

async function main() {
  const apiBaseUrl = requiredEnvironment('WECHAT_GEAR_MATRIX_API_BASE_URL')
  const classKey = requiredEnvironment('WECHAT_GEAR_MATRIX_CLASS')
  const outputPath = path.resolve(requiredEnvironment('WECHAT_GEAR_MATRIX_OUTPUT'))
  const buildMetadataPath = path.resolve(requiredEnvironment('WECHAT_GEAR_MATRIX_BUILD_METADATA'))
  const diagnosticActionOnly = process.env.WECHAT_GEAR_MATRIX_DIAGNOSTIC_ACTION_ONLY === '1'
  const slotShard = normalizeGearSlotShard(
    process.env.WECHAT_GEAR_MATRIX_SLOT_SHARD,
  )
  if (slotShard && diagnosticActionOnly) {
    throw new Error('slot shard and diagnostic action-only modes cannot be combined')
  }
  const requestedPhase = String(process.env.WECHAT_GEAR_MATRIX_PHASE || 'full').trim()
  if (
    requestedPhase !== 'full'
    && requestedPhase !== 'preview_catalog_actions'
    && requestedPhase !== 'preview_catalog_only'
  ) {
    throw new Error(`unsupported WECHAT_GEAR_MATRIX_PHASE ${requestedPhase}`)
  }
  const phase = slotShard
    ? 'preview_catalog_slot_shard'
    : requestedPhase
  const build = JSON.parse(fs.readFileSync(buildMetadataPath, 'utf8'))
  if (!build?.gitHead || !build?.sourceHash) throw new Error('WeChat build metadata lacks gitHead/sourceHash')
  const home = await fetchJson(new URL('/api/builds/home', apiBaseUrl), 'builds home')
  const matrix = normalizeSpecMatrix(home)
  const simcOptions = await fetchJson(
    new URL('/api/simulator/simc/options', apiBaseUrl),
    'SimC options',
  )
  const simcPolicy = normalizeSimcPolicy(simcOptions, matrix)
  const specs = matrix.filter((item) => item.classKey === classKey)
  if (!specs.length) throw new Error(`unknown WECHAT_GEAR_MATRIX_CLASS ${classKey}`)
  const firstPayload = await fetchJson(slotUrl(apiBaseUrl, specs[0], gearSlots[0]), 'matrix identity anchor')
  const stableIdentity = identityVector(firstPayload)
  const startedAt = new Date().toISOString()
  const miniProgram = await connectMiniProgram()
  const initialStorage = await storageValue(miniProgram)
  const results = []
  let failure = null
  try {
    const systemInfo = await waitForSystemInfo(miniProgram)
    for (const spec of specs) {
      try {
        results.push(await runSpec(
          miniProgram,
          systemInfo,
          apiBaseUrl,
          spec,
          stableIdentity,
          matrix.indexOf(spec),
          build,
          simcPolicy,
          phase,
          slotShard,
          diagnosticActionOnly,
        ))
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)
        const stack = error instanceof Error ? error.stack : message
        results.push({
          classKey: spec.classKey,
          className: spec.className,
          specId: spec.specId,
          specKey: spec.specKey,
          specName: spec.specName,
          status: 'FAIL',
          error: message,
          stack,
          slots: [],
          actions: {
            candidateApplyResolve: 'FAIL',
            craftedStatApplyResolve: 'FAIL',
            communityExactImport: 'FAIL',
            enhancementEditResolve: 'FAIL',
            saveReloadRecovery: 'FAIL',
            talentTemplatePreparation: 'FAIL',
            simcExecutionOrPolicyBlock: 'FAIL',
          },
        })
        failure = error
        process.stderr.write(`[wechat-gear-matrix:spec:end] ${spec.classKey}/${spec.specKey} FAIL ${stack}\n`)
        break
      }
    }
    const catalogOnly = phase === 'preview_catalog_only'
    const expectedResultStatus = slotShard
      ? 'SLOT_SHARD_PASS'
      : catalogOnly
        ? 'CATALOG_ONLY_PASS'
      : phase === 'preview_catalog_actions'
        ? 'PREVIEW_PASS'
        : 'PASS'
    const successStatus = slotShard
      ? 'SLOT_SHARD_PASS'
      : catalogOnly
        ? 'CATALOG_ONLY_PASS'
      : phase === 'preview_catalog_actions'
        ? 'PREVIEW_CATALOG_ACTIONS_PASS'
        : 'PASS'
    const report = {
      schemaVersion: 1,
      kind: slotShard
        ? 'wechat-gear-slot-shard'
        : catalogOnly
          ? 'wechat-gear-catalog-only-class-matrix'
        : 'wechat-gear-class-matrix',
      scope: {
        classKey,
        ...(slotShard ? { slotShard } : {}),
        expectedSpecs: specs.map((item) => item.specId),
        expectedSlotsPerSpec: slotShard ? [slotShard] : gearSlots,
        partialClassRunCannotProveGoal: true,
        catalogOnly: Boolean(slotShard || catalogOnly),
        actionsExcluded: Boolean(slotShard || catalogOnly),
        diagnosticActionOnly,
        phase,
        formalManifestRequiredForSkippedSimc: phase === 'preview_catalog_actions',
      },
      status: diagnosticActionOnly
        ? (!failure ? 'DIAGNOSTIC_PASS' : 'DIAGNOSTIC_FAIL')
        : !failure
          && results.length === specs.length
          && results.every((item) => item.status === expectedResultStatus)
          ? successStatus
          : 'FAIL',
      startedAt,
      completedAt: new Date().toISOString(),
      runtime: {
        apiBaseUrl,
        build,
        apiIdentity: stableIdentity,
        simcPolicy: {
          contractRevision: simcPolicy.contractRevision,
          supportedSpecCount: simcPolicy.supportedSpecCount,
          unsupportedSpecCount: simcPolicy.unsupportedSpecCount,
          unsupportedSpecializations: [...simcPolicy.unsupportedSpecializations].sort(),
        },
        systemInfo: {
          windowWidth: systemInfo.windowWidth,
          windowHeight: systemInfo.windowHeight,
          pixelRatio: systemInfo.pixelRatio,
        },
      },
      totals: {
        specsExpected: specs.length,
        specsExecuted: results.length,
        specsPassed: results.filter((item) => (
          item.status === expectedResultStatus
        )).length,
        slotChecks: results.reduce((sum, item) => sum + item.slots.length, 0),
        itemProgressionRelations: results.reduce(
          (sum, item) => sum + item.slots.reduce((slotSum, slot) => slotSum + slot.itemRelations.length, 0),
          0,
        ),
        candidateRowFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.candidateRowFactChecks,
            0,
          ),
          0,
        ),
        candidateMediaChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.candidateMediaChecks,
            0,
          ),
          0,
        ),
        candidateDetailFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.candidateDetailFactChecks,
            0,
          ),
          0,
        ),
        variantDisplayFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.variantDisplayFactChecks,
            0,
          ),
          0,
        ),
        expectedSelectableVariants: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.expectedSelectableVariants,
            0,
          ),
          0,
        ),
        selectedVariantFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.selectedVariantFactChecks,
            0,
          ),
          0,
        ),
        craftedOptionFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => slotSum + slot.craftedOptionFactChecks,
            0,
          ),
          0,
        ),
        selectedCraftedOptionFactChecks: results.reduce(
          (sum, item) => sum + item.slots.reduce(
            (slotSum, slot) => (
              slotSum + slot.selectedCraftedOptionFactChecks
            ),
            0,
          ),
          0,
        ),
      },
      results,
    }
    writeBoundedJsonAtomic(outputPath, report, `WeChat gear matrix ${classKey}`)
    process.stdout.write(`${JSON.stringify({
      status: report.status,
      classKey,
      outputPath,
      totals: report.totals,
      note: slotShard
        ? 'A catalog slot shard cannot prove action, SimC, or the 40-spec Goal verdict.'
        : phase === 'preview_catalog_actions'
        ? 'Preview catalog/actions evidence cannot prove final formal SimC or the 40-spec Goal verdict.'
        : 'A class PASS is not the 40-spec Goal verdict.',
    }, null, 2)}\n`)
    if (
      report.status !== 'PASS'
      && report.status !== 'DIAGNOSTIC_PASS'
      && report.status !== 'PREVIEW_CATALOG_ACTIONS_PASS'
      && report.status !== 'SLOT_SHARD_PASS'
      && report.status !== 'CATALOG_ONLY_PASS'
    ) process.exitCode = 1
  } finally {
    try {
      await restoreStorage(miniProgram, initialStorage)
    } finally {
      miniProgram.disconnect()
    }
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`)
  process.exit(1)
})
