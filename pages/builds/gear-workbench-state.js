function clone(value) {
  if (value === undefined) return undefined
  return JSON.parse(JSON.stringify(value))
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical)
  if (!value || typeof value !== 'object') return value
  return Object.keys(value).sort().reduce((output, key) => {
    output[key] = canonical(value[key])
    return output
  }, {})
}

function sameValue(left, right) {
  return JSON.stringify(canonical(left)) === JSON.stringify(canonical(right))
}

function problemList(envelope) {
  if (envelope && Array.isArray(envelope.problems) && envelope.problems.length) {
    return clone(envelope.problems)
  }
  const data = envelope && envelope.data
  return clone(data && Array.isArray(data.problems) ? data.problems : [])
}

function validEnvelope(value) {
  return !!(
    value &&
    typeof value === 'object' &&
    value.contractRevision === 'gear-result-envelope-v1' &&
    typeof value.status === 'string' &&
    value.data &&
    typeof value.data === 'object' &&
    !Array.isArray(value.data) &&
    Array.isArray(value.problems)
  )
}

const GEAR_STAT_MAX_ATTEMPTS = 15
const GEAR_STAT_MAX_DURATION_MS = 45000
const GEAR_STAT_DEFAULT_RETRY_MS = 1500
const GEAR_STAT_MIN_RETRY_MS = 250
const GEAR_STAT_MAX_RETRY_MS = 5000

function createGearStatSnapshotState(initialSnapshot, statSignature) {
  const snapshot = initialSnapshot && typeof initialSnapshot === 'object' ? clone(initialSnapshot) : null
  return {
    latestStatSerial: 0,
    activeStatRequest: null,
    statSnapshotStatus: snapshot ? 'verified' : 'idle',
    statSnapshotSignature: snapshot ? String(statSignature || '') : '',
    verifiedStatContextKey: '',
    currentStatSnapshot: snapshot,
    lastVerifiedStatSnapshot: snapshot,
    statProblems: [],
    statOffline: false,
    readOnlyStatSnapshot: false
  }
}

function beginGearStatSnapshot(state, options, nowMs) {
  const next = clone(state || createGearStatSnapshotState())
  const source = options && typeof options === 'object' ? options : {}
  const startedAtMs = Number(nowMs) || 0
  const request = {
    serial: Number(next.latestStatSerial || 0) + 1,
    contextKey: String(source.contextKey || ''),
    selectionIntent: clone(source.selectionIntent || {}),
    profileContext: clone(source.profileContext || {}),
    attempt: 1,
    startedAtMs,
    deadlineAtMs: startedAtMs + GEAR_STAT_MAX_DURATION_MS,
    retryAfterMs: 0
  }
  next.latestStatSerial = request.serial
  next.activeStatRequest = clone(request)
  next.statSnapshotStatus = 'requesting'
  next.currentStatSnapshot = null
  next.statProblems = []
  next.statOffline = false
  next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
  return { state: next, request }
}

function statRequestMatches(state, request) {
  const active = state && state.activeStatRequest
  return !!(
    active && request &&
    Number(request.serial) === Number(state.latestStatSerial) &&
    Number(request.serial) === Number(active.serial) &&
    String(request.contextKey || '') === String(active.contextKey || '') &&
    Number(request.attempt) === Number(active.attempt)
  )
}

function retryDelay(value) {
  const delay = Number(value) || GEAR_STAT_DEFAULT_RETRY_MS
  return Math.min(GEAR_STAT_MAX_RETRY_MS, Math.max(GEAR_STAT_MIN_RETRY_MS, delay))
}

function gearStatRequestTimeoutMs(request, nowMs) {
  const deadline = Number(request && request.deadlineAtMs) || 0
  const remaining = deadline - (Number(nowMs) || 0)
  return Math.min(30000, Math.max(1, remaining))
}

