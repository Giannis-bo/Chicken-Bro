const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')

const workbench = require('../pages/builds/gear-workbench-state')
const { serializeGearSelectionIntent } = require('../pages/builds/gear-selection-intent')

function intent(revision = 'gear-r17') {
  return {
    schemaRevision: 'selection-intent-v1',
    authoredAgainst: {
      seasonRevision: 'season-17',
      gearCatalogRevision: revision
    },
    eligibilityContext: {
      classKey: 'mage',
      specKey: 'arcane',
      level: 90
    },
    slots: {
      head: {
        itemId: '250060',
        variantKey: 'variant-head',
        gemOptionIds: [],
        enchantOptionId: '',
        embellishmentOptionId: '',
        craftedOptionId: '',
        catalystOptionId: ''
      }
    }
  }
}

function resolverContext() {
  return {
    selectionSchemaRevision: 'selection-intent-v1',
    authoredAgainst: {
      seasonRevision: 'season-17',
      gearCatalogRevision: 'gear-r17'
    }
  }
}

function snapshot(signature = 'resolved-1') {
  return {
    contractRevision: 'gear-resolved-snapshot-v1',
    status: 'verified',
    resolvedGearSignature: signature,
    aggregateLegality: { status: 'verified', problemCodes: [] },
    staticAttributes: { totals: { intellect: 100 } },
    setState: { itemSetCounts: { '1983': 1 } },
    constraints: { embellishmentCount: 0 },
    profileReadiness: { status: 'verified', simcReady: true },
    problems: []
  }
}

function envelope(status, data, problems, releaseContext) {
  return {
    contractRevision: 'gear-result-envelope-v1',
    requestId: `request-${status}`,
    status,
    releaseContext: releaseContext || {},
    data: data || {},
    problems: problems || []
  }
}

function transport(payload, httpStatus = 200) {
  return {
    payload,
    fromFallback: false,
    error: '',
    httpStatus,
    transportError: '',
    offline: false
  }
}

function resolveVerified(state, signature) {
  const pending = workbench.beginGearResolve(state)
  return workbench.applyGearResolveResult(
    pending.state,
    pending.request,
    transport(envelope('resolved', snapshot(signature)))
  )
}

test('Selection Intent serializer emits only client-owned identifiers from backend context', () => {
  const selectedGearBySlot = {
    head: {
      slot: 'head',
      itemId: '250060',
      variantKey: 'variant-head',
      displayName: 'forged name',
      itemStats: { intellect: 999999 },
      statSummary: '智力 999999',
      itemSetName: 'forged set',
      simcReady: true,
      legality: { status: 'verified' }
    }
  }
  const enhancementBySlot = {
    head: {
      socketOptionId: 'gem-haste',
      enchantOptionId: 'enchant-head',
      embellishmentOptionId: 'embellishment-head',
      craftedOptionId: 'crafted-head',
      catalystOptionId: 'catalyst-head',
      gem_id: 'forged-simc-gem',
      enchant_id: 'forged-simc-enchant'
    }
  }

  assert.deepEqual(
    serializeGearSelectionIntent({
      resolverContext: {
        contractRevision: 'gear-resolver-context-v1',
        selectionSchemaRevision: 'selection-intent-v1',
        authoredAgainst: {
          seasonRevision: 'season-17',
          gearCatalogRevision: 'gear-r17'
        }
      },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      selectedGearBySlot,
      enhancementBySlot
    }),
    {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: {
        seasonRevision: 'season-17',
        gearCatalogRevision: 'gear-r17'
      },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {
        head: {
          itemId: '250060',
          variantKey: 'variant-head',
          gemOptionIds: ['gem-haste'],
          enchantOptionId: 'enchant-head',
          embellishmentOptionId: 'embellishment-head',
          craftedOptionId: 'crafted-head',
          catalystOptionId: 'catalyst-head'
        }
      }
    }
  )
})

