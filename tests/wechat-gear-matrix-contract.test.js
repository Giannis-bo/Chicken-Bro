'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const {
  assertRuntimeBuildIdentity,
  gearSlots,
  normalizeCommittedGearEntries,
  normalizeCandidateDisplayRelations,
  normalizeSelectorMarker,
  normalizeSimcPolicy,
  normalizeSpecMatrix,
  normalizeTaskIds,
  selectCandidateApplySlot,
  selectCraftedApplyTarget,
  storageValueChanged,
  summarizeWechatGearClassReports,
  summarizeWechatGearMatrix,
  summarizeWechatGearPreviewClassReports,
} = require('../scripts/wechat-gear-matrix-contract')

test('normalizeCandidateDisplayRelations requires complete backend-owned visible facts', () => {
  const relations = normalizeCandidateDisplayRelations({
    items: [{
      itemId: '260423',
      displayName: '阿拉托尔的迅疾纪念',
      source: '团队副本',
      ilevel: '298',
      statSummary: '敏捷 67；暴击 60',
      iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/item.jpg',
      status: 'verified',
      equipmentBadges: [
        { key: 'equipment_type', label: '单手剑' },
        { key: 'weapon_handedness', label: '单手' },
      ],
      variants: [{
        variantKey: 'myth-289',
        difficultyLabel: '神话 6/6',
        itemLevel: 289,
        status: 'verified',
        statSummary: '敏捷 62；暴击 58',
        progressionState: { kind: 'upgrade_track' },
        displayProgression: { label: '神话 6/6' },
      }],
    }],
  })

  assert.deepEqual(relations, [{
    itemId: '260423',
    itemName: '阿拉托尔的迅疾纪念',
    sourceLabel: '团队副本',
    levelLabel: '装等 298',
    itemLevel: 298,
    statSummary: '敏捷 67；暴击 60',
    iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/item.jpg',
    equipmentTypeLabel: '单手剑',
    uiState: 'ready',
    variants: [{
      variantKey: 'myth-289',
      markerKey: 'myth-289',
      label: '神话 6/6',
      levelLabel: '装等 289',
      itemLevel: 289,
      statSummary: '敏捷 62；暴击 58',
      progression: '神话 6/6',
      progressionKind: 'upgrade_track',
      apiStatus: 'verified',
      uiState: 'ready',
      craftedStatSelectionRequired: false,
      craftedStatOptions: [],
    }],
  }])
})

test('normalizeCandidateDisplayRelations fails closed for missing display authority', () => {
  const fixture = {
    items: [{
      itemId: '260423',
      name: '阿拉托尔的迅疾纪念',
      source: '团队副本',
      ilevel: 298,
      statSummary: '敏捷 67',
      iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/item.jpg',
      status: 'verified',
      equipmentBadges: [{ key: 'equipment_type', label: '单手剑' }],
      variants: [{
        variantKey: 'myth-289',
        difficultyLabel: '神话 6/6',
        itemLevel: 289,
        status: 'verified',
        statSummary: '敏捷 62',
        progressionState: { kind: 'upgrade_track' },
        displayProgression: { label: '神话 6/6' },
      }],
    }],
  }

  for (const [label, mutate] of [
    ['source', (item) => { delete item.source }],
    ['icon', (item) => { delete item.iconUrl }],
    ['equipment type', (item) => { item.equipmentBadges = [] }],
    ['variant progression', (item) => { delete item.variants[0].progressionState }],
    ['variant stats', (item) => { delete item.variants[0].statSummary }],
  ]) {
    const candidate = structuredClone(fixture)
    mutate(candidate.items[0])
    assert.throws(
      () => normalizeCandidateDisplayRelations(candidate),
      new RegExp(label.replace(' ', '.*'), 'iu'),
    )
  }
})