function applyGearStatSnapshotResult(state, request, transportResult, nowMs) {
  if (!statRequestMatches(state, request)) return state
  const next = clone(state)
  const envelope = transportResult && transportResult.payload
  const now = Number(nowMs) || 0
  if (!transportResult || transportResult.fromFallback || !validEnvelope(envelope)) {
    next.activeStatRequest = null
    next.statSnapshotStatus = transportResult && transportResult.offline ? 'offline' : 'unavailable'
    next.currentStatSnapshot = null
    next.statProblems = [transportProblem(transportResult)]
    next.statOffline = !!(transportResult && transportResult.offline)
    next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
    return next
  }

  const httpStatus = Number(transportResult.httpStatus || 0)
  const problems = problemList(envelope)
  next.statProblems = problems
  next.statOffline = false

  if (httpStatus === 202 && envelope.status === 'pending') {
    if (Number(request.attempt) >= GEAR_STAT_MAX_ATTEMPTS || now >= Number(request.deadlineAtMs)) {
      next.activeStatRequest = null
      next.statSnapshotStatus = 'timed_out'
      next.currentStatSnapshot = null
      next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
      return next
    }
    const following = {
      ...clone(request),
      attempt: Number(request.attempt) + 1,
      retryAfterMs: Math.min(
        retryDelay(envelope.data && envelope.data.retryAfterMs),
        Math.max(1, Number(request.deadlineAtMs) - now)
      )
    }
    next.activeStatRequest = following
    next.statSnapshotStatus = 'pending'
    next.currentStatSnapshot = null
    next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
    return next
  }

  next.activeStatRequest = null
  next.currentStatSnapshot = null
  next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
  if (httpStatus === 409) {
    next.statSnapshotStatus = 'revision_conflict'
    return next
  }
  if (httpStatus === 503 || envelope.status === 'unavailable') {
    next.statSnapshotStatus = 'unavailable'
    return next
  }

  const data = envelope.data && typeof envelope.data === 'object' ? envelope.data : {}
  const snapshot = data.statSnapshot && typeof data.statSnapshot === 'object'
    ? clone(data.statSnapshot)
    : null
  if (
    httpStatus === 200 &&
    envelope.status === 'resolved' &&
    snapshot &&
    snapshot.statStatus === 'verified' &&
    problems.length === 0 &&
    String(data.statSignature || '')
  ) {
    next.statSnapshotStatus = 'verified'
    next.statSnapshotSignature = String(data.statSignature)
    next.verifiedStatContextKey = String(request.contextKey || '')
    next.currentStatSnapshot = snapshot
    next.lastVerifiedStatSnapshot = clone(snapshot)
    next.readOnlyStatSnapshot = false
    return next
  }
  next.statSnapshotStatus = envelope.status === 'blocked' ? 'blocked' : 'unavailable'
  return next
}

function invalidateGearStatSnapshot(state) {
  const next = clone(state || createGearStatSnapshotState())
  next.latestStatSerial = Number(next.latestStatSerial || 0) + 1
  next.activeStatRequest = null
  next.currentStatSnapshot = null
  next.statSnapshotStatus = next.lastVerifiedStatSnapshot ? 'stale' : 'idle'
  next.statProblems = []
  next.statOffline = false
  next.readOnlyStatSnapshot = !!next.lastVerifiedStatSnapshot
  return next
}

function createGearWorkbenchState(resolverContext, initialIntent) {
  const context = clone(resolverContext || {})
  const intent = clone(initialIntent || {})
  if (!intent.schemaRevision && context.selectionSchemaRevision) {
    intent.schemaRevision = context.selectionSchemaRevision
  }
  if (context.authoredAgainst && typeof context.authoredAgainst === 'object') {
    intent.authoredAgainst = {
      ...(intent.authoredAgainst || {}),
      ...clone(context.authoredAgainst)
    }
  }
  return {
    confirmedIntent: clone(intent),
    draftIntent: clone(intent),
    intentVersion: 0,
    latestResolveSerial: 0,
    resolveStatus: 'idle',
    activeRequest: null,
    currentSnapshot: null,
    lastVerifiedSnapshot: null,
    problems: [],
    offline: false,
    readOnly: false,
    revisionRetryCount: 0,
    ...createGearStatSnapshotState()
  }
}