test('gear selection intent preserves ordered duplicate gem option ids', () => {
  const selectionIntent = serializeGearSelectionIntent({
    resolverContext: {
      contractRevision: 'gear-resolver-context-v1',
      selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: {
        seasonRevision: 'season-17',
        gearCatalogRevision: 'gear-r17'
      }
    },
    eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
    selectedGearBySlot: {
      finger1: { slot: 'finger1', itemId: '250060', variantKey: 'variant-ring' }
    },
    enhancementBySlot: {
      finger1: { gemOptionIds: ['gem-haste', 'gem-haste', 'gem-mastery'] }
    }
  })
  const state = workbench.createGearWorkbenchState(resolverContext(), selectionIntent)
  const pending = workbench.beginGearResolve(state)

  assert.deepEqual(
    pending.request.selectionIntent.slots.finger1.gemOptionIds,
    ['gem-haste', 'gem-haste', 'gem-mastery']
  )
})

test('Selection Intent serializer fails closed when resolver context is incomplete', () => {
  assert.equal(serializeGearSelectionIntent({
    resolverContext: {
      selectionSchemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17' }
    },
    eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
    selectedGearBySlot: { head: { itemId: '250060' } }
  }), null)
})

test('draft edits preserve confirmed Intent and last verified snapshot until one confirm', () => {
  const initial = intent()
  const created = workbench.createGearWorkbenchState(resolverContext(), initial)
  const verified = resolveVerified(created, 'resolved-original')
  const before = JSON.parse(JSON.stringify(verified))

  const edited = workbench.editGearIntent(verified, (draft) => {
    draft.slots.head.itemId = '250061'
  })

  assert.equal(edited.draftIntent.slots.head.itemId, '250061')
  assert.equal(edited.confirmedIntent.slots.head.itemId, '250060')
  assert.equal(edited.lastVerifiedSnapshot.resolvedGearSignature, 'resolved-original')
  assert.deepEqual(verified, before)
  assert.equal(edited.resolveStatus, 'dirty')
  assert.equal(workbench.gearWorkbenchCanRunProfile(edited), false)

  const confirmed = workbench.confirmGearIntent(edited)
  const confirmedAgain = workbench.confirmGearIntent(confirmed)
  assert.equal(confirmed.confirmedIntent.slots.head.itemId, '250061')
  assert.equal(confirmed.intentVersion, edited.intentVersion + 1)
  assert.equal(confirmedAgain.intentVersion, confirmed.intentVersion)
  assert.deepEqual(confirmedAgain, confirmed)
})

test('begin resolve captures serial version and Intent while stale results are ignored by identity', () => {
  const initial = workbench.createGearWorkbenchState(resolverContext(), intent())
  const first = workbench.beginGearResolve(initial)
  const second = workbench.beginGearResolve(first.state)
  const staleSerial = workbench.applyGearResolveResult(
    second.state,
    first.request,
    transport(envelope('resolved', snapshot('stale-serial')))
  )
  assert.strictEqual(staleSerial, second.state)

  const edited = workbench.editGearIntent(second.state, (draft) => {
    draft.slots.head.itemId = '250062'
  })
  const confirmed = workbench.confirmGearIntent(edited)
  const staleVersion = workbench.applyGearResolveResult(
    confirmed,
    second.request,
    transport(envelope('resolved', snapshot('stale-version')))
  )
  assert.strictEqual(staleVersion, confirmed)
  assert.equal(second.request.serial, 2)
  assert.equal(second.request.intentVersion, 0)
  assert.deepEqual(second.request.selectionIntent, initial.confirmedIntent)
})

test('verified and blocked results keep current and last verified snapshots distinct', () => {
  const initial = workbench.createGearWorkbenchState(resolverContext(), intent())
  const verified = resolveVerified(initial, 'verified-1')
  assert.equal(verified.resolveStatus, 'verified')
  assert.equal(verified.currentSnapshot.resolvedGearSignature, 'verified-1')
  assert.equal(verified.lastVerifiedSnapshot.resolvedGearSignature, 'verified-1')
  assert.equal(workbench.gearWorkbenchCanUseVerifiedSnapshot(verified), true)
  assert.equal(workbench.gearWorkbenchCanRunProfile(verified), true)

  const edited = workbench.editGearIntent(verified, (draft) => {
    draft.slots.head.variantKey = 'blocked-variant'
  })
  const confirmed = workbench.confirmGearIntent(edited)
  const pending = workbench.beginGearResolve(confirmed)
  const problem = { kind: 'RULE_VIOLATION', code: 'GEAR_SLOT_NOT_ALLOWED' }
  const blockedSnapshot = {
    ...snapshot('blocked-current'),
    status: 'blocked',
    profileReadiness: { status: 'blocked', simcReady: false },
    problems: [problem]
  }
  const blocked = workbench.applyGearResolveResult(
    pending.state,
    pending.request,
    transport(envelope('blocked', blockedSnapshot, [problem]))
  )

  assert.equal(blocked.resolveStatus, 'blocked')
  assert.equal(blocked.currentSnapshot.status, 'blocked')
  assert.equal(blocked.lastVerifiedSnapshot.resolvedGearSignature, 'verified-1')
  assert.deepEqual(blocked.problems, [problem])
  assert.equal(workbench.gearWorkbenchCanUseVerifiedSnapshot(blocked), false)
  assert.equal(workbench.gearWorkbenchCanRunProfile(blocked), false)
})