test('normalizeCandidateDisplayRelations preserves selectable crafted-stat identities', () => {
  const [relation] = normalizeCandidateDisplayRelations({
    items: [{
      itemId: '244743',
      displayName: 'Aetherlume Eye Wrap',
      source: '制造装备',
      ilevel: 285,
      statSummary: '智力 201；急速 50；精通 50',
      iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/item.jpg',
      status: 'verified',
      equipmentBadges: [{ key: 'equipment_type', label: '布甲' }],
      variants: [{
        variantKey: 'crafted-myth-285',
        difficultyLabel: '神话',
        itemLevel: 285,
        status: 'verified',
        statSummary: '智力 201；急速 50；精通 50',
        progressionState: { kind: 'crafted_quality' },
        displayProgression: { label: '制造 神话' },
        craftedStatSelectionRequired: true,
        craftedStatOptions: [{
          optionId: 'crafted-stats-haste-mastery',
          key: 'haste-mastery',
          label: '急速 + 精通',
          status: 'verified',
          simcOptions: { crafted_stats: '36/49' },
        }],
      }],
    }],
  })

  assert.equal(relation.variants[0].craftedStatSelectionRequired, true)
  assert.deepEqual(relation.variants[0].craftedStatOptions, [{
    optionId: 'crafted-stats-haste-mastery',
    markerKey: 'crafted-stats-haste-mastery',
    key: 'haste-mastery',
    label: '急速 + 精通',
    craftedStats: '36/49',
    apiStatus: 'verified',
    uiState: 'ready',
  }])
  assert.throws(
    () => normalizeCandidateDisplayRelations({
      items: [{
        itemId: '244743',
        displayName: 'Aetherlume Eye Wrap',
        source: '制造装备',
        ilevel: 285,
        statSummary: '智力 201',
        iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/item.jpg',
        status: 'verified',
        equipmentBadges: [{ key: 'equipment_type', label: '布甲' }],
        variants: [{
          variantKey: 'crafted-myth-285',
          difficultyLabel: '神话',
          itemLevel: 285,
          status: 'verified',
          statSummary: '智力 201',
          progressionState: { kind: 'crafted_quality' },
          displayProgression: { label: '制造 神话' },
          craftedStatSelectionRequired: true,
          craftedStatOptions: [],
        }],
      }],
    }),
    /missing selectable crafted stat options/u,
  )
})

test('storageValueChanged compares persisted content rather than object identity', () => {
  const before = { templates: [{ id: 'gear-1', value: { itemId: '1001' } }] }

  assert.equal(storageValueChanged(before, structuredClone(before)), false)
  assert.equal(
    storageValueChanged(before, {
      templates: [{ id: 'gear-1', value: { itemId: '1002' } }],
    }),
    true,
  )
})