function editGearIntent(state, updater) {
  const next = clone(state)
  const draft = clone(next.draftIntent || next.confirmedIntent || {})
  let updated = draft
  if (typeof updater === 'function') {
    const returned = updater(draft)
    if (returned && typeof returned === 'object') updated = returned
  } else if (updater && typeof updater === 'object') {
    updated = updater
  }
  next.draftIntent = clone(updated)
  next.resolveStatus = 'dirty'
  next.activeRequest = null
  next.problems = []
  return next
}

function confirmGearIntent(state) {
  if (sameValue(state.confirmedIntent, state.draftIntent)) return state
  const next = clone(state)
  next.confirmedIntent = clone(next.draftIntent)
  next.intentVersion += 1
  next.resolveStatus = 'dirty'
  next.activeRequest = null
  next.problems = []
  next.offline = false
  next.readOnly = false
  next.revisionRetryCount = 0
  if (next.statSnapshotStatus === 'verified') next.statSnapshotStatus = 'stale'
  return next
}

function beginGearResolve(state) {
  const next = clone(state)
  const request = {
    serial: next.latestResolveSerial + 1,
    intentVersion: next.intentVersion,
    selectionIntent: clone(next.confirmedIntent)
  }
  next.latestResolveSerial = request.serial
  next.resolveStatus = 'resolving'
  next.activeRequest = clone(request)
  next.problems = []
  next.offline = false
  next.readOnly = false
  return { state: next, request }
}

function requestMatches(state, request) {
  return !!(
    request &&
    state.activeRequest &&
    request.serial === state.latestResolveSerial &&
    request.serial === state.activeRequest.serial &&
    request.intentVersion === state.intentVersion &&
    request.intentVersion === state.activeRequest.intentVersion
  )
}

function transportProblem(result) {
  const message = String(
    (result && (result.transportError || result.error)) ||
    'invalid structured response'
  )
  return {
    kind: 'TRANSPORT_ERROR',
    code: 'GEAR_TRANSPORT_UNAVAILABLE',
    title: message,
    retryable: true
  }
}

function applyGearResolveResult(state, request, transportResult) {
  if (!requestMatches(state, request)) return state
  const next = clone(state)
  next.activeRequest = null
  const envelope = transportResult && transportResult.payload
  if (!transportResult || transportResult.fromFallback || !validEnvelope(envelope)) {
    next.resolveStatus = 'offline'
    next.currentSnapshot = null
    next.problems = [transportProblem(transportResult)]
    next.offline = true
    next.readOnly = true
    return next
  }

  const httpStatus = Number(transportResult.httpStatus || 0)
  const problems = problemList(envelope)
  next.problems = problems
  next.offline = false

  if (httpStatus === 409) {
    next.resolveStatus = 'revision_conflict'
    next.currentSnapshot = null
    next.readOnly = next.revisionRetryCount >= 1
    return next
  }
  if (httpStatus === 503 || envelope.status === 'unavailable') {
    next.resolveStatus = 'unavailable'
    next.currentSnapshot = null
    next.readOnly = true
    return next
  }
  if (httpStatus === 202 || envelope.status === 'pending') {
    next.resolveStatus = 'pending'
    next.currentSnapshot = clone(envelope.data)
    next.readOnly = true
    return next
  }

  const snapshot = clone(envelope.data)
  next.currentSnapshot = snapshot
  next.readOnly = false
  if (
    httpStatus === 200 &&
    envelope.status === 'resolved' &&
    snapshot.status === 'verified' &&
    problems.length === 0
  ) {
    next.resolveStatus = 'verified'
    next.lastVerifiedSnapshot = clone(snapshot)
    next.revisionRetryCount = 0
    return next
  }
  next.resolveStatus = 'blocked'
  return next
}