test('409 preserves choices and permits exactly one revision-only rebase', () => {
  const initial = workbench.createGearWorkbenchState(resolverContext(), intent())
  const pending = workbench.beginGearResolve(initial)
  const conflictProblem = { kind: 'REVISION_CONFLICT', code: 'GEAR_CATALOG_REVISION_CONFLICT' }
  const conflicted = workbench.applyGearResolveResult(
    pending.state,
    pending.request,
    transport(envelope('blocked', {}, [conflictProblem], {
      seasonRevision: 'season-18',
      gearCatalogRevision: 'gear-r18'
    }), 409)
  )

  assert.equal(conflicted.resolveStatus, 'revision_conflict')
  assert.equal(conflicted.confirmedIntent.slots.head.itemId, '250060')
  const rebased = workbench.rebaseGearIntentRevisions(conflicted, {
    seasonRevision: 'season-18',
    gearCatalogRevision: 'gear-r18'
  })
  assert.equal(rebased.confirmedIntent.authoredAgainst.seasonRevision, 'season-18')
  assert.equal(rebased.confirmedIntent.authoredAgainst.gearCatalogRevision, 'gear-r18')
  assert.equal(rebased.confirmedIntent.slots.head.itemId, '250060')
  assert.equal(rebased.draftIntent.slots.head.itemId, '250060')
  assert.equal(rebased.revisionRetryCount, 1)
  assert.equal(rebased.intentVersion, 1)

  const retry = workbench.beginGearResolve(rebased)
  const secondConflict = workbench.applyGearResolveResult(
    retry.state,
    retry.request,
    transport(envelope('blocked', {}, [conflictProblem], {
      seasonRevision: 'season-19',
      gearCatalogRevision: 'gear-r19'
    }), 409)
  )
  const stopped = workbench.rebaseGearIntentRevisions(secondConflict, {
    seasonRevision: 'season-19',
    gearCatalogRevision: 'gear-r19'
  })
  assert.strictEqual(stopped, secondConflict)
  assert.equal(stopped.confirmedIntent.authoredAgainst.gearCatalogRevision, 'gear-r18')
  assert.equal(stopped.readOnly, true)
})

test('structured 503 is read-only but not offline while transport failure is offline', () => {
  const unavailableProblem = { kind: 'AUTHORITY_UNAVAILABLE', code: 'GEAR_AUTHORITY_READ_UNAVAILABLE' }
  const initial = workbench.createGearWorkbenchState(resolverContext(), intent())
  const first = workbench.beginGearResolve(initial)
  const unavailable = workbench.applyGearResolveResult(
    first.state,
    first.request,
    transport(envelope('unavailable', {}, [unavailableProblem]), 503)
  )
  assert.equal(unavailable.resolveStatus, 'unavailable')
  assert.equal(unavailable.readOnly, true)
  assert.equal(unavailable.offline, false)
  assert.deepEqual(unavailable.problems, [unavailableProblem])

  const retry = workbench.beginGearResolve(unavailable)
  const offline = workbench.applyGearResolveResult(retry.state, retry.request, {
    payload: null,
    fromFallback: true,
    error: 'request:fail timeout',
    httpStatus: 0,
    transportError: 'request:fail timeout',
    offline: true
  })
  assert.equal(offline.resolveStatus, 'offline')
  assert.equal(offline.readOnly, true)
  assert.equal(offline.offline, true)
  assert.equal(workbench.gearWorkbenchCanRunProfile(offline), false)
})