test('WeChat runner prepares supported SimC talent input through the rendered UI', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../scripts/verify-wechat-gear-matrix.js'),
    'utf8',
  )

  assert.match(source, /async function prepareTalentTemplateForSimc\(/u)
  assert.match(source, /\/pages\/builds\/talent-simulator\?spec=/u)
  assert.match(source, /\.wx-data-role-talent-template-import-sheet/u)
  assert.match(source, /\.wx-style-templatesheetcommunityimport/u)
  assert.match(source, /\.wx-data-role-talent-template-name-sheet/u)
  assert.match(source, /\.wx-style-templatenamesheetconfirm/u)
  assert.match(source, /\.wx-style-templatesheetitem/u)
  assert.match(source, /talentTemplatePreparation/u)
  assert.match(
    source,
    /const apply = await waitForEnabledElement\([\s\S]*?\.wx-data-action-id-gear-candidate-apply/u,
  )
  assert.match(source, /sawResolving = state\.resolveState === 'resolving' \|\| sawResolving/u)
  assert.match(source, /select inspected canonical variant/u)
  assert.match(source, /state === 'ready' \|\| item\.state === 'partial'/u)
  assert.match(source, /wait for .* enhancement option .* active/u)
  assert.match(
    source,
    /waitForEnabledElement\([\s\S]*?\.wx-data-action-id-gear-enhancement-confirm/u,
  )
  assert.match(source, /wait for .* enhancement commit outcome/u)
  assert.match(source, /enhancement failed; diagnostics=/u)
  assert.match(source, /async function applyCraftedCandidateAndResolve\(/u)
  assert.match(source, /\.wx-data-role-gear-crafted-stat-option/u)
  assert.match(source, /select apply crafted option/u)
  assert.match(source, /candidate-draft-crafted-option-id/u)
  assert.match(source, /resolved-slot-crafted-option-id/u)
  const enabledWithoutOptionBranch = source.match(
    /if \(!option\) \{(?<body>[\s\S]*?)\n      \}/u,
  )
  assert.ok(enabledWithoutOptionBranch?.groups?.body)
  assert.match(enabledWithoutOptionBranch.groups.body, /throw new Error/u)
  assert.doesNotMatch(enabledWithoutOptionBranch.groups.body, /\bcontinue\b/u)
})

test('selectCraftedApplyTarget avoids the ordinary apply item and current slot identity', () => {
  const targets = [
    {
      slot: 'head',
      itemId: '1001',
      variantKey: 'crafted-head',
      craftedOptionId: 'crafted-stats-haste',
    },
    {
      slot: 'head',
      itemId: '1002',
      variantKey: 'crafted-head-alt',
      craftedOptionId: 'crafted-stats-mastery',
    },
    {
      slot: 'wrist',
      itemId: '2001',
      variantKey: 'crafted-wrist',
      craftedOptionId: 'crafted-stats-crit-haste',
    },
  ]

  assert.deepEqual(
    selectCraftedApplyTarget(
      targets,
      {
        head: { committedItemId: '1001', resolvedItemId: '1001' },
        wrist: { committedItemId: '2000', resolvedItemId: '2000' },
      },
      ['1002'],
      0,
    ),
    targets[2],
  )
  assert.throws(
    () => selectCraftedApplyTarget(
      targets.slice(0, 2),
      { head: { committedItemId: '1001', resolvedItemId: '1001' } },
      ['1002'],
      0,
    ),
    /no cross-item crafted stat apply target/u,
  )
})

test('WeChat runner keeps preview catalog actions distinct from the final formal matrix', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../scripts/verify-wechat-gear-matrix.js'),
    'utf8',
  )
  const summarySource = fs.readFileSync(
    path.resolve(__dirname, '../scripts/summarize-wechat-gear-matrix.js'),
    'utf8',
  )

  assert.match(source, /WECHAT_GEAR_MATRIX_PHASE/u)
  assert.match(source, /preview_catalog_actions/u)
  assert.match(source, /PREVIEW_CATALOG_ACTIONS_PASS/u)
  assert.match(source, /NOT_RUN_PREVIEW_TRUST_BOUNDARY/u)
  assert.match(source, /preview_requires_formal_manifest/u)
  assert.match(summarySource, /WECHAT_GEAR_MATRIX_SUMMARY_PHASE/u)
  assert.match(summarySource, /wechat-gear-preview-catalog-actions-summary/u)
  assert.match(summarySource, /formalSimcProven: phase === 'full'/u)
})