function rebaseGearIntentRevisions(state, releaseContext) {
  if (state.resolveStatus !== 'revision_conflict' || state.revisionRetryCount >= 1) return state
  const release = releaseContext && typeof releaseContext === 'object' ? releaseContext : {}
  const seasonRevision = String(release.seasonRevision || '')
  const gearCatalogRevision = String(release.gearCatalogRevision || '')
  if (!seasonRevision || !gearCatalogRevision) return state

  const next = clone(state)
  for (const key of ['confirmedIntent', 'draftIntent']) {
    next[key] = next[key] || {}
    next[key].authoredAgainst = {
      ...(next[key].authoredAgainst || {}),
      seasonRevision,
      gearCatalogRevision
    }
  }
  next.intentVersion += 1
  next.resolveStatus = 'dirty'
  next.activeRequest = null
  next.problems = []
  next.offline = false
  next.readOnly = false
  next.revisionRetryCount = 1
  if (next.statSnapshotStatus === 'verified') next.statSnapshotStatus = 'stale'
  return next
}

function gearWorkbenchCanUseVerifiedSnapshot(state) {
  return !!(
    state &&
    state.resolveStatus === 'verified' &&
    !state.activeRequest &&
    !state.offline &&
    !state.readOnly &&
    state.currentSnapshot &&
    state.currentSnapshot.status === 'verified'
  )
}

function gearWorkbenchCanRunProfile(state) {
  const readiness = state && state.currentSnapshot && state.currentSnapshot.profileReadiness
  return gearWorkbenchCanUseVerifiedSnapshot(state) && !!(
    readiness &&
    readiness.status === 'verified' &&
    readiness.simcReady === true
  )
}

function gearWorkbenchView(state) {
  const snapshot = state && state.currentSnapshot && typeof state.currentSnapshot === 'object'
    ? state.currentSnapshot
    : {}
  return {
    resolveStatus: state.resolveStatus,
    intentVersion: state.intentVersion,
    resolving: state.resolveStatus === 'resolving',
    dirty: !sameValue(state.confirmedIntent, state.draftIntent) || state.resolveStatus === 'dirty',
    offline: !!state.offline,
    readOnly: !!state.readOnly,
    revisionRetryCount: state.revisionRetryCount,
    problemCodes: (state.problems || []).map((problem) => String(problem && problem.code || '')).filter(Boolean),
    hasLastVerifiedSnapshot: !!state.lastVerifiedSnapshot,
    canUseVerifiedSnapshot: gearWorkbenchCanUseVerifiedSnapshot(state),
    canRunProfile: gearWorkbenchCanRunProfile(state),
    resolvedGearSignature: String(snapshot.resolvedGearSignature || ''),
    aggregateLegality: clone(snapshot.aggregateLegality || null),
    staticAttributes: clone(snapshot.staticAttributes || null),
    setState: clone(snapshot.setState || null),
    constraints: clone(snapshot.constraints || null),
    profileReadiness: clone(snapshot.profileReadiness || null),
    statSnapshotSignature: String(state.statSnapshotSignature || ''),
    statSnapshotStatus: String(state.statSnapshotStatus || 'idle')
  }
}

module.exports = {
  GEAR_STAT_MAX_ATTEMPTS,
  GEAR_STAT_MAX_DURATION_MS,
  applyGearStatSnapshotResult,
  applyGearResolveResult,
  beginGearStatSnapshot,
  beginGearResolve,
  confirmGearIntent,
  createGearStatSnapshotState,
  createGearWorkbenchState,
  editGearIntent,
  gearWorkbenchCanRunProfile,
  gearWorkbenchCanUseVerifiedSnapshot,
  gearWorkbenchView,
  gearStatRequestTimeoutMs,
  invalidateGearStatSnapshot,
  rebaseGearIntentRevisions
}