test('Resolver readiness never promotes the independent stat snapshot state', () => {
  const initial = workbench.createGearWorkbenchState(resolverContext(), intent())
  assert.equal(initial.statSnapshotStatus, 'idle')
  const verified = resolveVerified(initial, 'verified-no-stat')
  assert.equal(verified.resolveStatus, 'verified')
  assert.equal(verified.statSnapshotStatus, 'idle')
  assert.equal(verified.statSnapshotSignature, '')

  const withStat = {
    ...verified,
    statSnapshotStatus: 'verified',
    statSnapshotSignature: 'legacy-stat-signature'
  }
  const edited = workbench.editGearIntent(withStat, (draft) => {
    draft.slots.head.itemId = '250099'
  })
  const confirmed = workbench.confirmGearIntent(edited)
  assert.equal(confirmed.statSnapshotStatus, 'stale')
  assert.equal(confirmed.statSnapshotSignature, 'legacy-stat-signature')
})

test('async stat state polls 202 then accepts only a verified 200 snapshot', () => {
  const oldSnapshot = { statStatus: 'verified', primary: { value: '100' } }
  const initial = workbench.createGearStatSnapshotState(oldSnapshot, 'sha256:old')
  const begun = workbench.beginGearStatSnapshot(initial, {
    contextKey: 'intent-v1|race-human|single',
    selectionIntent: intent(),
    profileContext: { race: 'human', scenarioKey: 'single', talents: 'C4DA' }
  }, 1000)

  assert.equal(begun.state.statSnapshotStatus, 'requesting')
  assert.equal(begun.state.currentStatSnapshot, null)
  assert.deepEqual(begun.state.lastVerifiedStatSnapshot, oldSnapshot)
  assert.equal(begun.request.attempt, 1)

  const pending = workbench.applyGearStatSnapshotResult(
    begun.state,
    begun.request,
    transport(envelope('pending', { status: 'pending', retryAfterMs: 1500 }), 202),
    1100
  )
  assert.equal(pending.statSnapshotStatus, 'pending')
  assert.equal(pending.activeStatRequest.attempt, 2)
  assert.equal(pending.activeStatRequest.retryAfterMs, 1500)
  assert.deepEqual(pending.lastVerifiedStatSnapshot, oldSnapshot)

  const verifiedSnapshot = { statStatus: 'verified', primary: { value: '200' }, blockers: [] }
  const verified = workbench.applyGearStatSnapshotResult(
    pending,
    pending.activeStatRequest,
    transport(envelope('resolved', {
      statSignature: 'sha256:new',
      snapshotHash: 'sha256:snapshot',
      statSnapshot: verifiedSnapshot
    }), 200),
    2700
  )
  assert.equal(verified.statSnapshotStatus, 'verified')
  assert.equal(verified.statSnapshotSignature, 'sha256:new')
  assert.deepEqual(verified.currentStatSnapshot, verifiedSnapshot)
  assert.deepEqual(verified.lastVerifiedStatSnapshot, verifiedSnapshot)
  assert.equal(verified.activeStatRequest, null)
})

test('async stat state ignores stale identity and keeps the last verified snapshot read-only', () => {
  const oldSnapshot = { statStatus: 'verified', primary: { value: '100' } }
  const initial = workbench.createGearStatSnapshotState(oldSnapshot, 'sha256:old')
  const first = workbench.beginGearStatSnapshot(initial, {
    contextKey: 'intent-v1', selectionIntent: intent(), profileContext: { race: 'human' }
  }, 1000)
  const changed = workbench.beginGearStatSnapshot(first.state, {
    contextKey: 'intent-v2', selectionIntent: intent('gear-r18'), profileContext: { race: 'orc' }
  }, 1200)
  const stale = workbench.applyGearStatSnapshotResult(
    changed.state,
    first.request,
    transport(envelope('resolved', {
      statSignature: 'sha256:stale',
      statSnapshot: { statStatus: 'verified', primary: { value: '999' } }
    })),
    1300
  )
  assert.strictEqual(stale, changed.state)
  assert.equal(stale.statSnapshotStatus, 'requesting')
  assert.equal(stale.currentStatSnapshot, null)
  assert.deepEqual(stale.lastVerifiedStatSnapshot, oldSnapshot)

  const unavailable = workbench.applyGearStatSnapshotResult(
    stale,
    stale.activeStatRequest,
    transport(envelope('unavailable', {}, [{ code: 'GEAR_STAT_WORKER_UNAVAILABLE' }]), 503),
    1400
  )
  assert.equal(unavailable.statSnapshotStatus, 'unavailable')
  assert.equal(unavailable.currentStatSnapshot, null)
  assert.deepEqual(unavailable.lastVerifiedStatSnapshot, oldSnapshot)
  assert.equal(unavailable.readOnlyStatSnapshot, true)
})