test('WeChat runner opens every candidate and every selectable variant to prove visible facts', () => {
  const source = fs.readFileSync(
    path.resolve(__dirname, '../scripts/verify-wechat-gear-matrix.js'),
    'utf8',
  )

  assert.match(source, /normalizeCandidateDisplayRelations\(group\)/u)
  assert.match(source, /async function inspectCandidateRow\(/u)
  assert.match(source, /trustedCandidateMedia\(entry\.row, relation\.itemId\)/u)
  assert.match(source, /candidateDetailExpectedText\(relation, variant\)/u)
  assert.match(
    source,
    /for \(const variant of relation\.variants\.filter\(\(item\) => item\.uiState === 'ready' \|\| item\.uiState === 'partial'\)\)/u,
  )
  assert.match(source, /selectedVariantFactChecks === expectedSelectableVariants/u)
  assert.match(source, /candidateMediaChecks/u)
  assert.match(source, /variantDisplayFactChecks/u)
})

test('assertRuntimeBuildIdentity fails closed for a stale or unidentified WeChat runtime', () => {
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const expectedRuntimeIdentity = {
    gitHead: normalizeSelectorMarker(build.gitHead),
    sourceHash: normalizeSelectorMarker(build.sourceHash),
  }

  assert.deepEqual(assertRuntimeBuildIdentity(expectedRuntimeIdentity, build), expectedRuntimeIdentity)
  assert.throws(() => assertRuntimeBuildIdentity({}, build), /identity is missing/u)
  assert.throws(
    () => assertRuntimeBuildIdentity({ ...expectedRuntimeIdentity, sourceHash: 'sha256-stale' }, build),
    /identity mismatch/u,
  )
})

function homeFixture() {
  return {
    classOptions: Array.from({ length: 13 }, (_, classIndex) => ({
      name: `Class ${classIndex}`,
      websimClassKey: `class-${classIndex}`,
      specializations: Array.from(
        { length: classIndex < 12 ? 3 : 4 },
        (_, specIndex) => ({
          id: `class-${classIndex}-spec-${specIndex}`,
          name: `Spec ${specIndex}`,
          websimClassKey: `class-${classIndex}`,
          websimSpecKey: `spec-${specIndex}`,
        }),
      ),
    })),
  }
}

function passingSpec(specId) {
  return {
    specId,
    status: 'PASS',
    slots: gearSlots.map((slot) => ({
      slot,
      status: 'PASS',
      expectedItems: 2,
      actualItems: 2,
      candidateRowFactChecks: 2,
      candidateMediaChecks: 2,
      candidateDetailFactChecks: 2,
      expectedVariants: 4,
      actualVariants: 4,
      variantDisplayFactChecks: 4,
      expectedSelectableVariants: 4,
      selectedVariantFactChecks: 4,
      craftedOptionFactChecks: slot.startsWith('trinket') ? 0 : 1,
      selectedCraftedOptionFactChecks: slot.startsWith('trinket') ? 0 : 1,
    })),
    actions: {
      candidateApplyResolve: 'PASS',
      craftedStatApplyResolve: 'PASS',
      communityExactImport: 'PASS',
      enhancementEditResolve: 'PASS',
      saveReloadRecovery: 'PASS',
      talentTemplatePreparation: 'PASS',
      simcExecutionOrPolicyBlock: 'PASS',
    },
  }
}

function passingCrossEquipmentSpec(spec, index, build) {
  const requestedKind = ['socket', 'enchant', 'embellishment'][index % 3]
  const applySlot = ['head', 'main_hand', 'trinket1'][index % 3]
  const craftedSlots = gearSlots.filter((slot) => !slot.startsWith('trinket'))
  const craftedOptionIds = [
    'crafted-stats-crit',
    'crafted-stats-haste',
    'crafted-stats-versatility',
    'crafted-stats-mastery',
    'crafted-stats-crit-haste',
    'crafted-stats-crit-versatility',
    'crafted-stats-crit-mastery',
    'crafted-stats-haste-versatility',
    'crafted-stats-haste-mastery',
    'crafted-stats-versatility-mastery',
  ]
  const craftedSlot = craftedSlots[index % craftedSlots.length]
  const craftedOptionId = craftedOptionIds[index % craftedOptionIds.length]
  const simcEvidence = index < 26
    ? {
        status: 'PASS',
        mode: 'executed',
        taskId: `task-${spec.specId}`,
        terminalResult: 'completed',
        taskListVisible: true,
      }
    : {
        status: 'PASS',
        mode: 'policy_blocked',
        blockerCode: 'SIMC_SPECIALIZATION_UNSUPPORTED',
        taskCreated: false,
      }
  return {
    ...passingSpec(spec.specId),
    classKey: spec.classKey,
    specKey: spec.specKey,
    status: 'PASS',
    runtimeBuildIdentity: {
      gitHead: normalizeSelectorMarker(build.gitHead),
      sourceHash: normalizeSelectorMarker(build.sourceHash),
    },
    slots: gearSlots.map((slot, slotIndex) => ({
      slot,
      status: 'PASS',
      expectedItems: 2,
      actualItems: 2,
      candidateRowFactChecks: 2,
      candidateMediaChecks: 2,
      candidateDetailFactChecks: 2,
      expectedVariants: 4,
      actualVariants: 4,
      variantDisplayFactChecks: 4,
      expectedSelectableVariants: 4,
      selectedVariantFactChecks: 4,
      craftedOptionFactChecks: slot.startsWith('trinket') ? 0 : 1,
      selectedCraftedOptionFactChecks: slot.startsWith('trinket') ? 0 : 1,
      itemRelations: [
        {
          itemId: `${spec.specId}-${slot}-item-${slotIndex}`,
          variantKey: `${spec.specId}-${slot}-variant-a`,
          status: 'PASS',
        },
        {
          itemId: `${spec.specId}-${slot}-item-${slotIndex + 1}`,
          variantKey: `${spec.specId}-${slot}-variant-b`,
          status: 'PASS',
        },
        {
          itemId: `${spec.specId}-${slot}-item-${slotIndex}`,
          variantKey: `${spec.specId}-${slot}-variant-c`,
          status: 'PASS',
        },
        {
          itemId: `${spec.specId}-${slot}-item-${slotIndex + 1}`,
          variantKey: `${spec.specId}-${slot}-variant-d`,
          status: 'PASS',
        },
      ],
    })),
    actionEvidence: {
      candidateApplyResolve: { status: 'PASS', slot: applySlot },
      craftedStatApplyResolve: {
        status: 'PASS',
        slot: craftedSlot,
        itemId: `crafted-${spec.specId}`,
        variantKey: 'crafted-myth-285',
        craftedOptionId,
        committedCraftedOptionId: craftedOptionId,
        resolvedCraftedOptionId: craftedOptionId,
      },
      communityExactImport: { status: 'PASS', importedSlots: 16 },
      enhancementEditResolve: {
        status: 'PASS',
        requestedKind,
        appliedKind: requestedKind,
      },
      saveReloadRecovery: { status: 'PASS', reloadedSlots: 16 },
      talentTemplatePreparation: index < 26
        ? {
            status: 'PASS',
            mode: 'prepared',
            communityImported: true,
            templatePersisted: true,
          }
        : {
            status: 'PASS',
            mode: 'policy_not_required',
            specializationUnsupported: true,
          },
      simcExecutionOrPolicyBlock: simcEvidence,
    },
  }
}

function passingClassReports(specs, build) {
  const byClass = new Map()
  specs.forEach((spec, index) => {
    if (!byClass.has(spec.classKey)) byClass.set(spec.classKey, [])
    byClass.get(spec.classKey).push(passingCrossEquipmentSpec(spec, index, build))
  })
  return [...byClass.entries()].map(([classKey, results]) => ({
    kind: 'wechat-gear-class-matrix',
    status: 'PASS',
    scope: {
      classKey,
      expectedSpecs: results.map((item) => item.specId),
      expectedSlotsPerSpec: gearSlots,
      diagnosticActionOnly: false,
    },
    runtime: { build },
    totals: {
      specsExpected: results.length,
      specsExecuted: results.length,
      specsPassed: results.length,
      slotChecks: results.length * gearSlots.length,
      itemProgressionRelations: results.reduce(
        (sum, item) => sum + item.slots.reduce(
          (slotSum, slot) => slotSum + slot.itemRelations.length,
          0,
        ),
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
  }))
}

function passingPreviewClassReports(specs, build) {
  const reports = passingClassReports(specs, build)
  const unsupported = new Set(
    specs.slice(26).map((spec) => `${spec.classKey}:${spec.specKey}`),
  )
  const apiIdentity = {
    manifestRevision: 'season-manifest:sha256:preview',
    gearCatalogRevision: 'gear-catalog:sha256:preview',
    gearExactRegistryRevision: 'gear-exact-registry:sha256:preview',
    gearCatalogReleaseId: 'gear-release:sha256:preview',
    communityTemplateReleaseId: 'community-release:sha256:preview',
    pointerGeneration: 35,
  }
  for (const report of reports) {
    report.status = 'PREVIEW_CATALOG_ACTIONS_PASS'
    report.scope.phase = 'preview_catalog_actions'
    report.scope.formalManifestRequiredForSkippedSimc = true
    report.runtime.apiIdentity = apiIdentity
    report.runtime.simcPolicy = {
      contractRevision: 'simc-execution-support-v1',
      supportedSpecCount: 26,
      unsupportedSpecCount: 14,
      unsupportedSpecializations: [...unsupported].sort(),
    }
    for (const result of report.results) {
      result.status = 'PREVIEW_PASS'
      const specializationId = `${result.classKey}:${specs.find((spec) => spec.specId === result.specId).specKey}`
      if (unsupported.has(specializationId)) continue
      result.actions.simcExecutionOrPolicyBlock = 'NOT_RUN_PREVIEW_TRUST_BOUNDARY'
      result.actionEvidence.simcExecutionOrPolicyBlock = {
        status: 'NOT_RUN_PREVIEW_TRUST_BOUNDARY',
        mode: 'preview_requires_formal_manifest',
        formalActiveManifestRequired: true,
      }
    }
    report.totals.specsPassed = report.results.length
  }
  return reports
}

function simcOptionsFixture(specs) {
  return {
    contractRevision: 'simc-options-v1',
    status: 'ready',
    specializationPolicy: {
      contractRevision: 'simc-execution-support-v1',
      status: 'ready',
      supportedSpecCount: 26,
      unsupportedSpecCount: 14,
      unsupportedSpecializations: specs.slice(26).map((spec) => ({
        specializationId: `${spec.classKey}:${spec.specKey}`,
        role: 'tank',
        code: 'SIMC_SPECIALIZATION_UNSUPPORTED',
      })),
    },
  }
}

test('normalizeSelectorMarker exactly mirrors the rendered semantic class contract', () => {
  assert.equal(
    normalizeSelectorMarker('browse-variant:sha256:ABC_123'),
    'browse-variant-sha256-abc_123',
  )
  assert.equal(normalizeSelectorMarker('  '), 'empty')
})

test('normalizeTaskIds excludes WeChat placeholder rows without turning null into a task', () => {
  assert.deepEqual(
    normalizeTaskIds([null, undefined, '', '  ', 'task-b', 'task-a', 'task-b']),
    ['task-a', 'task-b'],
  )
})

test('normalizeCommittedGearEntries distinguishes an empty marker sentinel from a committed item', () => {
  assert.deepEqual(
    normalizeCommittedGearEntries([
      {
        slot: 'head',
        itemId: 'empty',
        hasCommittedItem: 'false',
      },
      {
        slot: 'main_hand',
        itemId: 'item-main-hand',
        hasCommittedItem: 'true',
      },
    ]),
    { main_hand: 'item-main-hand' },
  )
  assert.throws(
    () => normalizeCommittedGearEntries([{
      slot: 'head',
      itemId: 'empty',
      hasCommittedItem: 'true',
    }]),
    /committed item identity is missing/u,
  )
  assert.throws(
    () => normalizeCommittedGearEntries([{
      slot: 'head',
      itemId: 'item-head',
      hasCommittedItem: 'unknown',
    }]),
    /committed item presence marker/u,
  )
})

test('selectCandidateApplySlot records a nonempty fallback without claiming the preferred slot', () => {
  const slots = [
    { slot: 'head', expectedItems: 0 },
    { slot: 'neck', expectedItems: 12 },
    { slot: 'trinket1', expectedItems: 35 },
  ]

  assert.deepEqual(selectCandidateApplySlot(slots, 'head'), {
    slot: 'neck',
    preferredSlot: 'head',
    usedFallback: true,
  })
  assert.deepEqual(selectCandidateApplySlot(slots, 'trinket1'), {
    slot: 'trinket1',
    preferredSlot: 'trinket1',
    usedFallback: false,
  })
  assert.throws(
    () => selectCandidateApplySlot([{ slot: 'head', expectedItems: 0 }], 'head'),
    /no inspected slot with candidates/u,
  )
})

test('normalizeSpecMatrix requires the current 13-class 40-spec topology', () => {
  const specs = normalizeSpecMatrix(homeFixture())

  assert.equal(specs.length, 40)
  assert.equal(new Set(specs.map((item) => item.specId)).size, 40)
  assert.equal(new Set(specs.map((item) => item.classKey)).size, 13)
})

test('normalizeSpecMatrix rejects an incomplete or ambiguous topology', () => {
  const incomplete = homeFixture()
  incomplete.classOptions[0].specializations.pop()
  assert.throws(() => normalizeSpecMatrix(incomplete), /expected 40 specs/u)

  const duplicate = homeFixture()
  duplicate.classOptions[1].specializations[0].id = duplicate.classOptions[0].specializations[0].id
  assert.throws(() => normalizeSpecMatrix(duplicate), /duplicate spec id/u)
})

test('normalizeSimcPolicy requires an exact backend-owned 26 executed / 14 blocked matrix', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const policy = normalizeSimcPolicy(simcOptionsFixture(specs), specs)

  assert.equal(policy.supportedSpecCount, 26)
  assert.equal(policy.unsupportedSpecCount, 14)
  assert.equal(policy.unsupportedSpecializations.size, 14)
  assert.ok(policy.unsupportedSpecializations.has(`${specs[39].classKey}:${specs[39].specKey}`))
})

test('normalizeSimcPolicy fails closed for a duplicate, unknown, or non-canonical blocker', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const duplicate = simcOptionsFixture(specs)
  duplicate.specializationPolicy.unsupportedSpecializations[0] = {
    ...duplicate.specializationPolicy.unsupportedSpecializations[1],
  }
  assert.throws(() => normalizeSimcPolicy(duplicate, specs), /invalid SimC unsupported/u)

  const unknown = simcOptionsFixture(specs)
  unknown.specializationPolicy.unsupportedSpecializations[0].specializationId = 'unknown:unknown'
  assert.throws(() => normalizeSimcPolicy(unknown, specs), /invalid SimC unsupported/u)

  const wrongCode = simcOptionsFixture(specs)
  wrongCode.specializationPolicy.unsupportedSpecializations[0].code = 'VIEW_ONLY_BLOCK'
  assert.throws(() => normalizeSimcPolicy(wrongCode, specs), /invalid SimC unsupported/u)
})

test('summarizeWechatGearMatrix passes only a complete 40-spec all-slot action matrix', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const summary = summarizeWechatGearMatrix(specs.map((item) => passingSpec(item.specId)), specs)

  assert.equal(summary.status, 'PASS')
  assert.equal(summary.classes, 13)
  assert.equal(summary.specs, 40)
  assert.equal(summary.slotChecks, 640)
  assert.equal(summary.actionChecks, 280)
  assert.deepEqual(summary.reasonCodes, [])
})

