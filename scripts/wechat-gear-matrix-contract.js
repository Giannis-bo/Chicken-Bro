'use strict'

const { isDeepStrictEqual } = require('node:util')

const gearSlots = Object.freeze([
  'head',
  'neck',
  'shoulder',
  'back',
  'chest',
  'wrist',
  'main_hand',
  'off_hand',
  'hands',
  'waist',
  'legs',
  'feet',
  'finger1',
  'finger2',
  'trinket1',
  'trinket2',
])

const requiredActions = Object.freeze([
  'candidateApplyResolve',
  'craftedStatApplyResolve',
  'communityExactImport',
  'enhancementEditResolve',
  'saveReloadRecovery',
  'talentTemplatePreparation',
  'simcExecutionOrPolicyBlock',
])

function normalizeSelectorMarker(value) {
  const normalized = String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return normalized || 'empty'
}

function normalizeTaskIds(values) {
  return [...new Set(
    (Array.isArray(values) ? values : [])
      .filter((value) => value !== null && value !== undefined && String(value).trim())
      .map(String),
  )].sort()
}

function storageValueChanged(before, after) {
  return !isDeepStrictEqual(before, after)
}

function displayText(value) {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value).trim()
    : ''
}

function finitePositiveNumber(...values) {
  for (const value of values) {
    const raw = displayText(value)
    if (!/^(?:\d+|\d+\.\d+)$/u.test(raw)) continue
    const parsed = Number(raw)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return null
}

function firstDisplayText(...values) {
  return values.map(displayText).find(Boolean) ?? ''
}

function candidateUiState(item) {
  const compatibility = typeof item?.compatibility === 'string'
    ? displayText(item.compatibility)
    : displayText(item?.compatibility?.status)
  const statuses = [item?.status, item?.state]
    .map((value) => displayText(value).toLowerCase())
    .filter(Boolean)
  const blockers = Array.isArray(item?.blockers)
    ? item.blockers.map(displayText).filter(Boolean)
    : []
  if (
    !displayText(item?.itemId ?? item?.id)
    || compatibility.toLowerCase() === 'incompatible'
    || statuses.includes('blocked')
    || displayText(item?.metadataStatus).toLowerCase() === 'blocked'
    || blockers.length
  ) return 'blocked'
  if (
    item?.simcReady === true
    || statuses.some((status) => status === 'ready' || status === 'verified')
  ) return 'ready'
  return 'partial'
}

function variantUiState(variant) {
  const blockers = Array.isArray(variant?.blockers)
    ? variant.blockers.map(displayText).filter(Boolean)
    : []
  const status = firstDisplayText(variant?.state, variant?.status).toLowerCase()
  if (status === 'blocked' || blockers.length) return 'blocked'
  if (status === 'ready' || status === 'verified') return 'ready'
  if (status === 'partial') return 'partial'
  return 'blocked'
}

function requiredDisplayText(value, label, itemId) {
  const result = displayText(value)
  if (!result) throw new Error(`candidate ${itemId || 'unknown'} is missing ${label}`)
  return result
}

function normalizeCraftedStatOptions(variant, itemId, variantKey) {
  const required = variant?.craftedStatSelectionRequired === true
  const values = Array.isArray(variant?.craftedStatOptions)
    ? variant.craftedStatOptions
    : []
  if (required && values.length === 0) {
    throw new Error(
      `candidate ${itemId} variant ${variantKey} is missing selectable crafted stat options`,
    )
  }
  if (!required && values.length > 0) {
    throw new Error(
      `candidate ${itemId} variant ${variantKey} exposes crafted stat options without a selection requirement`,
    )
  }
  const seen = new Set()
  return values.map((option) => {
    const optionId = requiredDisplayText(
      option?.optionId ?? option?.id,
      'crafted option identity',
      itemId,
    )
    if (seen.has(optionId)) {
      throw new Error(
        `candidate ${itemId} variant ${variantKey} duplicates crafted option ${optionId}`,
      )
    }
    seen.add(optionId)
    const key = requiredDisplayText(
      option?.key,
      'crafted option key',
      itemId,
    )
    const label = requiredDisplayText(
      option?.label ?? option?.name,
      'crafted option label',
      itemId,
    )
    const craftedStats = requiredDisplayText(
      option?.simcOptions?.crafted_stats,
      'crafted_stats authority',
      itemId,
    )
    const apiStatus = requiredDisplayText(
      option?.status ?? option?.state,
      'crafted option status',
      itemId,
    )
    return {
      optionId,
      markerKey: normalizeSelectorMarker(optionId),
      key,
      label,
      craftedStats,
      apiStatus,
      uiState: variantUiState(option),
    }
  })
}

function normalizeCandidateDisplayRelations(group) {
  if (!Array.isArray(group?.items)) throw new Error('candidate group items must be an array')
  const seenItems = new Set()
  return group.items.map((item) => {
    const itemId = requiredDisplayText(item?.itemId ?? item?.id, 'item identity', '')
    if (seenItems.has(itemId)) throw new Error(`candidate item identity is duplicated: ${itemId}`)
    seenItems.add(itemId)
    const itemName = requiredDisplayText(
      firstDisplayText(item?.displayName, item?.name, item?.itemName),
      'name',
      itemId,
    )
    const sourceLabel = requiredDisplayText(item?.source, 'source', itemId)
    const itemLevel = finitePositiveNumber(item?.ilevel, item?.itemLevel)
    if (itemLevel === null) throw new Error(`candidate ${itemId} is missing item level`)
    const statSummary = requiredDisplayText(item?.statSummary, 'stats', itemId)
    const iconUrl = requiredDisplayText(item?.iconUrl, 'icon', itemId)
    const equipmentBadges = Array.isArray(item?.equipmentBadges) ? item.equipmentBadges : []
    const equipmentTypeLabel = equipmentBadges
      .filter((badge) => badge && typeof badge === 'object')
      .find((badge) => displayText(badge.key) === 'equipment_type')
    const equipmentType = displayText(equipmentTypeLabel?.label)
    if (!equipmentType) throw new Error(`candidate ${itemId} is missing equipment type authority`)

    const variants = Array.isArray(item?.variants) ? item.variants : []
    const seenVariants = new Set()
    const normalizedVariants = variants.flatMap((variant) => {
      const variantKey = displayText(variant?.key ?? variant?.variantKey)
      if (variantKey === 'needs-variant') return []
      if (!variantKey) throw new Error(`candidate ${itemId} is missing variant identity`)
      if (seenVariants.has(variantKey)) {
        throw new Error(`candidate ${itemId} variant identity is duplicated: ${variantKey}`)
      }
      seenVariants.add(variantKey)
      const label = requiredDisplayText(
        firstDisplayText(
          variant?.difficultyLabel,
          variant?.trackLabel,
          variant?.displayLabel,
          variant?.label,
          variant?.name,
        ),
        'variant label',
        itemId,
      )
      const variantLevel = finitePositiveNumber(variant?.itemLevel, variant?.ilevel)
      if (variantLevel === null) {
        throw new Error(`candidate ${itemId} variant ${variantKey} is missing item level`)
      }
      const progression = requiredDisplayText(
        firstDisplayText(variant?.displayProgression?.label, variant?.progressionLabel),
        'variant progression label',
        itemId,
      )
      const progressionKind = requiredDisplayText(
        variant?.progressionState?.kind,
        'variant progression kind',
        itemId,
      )
      const apiStatus = requiredDisplayText(
        firstDisplayText(variant?.status, variant?.state),
        'variant status',
        itemId,
      )
      const uiState = variantUiState(variant)
      const variantStatSummary = displayText(variant?.statSummary)
      if (uiState !== 'blocked' && !variantStatSummary) {
        throw new Error(`candidate ${itemId} variant ${variantKey} is missing variant stats`)
      }
      const craftedStatSelectionRequired = (
        variant?.craftedStatSelectionRequired === true
      )
      const craftedStatOptions = normalizeCraftedStatOptions(
        variant,
        itemId,
        variantKey,
      )
      return [{
        variantKey,
        markerKey: normalizeSelectorMarker(variantKey),
        label,
        levelLabel: `装等 ${Math.round(variantLevel)}`,
        itemLevel: variantLevel,
        statSummary: variantStatSummary,
        progression,
        progressionKind,
        apiStatus,
        uiState,
        craftedStatSelectionRequired,
        craftedStatOptions,
      }]
    })
    if (variants.length > 0 && normalizedVariants.length === 0) {
      throw new Error(`candidate ${itemId} has no visible canonical variants`)
    }
    return {
      itemId,
      itemName,
      sourceLabel,
      levelLabel: `装等 ${Math.round(itemLevel)}`,
      itemLevel,
      statSummary,
      iconUrl,
      equipmentTypeLabel: equipmentType,
      uiState: candidateUiState(item),
      variants: normalizedVariants,
    }
  })
}

function normalizeCommittedGearEntries(entries) {
  if (!Array.isArray(entries)) {
    throw new Error('committed gear entries must be an array')
  }
  const result = {}
  for (const raw of entries) {
    const slot = String(raw?.slot ?? '').trim()
    const itemId = String(raw?.itemId ?? '').trim()
    const hasCommittedItem = String(
      raw?.hasCommittedItem ?? '',
    ).trim()
    if (!gearSlots.includes(slot) || Object.hasOwn(result, slot)) {
      throw new Error(`invalid or duplicate committed gear slot ${slot || 'empty'}`)
    }
    if (
      hasCommittedItem !== 'true'
      && hasCommittedItem !== 'false'
    ) {
      throw new Error(
        `committed item presence marker is invalid for ${slot}`,
      )
    }
    if (hasCommittedItem === 'false') continue
    if (!itemId || itemId === 'empty') {
      throw new Error(
        `committed item identity is missing for ${slot}`,
      )
    }
    result[slot] = itemId
  }
  return result
}

function selectCandidateApplySlot(slots, preferredSlot) {
  const preferred = String(preferredSlot ?? '').trim()
  const candidates = (Array.isArray(slots) ? slots : []).filter((item) => (
    gearSlots.includes(String(item?.slot ?? ''))
    && Number.isInteger(Number(item?.expectedItems))
    && Number(item.expectedItems) > 0
  ))
  const selected = candidates.find((item) => item.slot === preferred) ?? candidates[0]
  if (!selected) throw new Error('no inspected slot with candidates is available for apply verification')
  return {
    slot: selected.slot,
    preferredSlot: preferred,
    usedFallback: selected.slot !== preferred,
  }
}

function selectCraftedApplyTarget(
  targets,
  currentSlotIdentities,
  excludedItemIds = [],
  preferredIndex = 0,
) {
  const candidates = (Array.isArray(targets) ? targets : []).filter((target) => (
    gearSlots.includes(String(target?.slot ?? ''))
    && String(target?.itemId ?? '').trim()
    && String(target?.variantKey ?? '').trim()
    && String(target?.craftedOptionId ?? '').trim()
  ))
  const excluded = new Set(
    (Array.isArray(excludedItemIds) ? excludedItemIds : [])
      .map((itemId) => String(itemId ?? '').trim())
      .filter(Boolean),
  )
  const offset = candidates.length > 0
    ? ((Number(preferredIndex) % candidates.length) + candidates.length) % candidates.length
    : 0
  const rotated = candidates.slice(offset).concat(candidates.slice(0, offset))
  const selected = rotated.find((target) => {
    const itemId = String(target.itemId)
    const current = currentSlotIdentities?.[target.slot] ?? {}
    return (
      !excluded.has(itemId)
      && itemId !== String(current.committedItemId ?? '')
      && itemId !== String(current.resolvedItemId ?? '')
    )
  })
  if (!selected) {
    throw new Error('no cross-item crafted stat apply target differs from the current slot identity')
  }
  return selected
}

function assertRuntimeBuildIdentity(runtime, build) {
  const actualGitHead = String(runtime?.gitHead ?? '').trim()
  const actualSourceHash = String(runtime?.sourceHash ?? '').trim()
  const expectedGitHead = normalizeSelectorMarker(build?.gitHead ?? '')
  const expectedSourceHash = normalizeSelectorMarker(build?.sourceHash ?? '')
  if (!actualGitHead || !actualSourceHash) {
    throw new Error('WeChat runtime build identity is missing')
  }
  if (actualGitHead !== expectedGitHead || actualSourceHash !== expectedSourceHash) {
    throw new Error(
      `WeChat runtime build identity mismatch: expected=${expectedGitHead}/${expectedSourceHash} actual=${actualGitHead}/${actualSourceHash}`,
    )
  }
  return {
    gitHead: actualGitHead,
    sourceHash: actualSourceHash,
  }
}

function normalizeSpecMatrix(home) {
  const classOptions = Array.isArray(home?.classOptions) ? home.classOptions : []
  if (classOptions.length !== 13) {
    throw new Error(`expected 13 classes, received ${classOptions.length}`)
  }
  const specs = classOptions.flatMap((classItem) => {
    const classKey = String(classItem?.websimClassKey ?? '')
    if (!classKey) throw new Error(`class ${classItem?.name ?? 'unknown'} is missing websimClassKey`)
    const specializations = Array.isArray(classItem?.specializations) ? classItem.specializations : []
    return specializations.map((spec) => {
      const specId = String(spec?.id ?? '')
      const specKey = String(spec?.websimSpecKey ?? '')
      if (!specId || !specKey) throw new Error(`class ${classKey} has an incomplete specialization identity`)
      if (String(spec?.websimClassKey ?? classKey) !== classKey) {
        throw new Error(`spec ${specId} class identity does not match ${classKey}`)
      }
      return {
        classKey,
        className: String(classItem?.name ?? classKey),
        specId,
        specKey,
        specName: String(spec?.name ?? specKey),
      }
    })
  })
  if (specs.length !== 40) throw new Error(`expected 40 specs, received ${specs.length}`)
  const specIds = specs.map((item) => item.specId)
  if (new Set(specIds).size !== specIds.length) throw new Error('duplicate spec id in 40-spec matrix')
  const compoundKeys = specs.map((item) => `${item.classKey}/${item.specKey}`)
  if (new Set(compoundKeys).size !== compoundKeys.length) {
    throw new Error('duplicate class/spec API identity in 40-spec matrix')
  }
  return specs
}

function normalizeSimcPolicy(options, specs) {
  if (options?.contractRevision !== 'simc-options-v1' || options?.status !== 'ready') {
    throw new Error('SimC options contract is not ready')
  }
  const policy = options?.specializationPolicy
  if (
    policy?.contractRevision !== 'simc-execution-support-v1'
    || policy?.status !== 'ready'
    || policy?.supportedSpecCount !== 26
    || policy?.unsupportedSpecCount !== 14
  ) {
    throw new Error('SimC specialization policy is not the required 26/14 ready contract')
  }
  const expectedSpecializations = new Set(
    specs.map((spec) => `${spec.classKey}:${spec.specKey}`),
  )
  const rows = Array.isArray(policy?.unsupportedSpecializations)
    ? policy.unsupportedSpecializations
    : []
  const unsupportedSpecializations = new Set()
  for (const row of rows) {
    const specializationId = String(row?.specializationId ?? '')
    if (
      !expectedSpecializations.has(specializationId)
      || row?.code !== 'SIMC_SPECIALIZATION_UNSUPPORTED'
      || unsupportedSpecializations.has(specializationId)
    ) {
      throw new Error(`invalid SimC unsupported specialization policy row ${specializationId || 'empty'}`)
    }
    unsupportedSpecializations.add(specializationId)
  }
  if (
    unsupportedSpecializations.size !== 14
    || expectedSpecializations.size - unsupportedSpecializations.size !== 26
  ) {
    throw new Error('SimC specialization policy does not cover the exact 40-spec matrix')
  }
  return {
    contractRevision: policy.contractRevision,
    supportedSpecCount: 26,
    unsupportedSpecCount: 14,
    unsupportedSpecializations,
  }
}

function summarizeWechatGearMatrix(results, expectedSpecs, phase = 'full') {
  const preview = phase === 'preview_catalog_actions'
  if (!preview && phase !== 'full') throw new Error(`unsupported WeChat gear matrix phase ${phase}`)
  const reasonCodes = new Set()
  const expectedSpecIds = new Set(expectedSpecs.map((item) => item.specId))
  const actualSpecIds = new Set(results.map((item) => item.specId))
  if (
    results.length !== expectedSpecs.length
    || actualSpecIds.size !== results.length
    || [...expectedSpecIds].some((specId) => !actualSpecIds.has(specId))
  ) reasonCodes.add('missing_spec_checks')

  let slotChecks = 0
  let actionChecks = 0
  for (const result of results) {
    if (result?.status !== (preview ? 'PREVIEW_PASS' : 'PASS')) {
      reasonCodes.add('spec_result_failed')
    }
    const slots = Array.isArray(result?.slots) ? result.slots : []
    slotChecks += slots.length
    const slotKeys = new Set(slots.map((item) => item.slot))
    if (
      slots.length !== gearSlots.length
      || slotKeys.size !== gearSlots.length
      || gearSlots.some((slot) => !slotKeys.has(slot))
    ) reasonCodes.add('missing_slot_checks')
    for (const slot of slots) {
      if (
        slot.status !== 'PASS'
        || slot.expectedItems !== slot.actualItems
        || slot.expectedVariants !== slot.actualVariants
      ) reasonCodes.add('catalog_surface_mismatch')
      if (
        slot.candidateRowFactChecks !== slot.expectedItems
        || slot.candidateMediaChecks !== slot.expectedItems
        || slot.candidateDetailFactChecks !== slot.expectedItems
        || slot.variantDisplayFactChecks !== slot.expectedVariants
        || slot.selectedVariantFactChecks !== slot.expectedSelectableVariants
      ) reasonCodes.add('visible_fact_matrix_incomplete')
    }
    for (const action of requiredActions) {
      actionChecks += 1
      const actionStatus = result?.actions?.[action]
      if (
        actionStatus !== 'PASS'
        && !(
          preview
          && action === 'simcExecutionOrPolicyBlock'
          && actionStatus === 'NOT_RUN_PREVIEW_TRUST_BOUNDARY'
        )
      ) reasonCodes.add('action_matrix_incomplete')
    }
  }

  const classCount = new Set(expectedSpecs.map((item) => item.classKey)).size
  if (
    expectedSpecs.length !== 40
    || classCount !== 13
    || slotChecks !== 40 * gearSlots.length
  ) reasonCodes.add('topology_incomplete')

  return {
    status: reasonCodes.size === 0 ? 'PASS' : 'FAIL',
    classes: classCount,
    specs: results.length,
    slotChecks,
    actionChecks,
    reasonCodes: [...reasonCodes].sort(),
  }
}

function sameStringSet(actualValues, expectedValues) {
  const actual = [...new Set((actualValues ?? []).map(String))].sort()
  const expected = [...new Set((expectedValues ?? []).map(String))].sort()
  return JSON.stringify(actual) === JSON.stringify(expected)
}

function summarizeWechatGearClassReportsForPhase(
  reports,
  expectedSpecs,
  expectedBuild,
  phase,
) {
  const preview = phase === 'preview_catalog_actions'
  if (!preview && phase !== 'full') throw new Error(`unsupported WeChat gear matrix phase ${phase}`)
  const reasonCodes = new Set()
  const expectedByClass = new Map()
  for (const spec of expectedSpecs) {
    if (!expectedByClass.has(spec.classKey)) expectedByClass.set(spec.classKey, [])
    expectedByClass.get(spec.classKey).push(spec)
  }
  const expectedRuntimeIdentity = {
    gitHead: normalizeSelectorMarker(expectedBuild?.gitHead ?? ''),
    sourceHash: normalizeSelectorMarker(expectedBuild?.sourceHash ?? ''),
  }
  const reportClasses = reports.map((report) => String(report?.scope?.classKey ?? ''))
  if (
    reports.length !== 13
    || new Set(reportClasses).size !== 13
    || !sameStringSet(reportClasses, [...expectedByClass.keys()])
  ) reasonCodes.add('class_reports_incomplete')

  const results = []
  let itemChecks = 0
  let variantChecks = 0
  let itemProgressionRelations = 0
  let candidateRowFactChecks = 0
  let candidateMediaChecks = 0
  let candidateDetailFactChecks = 0
  let variantDisplayFactChecks = 0
  let expectedSelectableVariants = 0
  let selectedVariantFactChecks = 0
  let craftedOptionFactChecks = 0
  let selectedCraftedOptionFactChecks = 0
  const distinctItems = new Set()
  const distinctVariants = new Set()
  const applySlots = new Set()
  const craftedApplySlots = new Set()
  const craftedApplyItems = new Set()
  const craftedApplyOptions = new Set()
  const preferredEnhancementKinds = new Set()
  const requestedEnhancementKinds = new Set()
  const appliedEnhancementKinds = new Set()
  let talentTemplatesPrepared = 0
  let talentTemplatesPolicyNotRequired = 0
  let simcExecuted = 0
  let simcPolicyBlocked = 0
  let simcFormalRequired = 0
  const apiIdentityVectors = new Set()
  const apiIdentityFields = [
    'manifestRevision',
    'gearCatalogRevision',
    'gearExactRegistryRevision',
    'gearCatalogReleaseId',
    'communityTemplateReleaseId',
    'pointerGeneration',
  ]

  for (const report of reports) {
    const classKey = String(report?.scope?.classKey ?? '')
    const classSpecs = expectedByClass.get(classKey) ?? []
    const classSpecIds = classSpecs.map((item) => item.specId)
    const reportResults = Array.isArray(report?.results) ? report.results : []
    if (
      report?.kind !== 'wechat-gear-class-matrix'
      || report?.status !== (preview ? 'PREVIEW_CATALOG_ACTIONS_PASS' : 'PASS')
    ) {
      reasonCodes.add('class_report_failed')
    }
    if (report?.scope?.diagnosticActionOnly === true) reasonCodes.add('diagnostic_report_present')
    if (
      preview
      && (
        report?.scope?.phase !== 'preview_catalog_actions'
        || report?.scope?.formalManifestRequiredForSkippedSimc !== true
      )
    ) reasonCodes.add('preview_trust_boundary_missing')
    if (
      !sameStringSet(report?.scope?.expectedSpecs, classSpecIds)
      || !sameStringSet(report?.scope?.expectedSlotsPerSpec, gearSlots)
      || !sameStringSet(reportResults.map((item) => item?.specId), classSpecIds)
    ) reasonCodes.add('class_report_scope_mismatch')
    if (
      String(report?.runtime?.build?.gitHead ?? '') !== String(expectedBuild?.gitHead ?? '')
      || String(report?.runtime?.build?.sourceHash ?? '') !== String(expectedBuild?.sourceHash ?? '')
    ) reasonCodes.add('runtime_build_mismatch')

    let unsupportedSpecializations = new Set()
    if (preview) {
      const apiIdentity = Object.fromEntries(
        apiIdentityFields.map((field) => [field, report?.runtime?.apiIdentity?.[field]]),
      )
      if (
        apiIdentityFields.some((field) => (
          field === 'pointerGeneration'
            ? !Number.isInteger(Number(apiIdentity[field]))
            : !String(apiIdentity[field] ?? '').trim()
        ))
      ) {
        reasonCodes.add('api_identity_incomplete')
      } else {
        apiIdentityVectors.add(JSON.stringify(apiIdentity))
      }
      const policy = report?.runtime?.simcPolicy
      unsupportedSpecializations = new Set(
        Array.isArray(policy?.unsupportedSpecializations)
          ? policy.unsupportedSpecializations.map(String)
          : [],
      )
      if (
        policy?.contractRevision !== 'simc-execution-support-v1'
        || Number(policy?.supportedSpecCount) !== 26
        || Number(policy?.unsupportedSpecCount) !== 14
        || unsupportedSpecializations.size !== 14
      ) reasonCodes.add('simc_policy_identity_invalid')
    }

    let reportSlotChecks = 0
    let reportItemProgressionRelations = 0
    let reportCandidateRowFactChecks = 0
    let reportCandidateMediaChecks = 0
    let reportCandidateDetailFactChecks = 0
    let reportVariantDisplayFactChecks = 0
    let reportExpectedSelectableVariants = 0
    let reportSelectedVariantFactChecks = 0
    let reportCraftedOptionFactChecks = 0
    let reportSelectedCraftedOptionFactChecks = 0
    for (const result of reportResults) {
      results.push(result)
      const runtimeIdentity = result?.runtimeBuildIdentity ?? {}
      if (
        runtimeIdentity.gitHead !== expectedRuntimeIdentity.gitHead
        || runtimeIdentity.sourceHash !== expectedRuntimeIdentity.sourceHash
      ) reasonCodes.add('runtime_build_mismatch')
      const slots = Array.isArray(result?.slots) ? result.slots : []
      reportSlotChecks += slots.length
      for (const slot of slots) {
        const expectedItems = Number(slot?.expectedItems)
        const expectedVariants = Number(slot?.expectedVariants)
        if (!Number.isInteger(expectedItems) || expectedItems < 0) {
          reasonCodes.add('cross_equipment_counts_invalid')
        } else {
          itemChecks += expectedItems
        }
        if (!Number.isInteger(expectedVariants) || expectedVariants < 0) {
          reasonCodes.add('cross_equipment_counts_invalid')
        } else {
          variantChecks += expectedVariants
        }
        const relations = Array.isArray(slot?.itemRelations) ? slot.itemRelations : []
        reportItemProgressionRelations += relations.length
        itemProgressionRelations += relations.length
        const visibleCounts = [
          ['candidateRowFactChecks', expectedItems],
          ['candidateMediaChecks', expectedItems],
          ['candidateDetailFactChecks', expectedItems],
          ['variantDisplayFactChecks', expectedVariants],
        ]
        for (const [field, expected] of visibleCounts) {
          const value = Number(slot?.[field])
          if (!Number.isInteger(value) || value !== expected) {
            reasonCodes.add('visible_fact_matrix_incomplete')
          }
        }
        const selectableVariants = Number(slot?.expectedSelectableVariants)
        const selectedFacts = Number(slot?.selectedVariantFactChecks)
        if (
          !Number.isInteger(selectableVariants)
          || selectableVariants < 0
          || !Number.isInteger(selectedFacts)
          || selectedFacts !== selectableVariants
          || selectableVariants > expectedVariants
        ) reasonCodes.add('visible_fact_matrix_incomplete')
        const craftedFacts = Number(slot?.craftedOptionFactChecks)
        const selectedCraftedFacts = Number(
          slot?.selectedCraftedOptionFactChecks,
        )
        if (
          !Number.isInteger(craftedFacts)
          || craftedFacts < 0
          || !Number.isInteger(selectedCraftedFacts)
          || selectedCraftedFacts !== craftedFacts
        ) reasonCodes.add('crafted_stat_visible_fact_matrix_incomplete')
        reportCandidateRowFactChecks += Number(slot?.candidateRowFactChecks) || 0
        reportCandidateMediaChecks += Number(slot?.candidateMediaChecks) || 0
        reportCandidateDetailFactChecks += Number(slot?.candidateDetailFactChecks) || 0
        reportVariantDisplayFactChecks += Number(slot?.variantDisplayFactChecks) || 0
        reportExpectedSelectableVariants += selectableVariants || 0
        reportSelectedVariantFactChecks += selectedFacts || 0
        candidateRowFactChecks += Number(slot?.candidateRowFactChecks) || 0
        candidateMediaChecks += Number(slot?.candidateMediaChecks) || 0
        candidateDetailFactChecks += Number(slot?.candidateDetailFactChecks) || 0
        variantDisplayFactChecks += Number(slot?.variantDisplayFactChecks) || 0
        expectedSelectableVariants += selectableVariants || 0
        selectedVariantFactChecks += selectedFacts || 0
        reportCraftedOptionFactChecks += craftedFacts || 0
        reportSelectedCraftedOptionFactChecks += selectedCraftedFacts || 0
        craftedOptionFactChecks += craftedFacts || 0
        selectedCraftedOptionFactChecks += selectedCraftedFacts || 0
        for (const relation of relations) {
          const itemId = String(relation?.itemId ?? '')
          const variantKey = String(relation?.variantKey ?? '')
          if (itemId) distinctItems.add(itemId)
          if (itemId && variantKey) distinctVariants.add(`${itemId}/${variantKey}`)
        }
      }
      const applySlot = String(result?.actionEvidence?.candidateApplyResolve?.slot ?? '')
      const craftedEvidence = (
        result?.actionEvidence?.craftedStatApplyResolve ?? {}
      )
      const craftedSlot = String(craftedEvidence.slot ?? '')
      const craftedItemId = String(craftedEvidence.itemId ?? '')
      const craftedVariantKey = String(craftedEvidence.variantKey ?? '')
      const craftedOptionId = String(craftedEvidence.craftedOptionId ?? '')
      if (
        craftedEvidence.status !== 'PASS'
        || !gearSlots.includes(craftedSlot)
        || !craftedItemId
        || !craftedVariantKey
        || !craftedOptionId
        || craftedEvidence.committedCraftedOptionId !== craftedOptionId
        || craftedEvidence.resolvedCraftedOptionId !== craftedOptionId
      ) {
        reasonCodes.add('crafted_stat_apply_resolve_incomplete')
      } else {
        craftedApplySlots.add(craftedSlot)
        craftedApplyItems.add(craftedItemId)
        craftedApplyOptions.add(craftedOptionId)
      }
      const enhancementEvidence = result?.actionEvidence?.enhancementEditResolve ?? {}
      const preferredKind = String(
        enhancementEvidence.preferredKind
        ?? enhancementEvidence.requestedKind
        ?? '',
      )
      const requestedKind = String(enhancementEvidence.requestedKind ?? '')
      const appliedKind = String(enhancementEvidence.appliedKind ?? '')
      if (applySlot) applySlots.add(applySlot)
      if (preferredKind) preferredEnhancementKinds.add(preferredKind)
      if (requestedKind) requestedEnhancementKinds.add(requestedKind)
      if (appliedKind) appliedEnhancementKinds.add(appliedKind)
      if (requestedKind !== appliedKind) {
        reasonCodes.add('enhancement_fallback_unproven')
      }
      if (preferredKind && preferredKind !== appliedKind) {
        const unavailable = Array.isArray(enhancementEvidence.unavailableBeforeApply)
          ? enhancementEvidence.unavailableBeforeApply
          : []
        const preferredUnavailable = unavailable.some((entry) => (
          String(entry?.kind ?? '') === preferredKind
          && ['control_missing', 'control_disabled'].includes(String(entry?.reason ?? ''))
        ))
        if (
          enhancementEvidence.fallbackUsed !== true
          || !preferredUnavailable
        ) reasonCodes.add('enhancement_fallback_unproven')
      }
      const talentPreparation = result?.actionEvidence?.talentTemplatePreparation ?? {}
      const simcEvidence = result?.actionEvidence?.simcExecutionOrPolicyBlock ?? {}
      const specializationId = `${String(result?.classKey ?? '')}:${String(result?.specKey ?? '')}`
      if (
        simcEvidence.status === 'PASS'
        && simcEvidence.mode === 'executed'
        && String(simcEvidence.taskId ?? '')
        && simcEvidence.terminalResult === 'completed'
        && simcEvidence.taskListVisible === true
      ) {
        if (preview) reasonCodes.add('preview_formal_boundary_violated')
        if (
          talentPreparation.status === 'PASS'
          && talentPreparation.mode === 'prepared'
          && talentPreparation.communityImported === true
          && talentPreparation.templatePersisted === true
        ) {
          talentTemplatesPrepared += 1
          simcExecuted += 1
        } else {
          reasonCodes.add('simc_input_preparation_incomplete')
        }
      } else if (
        simcEvidence.status === 'PASS'
        && simcEvidence.mode === 'policy_blocked'
        && simcEvidence.blockerCode === 'SIMC_SPECIALIZATION_UNSUPPORTED'
        && simcEvidence.taskCreated === false
      ) {
        if (preview && !unsupportedSpecializations.has(specializationId)) {
          reasonCodes.add('simc_policy_identity_invalid')
        }
        if (
          talentPreparation.status === 'PASS'
          && talentPreparation.mode === 'policy_not_required'
          && talentPreparation.specializationUnsupported === true
        ) {
          talentTemplatesPolicyNotRequired += 1
          simcPolicyBlocked += 1
        } else {
          reasonCodes.add('simc_input_preparation_incomplete')
        }
      } else if (
        preview
        && simcEvidence.status === 'NOT_RUN_PREVIEW_TRUST_BOUNDARY'
        && simcEvidence.mode === 'preview_requires_formal_manifest'
        && simcEvidence.formalActiveManifestRequired === true
      ) {
        if (unsupportedSpecializations.has(specializationId)) {
          reasonCodes.add('simc_policy_identity_invalid')
        }
        if (
          talentPreparation.status === 'PASS'
          && talentPreparation.mode === 'prepared'
          && talentPreparation.communityImported === true
          && talentPreparation.templatePersisted === true
        ) {
          talentTemplatesPrepared += 1
          simcFormalRequired += 1
        } else {
          reasonCodes.add('simc_input_preparation_incomplete')
        }
      } else {
        reasonCodes.add('simc_matrix_incomplete')
      }
    }
    if (
      Number(report?.totals?.specsExpected) !== classSpecs.length
      || Number(report?.totals?.specsExecuted) !== reportResults.length
      || Number(report?.totals?.specsPassed) !== reportResults.filter(
        (item) => item?.status === (preview ? 'PREVIEW_PASS' : 'PASS'),
      ).length
      || Number(report?.totals?.slotChecks) !== reportSlotChecks
      || Number(report?.totals?.itemProgressionRelations) !== reportItemProgressionRelations
      || Number(report?.totals?.candidateRowFactChecks) !== reportCandidateRowFactChecks
      || Number(report?.totals?.candidateMediaChecks) !== reportCandidateMediaChecks
      || Number(report?.totals?.candidateDetailFactChecks) !== reportCandidateDetailFactChecks
      || Number(report?.totals?.variantDisplayFactChecks) !== reportVariantDisplayFactChecks
      || Number(report?.totals?.expectedSelectableVariants) !== reportExpectedSelectableVariants
      || Number(report?.totals?.selectedVariantFactChecks) !== reportSelectedVariantFactChecks
      || Number(report?.totals?.craftedOptionFactChecks) !== reportCraftedOptionFactChecks
      || Number(report?.totals?.selectedCraftedOptionFactChecks) !== reportSelectedCraftedOptionFactChecks
    ) reasonCodes.add('class_report_totals_mismatch')
  }

  const matrix = summarizeWechatGearMatrix(results, expectedSpecs, phase)
  matrix.reasonCodes.forEach((reasonCode) => reasonCodes.add(reasonCode))
  if (
    itemChecks <= matrix.slotChecks
    || variantChecks < itemChecks
    || itemProgressionRelations !== variantChecks
    || distinctItems.size < 2
    || distinctVariants.size < 2
  ) reasonCodes.add('cross_equipment_coverage_incomplete')
  if (
    !sameStringSet([...applySlots], ['head', 'main_hand', 'trinket1'])
    || !sameStringSet([...preferredEnhancementKinds], ['socket', 'enchant', 'embellishment'])
    || !sameStringSet([...requestedEnhancementKinds], ['socket', 'enchant', 'embellishment'])
    || !sameStringSet([...appliedEnhancementKinds], ['socket', 'enchant', 'embellishment'])
  ) reasonCodes.add('cross_action_coverage_incomplete')
  if (
    craftedOptionFactChecks <= 0
    || craftedOptionFactChecks !== selectedCraftedOptionFactChecks
    || craftedApplySlots.size < 8
    || craftedApplyItems.size < 20
    || craftedApplyOptions.size < 10
  ) reasonCodes.add('crafted_stat_cross_coverage_incomplete')
  if (preview) {
    if (
      simcExecuted !== 0
      || simcFormalRequired !== 26
      || simcPolicyBlocked !== 14
    ) reasonCodes.add('simc_matrix_incomplete')
    if (
      talentTemplatesPrepared !== 26
      || talentTemplatesPolicyNotRequired !== 14
    ) reasonCodes.add('simc_input_preparation_incomplete')
    if (apiIdentityVectors.size !== 1) reasonCodes.add('api_identity_mismatch')
  } else {
    if (simcExecuted !== 26 || simcPolicyBlocked !== 14) {
      reasonCodes.add('simc_matrix_incomplete')
    }
    if (
      talentTemplatesPrepared !== 26
      || talentTemplatesPolicyNotRequired !== 14
    ) {
      reasonCodes.add('simc_input_preparation_incomplete')
    }
  }

  return {
    ...matrix,
    status: reasonCodes.size === 0
      ? preview ? 'PREVIEW_CATALOG_ACTIONS_PASS' : 'PASS'
      : 'FAIL',
    phase,
    itemChecks,
    variantChecks,
    itemProgressionRelations,
    candidateRowFactChecks,
    candidateMediaChecks,
    candidateDetailFactChecks,
    variantDisplayFactChecks,
    expectedSelectableVariants,
    selectedVariantFactChecks,
    craftedOptionFactChecks,
    selectedCraftedOptionFactChecks,
    distinctItems: distinctItems.size,
    distinctVariants: distinctVariants.size,
    applySlots: [...applySlots].sort(),
    craftedApplySlots: [...craftedApplySlots].sort(),
    craftedApplyItems: craftedApplyItems.size,
    craftedApplyOptions: [...craftedApplyOptions].sort(),
    preferredEnhancementKinds: [...preferredEnhancementKinds].sort(),
    requestedEnhancementKinds: [...requestedEnhancementKinds].sort(),
    appliedEnhancementKinds: [...appliedEnhancementKinds].sort(),
    talentTemplatesPrepared,
    talentTemplatesPolicyNotRequired,
    simcExecuted,
    simcPolicyBlocked,
    simcFormalRequired,
    apiIdentityCount: apiIdentityVectors.size,
    reasonCodes: [...reasonCodes].sort(),
  }
}

function summarizeWechatGearClassReports(reports, expectedSpecs, expectedBuild) {
  return summarizeWechatGearClassReportsForPhase(
    reports,
    expectedSpecs,
    expectedBuild,
    'full',
  )
}

function summarizeWechatGearPreviewClassReports(reports, expectedSpecs, expectedBuild) {
  return summarizeWechatGearClassReportsForPhase(
    reports,
    expectedSpecs,
    expectedBuild,
    'preview_catalog_actions',
  )
}

module.exports = {
  assertRuntimeBuildIdentity,
  gearSlots,
  normalizeCandidateDisplayRelations,
  normalizeCommittedGearEntries,
  normalizeSelectorMarker,
  normalizeSimcPolicy,
  normalizeSpecMatrix,
  normalizeTaskIds,
  requiredActions,
  selectCandidateApplySlot,
  selectCraftedApplyTarget,
  storageValueChanged,
  summarizeWechatGearClassReports,
  summarizeWechatGearMatrix,
  summarizeWechatGearPreviewClassReports,
}