test('async stat state caps polling at 15 attempts or 45 seconds and marks transport offline', () => {
  let current = workbench.beginGearStatSnapshot(
    workbench.createGearStatSnapshotState(),
    { contextKey: 'same', selectionIntent: intent(), profileContext: {} },
    1000
  )
  for (let attempt = 1; attempt < 15; attempt += 1) {
    const next = workbench.applyGearStatSnapshotResult(
      current.state,
      current.request,
      transport(envelope('pending', { status: 'pending', retryAfterMs: 999999 }), 202),
      1000 + attempt
    )
    current = { state: next, request: next.activeStatRequest }
  }
  const timedOut = workbench.applyGearStatSnapshotResult(
    current.state,
    current.request,
    transport(envelope('pending', { status: 'pending', retryAfterMs: 1500 }), 202),
    1020
  )
  assert.equal(timedOut.statSnapshotStatus, 'timed_out')
  assert.equal(timedOut.activeStatRequest, null)

  const duration = workbench.beginGearStatSnapshot(
    workbench.createGearStatSnapshotState(),
    { contextKey: 'duration', selectionIntent: intent(), profileContext: {} },
    1000
  )
  const durationTimeout = workbench.applyGearStatSnapshotResult(
    duration.state,
    duration.request,
    transport(envelope('pending', { status: 'pending', retryAfterMs: 1500 }), 202),
    46001
  )
  assert.equal(durationTimeout.statSnapshotStatus, 'timed_out')

  const nearDeadline = workbench.beginGearStatSnapshot(
    workbench.createGearStatSnapshotState(),
    { contextKey: 'near-deadline', selectionIntent: intent(), profileContext: {} },
    1000
  )
  const boundedDelay = workbench.applyGearStatSnapshotResult(
    nearDeadline.state,
    nearDeadline.request,
    transport(envelope('pending', { status: 'pending', retryAfterMs: 5000 }), 202),
    45900
  )
  assert.equal(boundedDelay.activeStatRequest.retryAfterMs, 100)

  const offlineStart = workbench.beginGearStatSnapshot(
    workbench.createGearStatSnapshotState(),
    { contextKey: 'offline', selectionIntent: intent(), profileContext: {} },
    0
  )
  const offline = workbench.applyGearStatSnapshotResult(offlineStart.state, offlineStart.request, {
    payload: null, fromFallback: true, error: 'request:fail timeout', offline: true
  }, 1)
  assert.equal(offline.statSnapshotStatus, 'offline')
  assert.equal(offline.statOffline, true)
  assert.equal(workbench.gearStatRequestTimeoutMs(duration.request, 1000), 30000)
  assert.equal(workbench.gearStatRequestTimeoutMs(duration.request, 32000), 14000)
  assert.equal(workbench.gearStatRequestTimeoutMs(duration.request, 999999), 1)
})

test('view is compact display-only and the module has no runtime dependencies', () => {
  const initialIntent = intent()
  const context = resolverContext()
  const beforeIntent = JSON.parse(JSON.stringify(initialIntent))
  const beforeContext = JSON.parse(JSON.stringify(context))
  const state = resolveVerified(
    workbench.createGearWorkbenchState(context, initialIntent),
    'verified-view'
  )
  const view = workbench.gearWorkbenchView(state)

  assert.deepEqual(initialIntent, beforeIntent)
  assert.deepEqual(context, beforeContext)
  assert.equal(view.resolveStatus, 'verified')
  assert.equal(view.resolvedGearSignature, 'verified-view')
  assert.equal(view.canRunProfile, true)
  assert.deepEqual(view.aggregateLegality, { status: 'verified', problemCodes: [] })
  assert.equal('confirmedIntent' in view, false)
  assert.equal('draftIntent' in view, false)
  assert.equal('currentSnapshot' in view, false)
  assert.equal('lastVerifiedSnapshot' in view, false)

  const source = fs.readFileSync('pages/builds/gear-workbench-state.js', 'utf8')
  assert.doesNotMatch(source, /\bwx\b|getStorage|setStorage|requestJson|Date\.|Date\(|setTimeout|require\(/)
})