test('summarizeWechatGearMatrix fails closed for a missing slot, item mismatch, or action', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const results = specs.map((item) => passingSpec(item.specId))
  results[0].slots.pop()
  results[1].slots[0].actualItems = 1
  results[2].actions.enhancementEditResolve = 'SKIP'

  const summary = summarizeWechatGearMatrix(results, specs)

  assert.equal(summary.status, 'FAIL')
  assert.ok(summary.reasonCodes.includes('missing_slot_checks'))
  assert.ok(summary.reasonCodes.includes('catalog_surface_mismatch'))
  assert.ok(summary.reasonCodes.includes('action_matrix_incomplete'))
})

test('summarizeWechatGearClassReports proves only 13 non-diagnostic reports with cross-equipment coverage', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const reports = passingClassReports(specs, build)

  const summary = summarizeWechatGearClassReports(reports, specs, build)

  assert.equal(summary.status, 'PASS')
  assert.equal(summary.classes, 13)
  assert.equal(summary.specs, 40)
  assert.equal(summary.slotChecks, 640)
  assert.equal(summary.actionChecks, 280)
  assert.equal(summary.itemChecks, 1280)
  assert.equal(summary.variantChecks, 2560)
  assert.equal(summary.itemProgressionRelations, 2560)
  assert.deepEqual(summary.applySlots, ['head', 'main_hand', 'trinket1'])
  assert.deepEqual(summary.requestedEnhancementKinds, ['embellishment', 'enchant', 'socket'])
  assert.deepEqual(summary.appliedEnhancementKinds, ['embellishment', 'enchant', 'socket'])
  assert.equal(summary.talentTemplatesPrepared, 26)
  assert.equal(summary.talentTemplatesPolicyNotRequired, 14)
  assert.equal(summary.simcExecuted, 26)
  assert.equal(summary.simcPolicyBlocked, 14)
  assert.deepEqual(summary.reasonCodes, [])
})

test('summarizeWechatGearClassReports rejects an enhancement fallback without unavailable-control proof', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const reports = passingClassReports(specs, build)
  const fallback = reports[0].results[0].actionEvidence.enhancementEditResolve
  fallback.appliedKind = fallback.requestedKind === 'socket' ? 'enchant' : 'socket'

  const summary = summarizeWechatGearClassReports(reports, specs, build)

  assert.equal(summary.status, 'FAIL')
  assert.ok(summary.reasonCodes.includes('enhancement_fallback_unproven'))
})

test('summarizeWechatGearClassReports rejects an incomplete actual visible-fact matrix', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const reports = passingClassReports(specs, build)
  reports[0].results[0].slots[0].candidateMediaChecks -= 1

  const summary = summarizeWechatGearClassReports(reports, specs, build)

  assert.equal(summary.status, 'FAIL')
  assert.ok(summary.reasonCodes.includes('visible_fact_matrix_incomplete'))
  assert.ok(summary.reasonCodes.includes('class_report_totals_mismatch'))
})

test('summarizeWechatGearPreviewClassReports proves the complete preview matrix without claiming formal SimC', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const reports = passingPreviewClassReports(specs, build)

  const summary = summarizeWechatGearPreviewClassReports(reports, specs, build)

  assert.equal(summary.status, 'PREVIEW_CATALOG_ACTIONS_PASS')
  assert.equal(summary.classes, 13)
  assert.equal(summary.specs, 40)
  assert.equal(summary.slotChecks, 640)
  assert.equal(summary.simcFormalRequired, 26)
  assert.equal(summary.simcExecuted, 0)
  assert.equal(summary.simcPolicyBlocked, 14)
  assert.equal(summary.apiIdentityCount, 1)
  assert.deepEqual(summary.reasonCodes, [])
})

test('summarizeWechatGearClassReports fails closed for diagnostic, missing class, or incomplete cross-actions', () => {
  const specs = normalizeSpecMatrix(homeFixture())
  const build = {
    gitHead: '7a620282c1b4f39cee498cb6a7e9c4a3f1408633',
    sourceHash: 'sha256:d6f69b7878294dd7db03bde0aca65e0b0a9e0f8b4201a2de647bd0266bded781',
  }
  const reports = passingClassReports(specs, build)
  reports[0].scope.diagnosticActionOnly = true
  reports.forEach((report) => report.results.forEach((item) => {
    item.actionEvidence.enhancementEditResolve.appliedKind = 'socket'
    item.actionEvidence.talentTemplatePreparation = {
      status: 'PASS',
      mode: 'policy_not_required',
      specializationUnsupported: true,
    }
    item.actionEvidence.simcExecutionOrPolicyBlock = {
      status: 'PASS',
      mode: 'policy_blocked',
      blockerCode: 'SIMC_SPECIALIZATION_UNSUPPORTED',
      taskCreated: false,
    }
  }))
  reports.pop()

  const summary = summarizeWechatGearClassReports(reports, specs, build)

  assert.equal(summary.status, 'FAIL')
  assert.ok(summary.reasonCodes.includes('class_reports_incomplete'))
  assert.ok(summary.reasonCodes.includes('diagnostic_report_present'))
  assert.ok(summary.reasonCodes.includes('cross_action_coverage_incomplete'))
  assert.ok(summary.reasonCodes.includes('simc_input_preparation_incomplete'))
  assert.ok(summary.reasonCodes.includes('simc_matrix_incomplete'))
})
