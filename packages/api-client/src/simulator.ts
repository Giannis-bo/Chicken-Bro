import {
  storageKey,
  type ChickenbroResponse,
  type ChickenbroSessionDetailPayload,
  type ChickenbroSessionListPayload,
  type ChickenbroSessionSummary,
  type GearSelectionIntent,
  type SimcOptionsPayload,
  type SimulatorAnalysisResponse,
  type SimulatorTaskRecord,
} from '@wow-mini/domain'

import { isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiResult, ApiStreamTask, ApiTransport } from './transport'

export interface TaskListPayload { tasks: readonly SimulatorTaskRecord[] }
export interface TaskDetailPayload { task: SimulatorTaskRecord | null }
export interface ChickenbroMessageRequest { message: string; sessionId?: string; clientMessageId?: string }
export interface ChickenbroSessionListRequest { limit?: number; cursor?: string }
export type ChickenbroStreamEvent =
  | { type: 'started'; requestId: string; sessionId: string }
  | { type: 'status'; requestId: string; stage: 'preparing' | 'generating' }
  | { type: 'delta'; requestId: string; sequence: number; text: string }
  | { type: 'final'; requestId: string; response: ChickenbroResponse }
  | { type: 'failed'; requestId: string; code: string; retryable: boolean }

export interface ChickenbroStreamHandlers {
  onEvent: (event: ChickenbroStreamEvent) => void
  onFailure: (error: string) => void
  onFallback?: (result: ApiResult<ChickenbroResponse>) => void
}

export interface SimulatorRequestOptions {
  auth?: boolean
  allowInsecureGuestRequest?: boolean
}

export interface ExactSimcSourceRef {
  contractRevision: 'exact-simc-source-ref-v1'
  kind: 'template'
  sourceId: string
  remote: true
}

export interface ExactSimcProfileRef {
  contractRevision: 'exact-simc-profile-ref-v1'
  kind: 'talent-template'
  sourceId: string
  remote: true
}

export interface ExactSimcExecutionIntent {
  contractRevision: 'exact-simc-execution-intent-v1'
  raceKey: string
  scenarioKey: string
}

/** Client intent only; the server must reload all Exact facts from the refs. */
export interface ExactSimcRequest {
  selectionIntent: GearSelectionIntent
  sourceRef: ExactSimcSourceRef
  profileRef: ExactSimcProfileRef
  executionIntent: ExactSimcExecutionIntent
}

export interface ExactSimcDependencyVector {
  seasonRevision: string
  gameBuild: string
  gearRuleRevision: string
  resolverRevision: string
  compilerRevision: string
  workerRevision: string
  simcRuntimeRevision: string
  effectAuthorityRevision: string
}

export interface ExactSimcConfirmation {
  requestKey: string
  resolvedLoadoutKey: string
  simulationSnapshotKey: string
  dependencyVector: ExactSimcDependencyVector
}

export interface ExactSimcProblem {
  code: string
  path?: string
}

export type ExactSimcStatus =
  | 'ready'
  | 'queued'
  | 'pending'
  | 'running'
  | 'resolved'
  | 'blocked'
  | 'unsupported'
  | 'failed'

type ExactSimcEmptyData = Readonly<Record<string, never>>

export interface ExactSimcJobRead {
  jobId: number
  requestKey: string
  jobStatus: 'pending' | 'running' | 'resolved' | 'blocked' | 'unsupported' | 'failed'
  result: Readonly<Record<string, unknown>> | null
  cooldownUntil: string | null
}

export type ExactSimcConfirmEnvelope =
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'confirm'
      status: 'ready'
      data: ExactSimcConfirmation
      problems: readonly []
    }
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'confirm'
      status: 'blocked' | 'unsupported'
      data: ExactSimcEmptyData
      problems: readonly ExactSimcProblem[]
    }

export type ExactSimcSubmitEnvelope =
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'submit'
      status: 'queued'
      data: ExactSimcConfirmation & { jobId: number; jobStatus: string; cooldownUntil: string | null }
      problems: readonly []
    }
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'submit'
      status: 'blocked' | 'unsupported'
      data: ExactSimcEmptyData
      problems: readonly ExactSimcProblem[]
    }

export type ExactSimcReadEnvelope =
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'read'
      status: 'pending' | 'running' | 'resolved'
      data: ExactSimcJobRead
      problems: readonly []
    }
  | {
      contractRevision: 'exact-simc-envelope-v1'
      operation: 'read'
      status: 'blocked' | 'unsupported' | 'failed'
      data: ExactSimcJobRead | ExactSimcEmptyData
      problems: readonly ExactSimcProblem[]
    }

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() === value && value.length > 0
}

function nonEmptyTextChunk(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function uniqueNonEmptyStrings(value: unknown): value is readonly string[] {
  return Array.isArray(value)
    && value.length > 0
    && value.every(nonEmptyString)
    && new Set(value).size === value.length
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

function stringList(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.every(nonEmptyString)
}

function optionalString(value: unknown): boolean {
  return value === undefined || nonEmptyString(value)
}

function optionalText(value: unknown): boolean {
  return value === undefined || typeof value === 'string'
}

function optionalRecord(value: unknown): boolean {
  return value === undefined || isRecord(value)
}

const exactPrivateResponseKeys = new Set([
  'rawProfile', 'rawString', 'playerName', 'characterName', 'realm', 'server',
  'userId', 'user_id', 'ownerKeyHash', 'owner_key_hash', 'profileContext',
])

function exactKeys(value: Readonly<Record<string, unknown>>, keys: readonly string[]): boolean {
  const actual = Object.keys(value)
  return actual.length === keys.length && actual.every((key) => keys.includes(key))
}

function containsExactPrivateResponseKey(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(containsExactPrivateResponseKey)
  return isRecord(value) && Object.entries(value).some(([key, nested]) => (
    exactPrivateResponseKeys.has(key) || containsExactPrivateResponseKey(nested)
  ))
}

function isExactProblem(value: unknown): value is ExactSimcProblem {
  return isRecord(value)
    && exactKeys(value, value['path'] === undefined ? ['code'] : ['code', 'path'])
    && nonEmptyString(value['code'])
    && (value['path'] === undefined || nonEmptyString(value['path']))
}

function isExactProblemList(value: unknown, { required }: { required: boolean }): value is readonly ExactSimcProblem[] {
  return Array.isArray(value)
    && (!required || value.length > 0)
    && value.every(isExactProblem)
}

function isExactEmptyData(value: unknown): value is ExactSimcEmptyData {
  return isRecord(value) && Object.keys(value).length === 0
}

function isExactDependencyVector(value: unknown): value is ExactSimcDependencyVector {
  const keys = [
    'seasonRevision', 'gameBuild', 'gearRuleRevision', 'resolverRevision',
    'compilerRevision', 'workerRevision', 'simcRuntimeRevision', 'effectAuthorityRevision',
  ]
  return isRecord(value)
    && exactKeys(value, keys)
    && keys.every((key) => nonEmptyString(value[key]))
}

function isExactConfirmation(value: unknown): value is ExactSimcConfirmation {
  return isRecord(value)
    && exactKeys(value, [
      'requestKey', 'resolvedLoadoutKey', 'simulationSnapshotKey', 'dependencyVector',
    ])
    && /^exact-import-request:sha256:[0-9a-f]{64}$/.test(String(value['requestKey']))
    && /^resolved-loadout-v2:sha256:[0-9a-f]{64}$/.test(String(value['resolvedLoadoutKey']))
    && /^simulation-snapshot-v2:sha256:[0-9a-f]{64}$/.test(String(value['simulationSnapshotKey']))
    && isExactDependencyVector(value['dependencyVector'])
}

function isExactJobRead(value: unknown, status: ExactSimcReadEnvelope['status']): value is ExactSimcJobRead {
  if (!isRecord(value)
    || !exactKeys(value, ['jobId', 'requestKey', 'jobStatus', 'result', 'cooldownUntil'])
    || !positiveInteger(value['jobId'])
    || !/^exact-import-request:sha256:[0-9a-f]{64}$/.test(String(value['requestKey']))
    || value['jobStatus'] !== status
    || (value['cooldownUntil'] !== null && !nonEmptyString(value['cooldownUntil']))) return false
  if (status === 'resolved') return isRecord(value['result']) && !containsExactPrivateResponseKey(value['result'])
  return value['result'] === null
}

function isExactSimcConfirmEnvelope(value: unknown): value is ExactSimcConfirmEnvelope {
  if (!isRecord(value)
    || !exactKeys(value, ['contractRevision', 'operation', 'status', 'data', 'problems'])
    || containsExactPrivateResponseKey(value)
    || value['contractRevision'] !== 'exact-simc-envelope-v1'
    || value['operation'] !== 'confirm') return false
  if (value['status'] === 'ready') {
    return isExactConfirmation(value['data']) && isExactProblemList(value['problems'], { required: false })
      && value['problems'].length === 0
  }
  return (value['status'] === 'blocked' || value['status'] === 'unsupported')
    && isExactEmptyData(value['data'])
    && isExactProblemList(value['problems'], { required: true })
}

function isExactSimcSubmitEnvelope(value: unknown): value is ExactSimcSubmitEnvelope {
  if (!isRecord(value)
    || !exactKeys(value, ['contractRevision', 'operation', 'status', 'data', 'problems'])
    || containsExactPrivateResponseKey(value)
    || value['contractRevision'] !== 'exact-simc-envelope-v1'
    || value['operation'] !== 'submit') return false
  if (value['status'] === 'queued') {
    const data = value['data']
    return isRecord(data)
      && exactKeys(data, [
        'requestKey', 'resolvedLoadoutKey', 'simulationSnapshotKey', 'dependencyVector',
        'jobId', 'jobStatus', 'cooldownUntil',
      ])
      && isExactConfirmation({
        requestKey: data['requestKey'],
        resolvedLoadoutKey: data['resolvedLoadoutKey'],
        simulationSnapshotKey: data['simulationSnapshotKey'],
        dependencyVector: data['dependencyVector'],
      })
      && positiveInteger(data['jobId'])
      && nonEmptyString(data['jobStatus'])
      && (data['cooldownUntil'] === null || nonEmptyString(data['cooldownUntil']))
      && isExactProblemList(value['problems'], { required: false })
      && value['problems'].length === 0
  }
  return (value['status'] === 'blocked' || value['status'] === 'unsupported')
    && isExactEmptyData(value['data'])
    && isExactProblemList(value['problems'], { required: true })
}

function isExactSimcReadEnvelope(value: unknown): value is ExactSimcReadEnvelope {
  if (!isRecord(value)
    || !exactKeys(value, ['contractRevision', 'operation', 'status', 'data', 'problems'])
    || containsExactPrivateResponseKey(value)
    || value['contractRevision'] !== 'exact-simc-envelope-v1'
    || value['operation'] !== 'read') return false
  const status = value['status']
  if (status !== 'pending' && status !== 'running' && status !== 'resolved'
    && status !== 'blocked' && status !== 'unsupported' && status !== 'failed') return false
  if (status === 'pending' || status === 'running' || status === 'resolved') {
    return isExactJobRead(value['data'], status)
      && isExactProblemList(value['problems'], { required: false })
      && value['problems'].length === 0
  }
  if (isExactEmptyData(value['data'])) return isExactProblemList(value['problems'], { required: true })
  return isExactJobRead(value['data'], status)
    && isExactProblemList(value['problems'], { required: true })
}

function exactSimcFallback(operation: 'confirm'): ExactSimcConfirmEnvelope
function exactSimcFallback(operation: 'submit'): ExactSimcSubmitEnvelope
function exactSimcFallback(operation: 'read'): ExactSimcReadEnvelope
function exactSimcFallback(
  operation: 'confirm' | 'submit' | 'read',
): ExactSimcConfirmEnvelope | ExactSimcSubmitEnvelope | ExactSimcReadEnvelope {
  return {
    contractRevision: 'exact-simc-envelope-v1',
    operation,
    status: 'blocked',
    data: {},
    problems: [{ code: 'EXACT_AUTHORITY_UNAVAILABLE' }],
  } as ExactSimcConfirmEnvelope | ExactSimcSubmitEnvelope | ExactSimcReadEnvelope
}

function isSimulatorAnalysisResponse(value: unknown): boolean {
  return isRecord(value)
    && nonEmptyString(value['mode'])
    && nonEmptyString(value['status'])
    && stringList(value['recommendations'])
    && optionalString(value['taskId'])
    && optionalRecord(value['request'])
    && optionalRecord(value['agent'])
    && optionalRecord(value['simulation'])
    && optionalRecord(value['simcReport'])
    && (value['stages'] === undefined
      || (Array.isArray(value['stages']) && value['stages'].every(isRecord)))
}

function hasExplicitValidation(value: unknown): boolean {
  if (!isRecord(value) || !isRecord(value['agent'])) return false
  const validation = value['agent']['validation']
  return isRecord(validation) && typeof validation['passed'] === 'boolean'
}

function isSimulatorAnalysisForRequest(
  value: unknown,
  request: Readonly<Record<string, unknown>>,
): boolean {
  if (!isSimulatorAnalysisResponse(value) || !isRecord(value)) return false
  const requestedMode = request['mode']
  if (typeof requestedMode === 'string' && value['mode'] !== requestedMode) return false
  if (request['confirmOnly'] === true) {
    return value['taskId'] === undefined
      && isRecord(value['request'])
      && isRecord(value['simulation'])
      && hasExplicitValidation(value)
  }
  if (request['saveTask'] === true) {
    return nonEmptyString(value['taskId'])
      && isRecord(value['request'])
      && isRecord(value['simulation'])
      && hasExplicitValidation(value)
  }
  return true
}

function isSimulatorTaskReportSummary(value: unknown): boolean {
  return isRecord(value)
    && optionalText(value['state'])
    && optionalText(value['title'])
    && optionalText(value['summary'])
    && optionalText(value['dpsDisplay'])
    && optionalText(value['statusText'])
    && optionalText(value['updatedAt'])
    && optionalRecord(value['scenario'])
    && optionalRecord(value['preparation'])
    && optionalRecord(value['build'])
    && optionalRecord(value['timing'])
}

function isSimulatorTaskRecord(value: unknown): boolean {
  return isRecord(value)
    && nonEmptyString(value['taskId'])
    && nonEmptyString(value['status'])
    && optionalText(value['id'])
    && optionalText(value['mode'])
    && optionalText(value['question'])
    && optionalText(value['createdAt'])
    && optionalText(value['updatedAt'])
    && optionalRecord(value['request'])
    && (value['analysis'] === undefined || isSimulatorAnalysisResponse(value['analysis']))
    && (value['recommendations'] === undefined || stringList(value['recommendations']))
    && (value['simcReportSummary'] === undefined || isSimulatorTaskReportSummary(value['simcReportSummary']))
}

function isChickenbroMessage(value: unknown, role: 'user' | 'assistant'): boolean {
  return isRecord(value)
    && value['role'] === role
    && nonEmptyString(value['content'])
    && optionalString(value['messageId'])
    && optionalString(value['status'])
}

function isChickenbroAssistantPayload(value: unknown): boolean {
  if (!isRecord(value)
    || !nonEmptyString(value['answerSource'])
    || !nonEmptyString(value['confidence'])
    || !Array.isArray(value['priorityActions'])
    || !stringList(value['evidenceRefs'])
    || !stringList(value['limitations'])
    || !optionalString(value['answerLayer'])
    || !optionalString(value['basisLabel'])
    || (value['evidenceOutcome'] !== undefined
      && value['evidenceOutcome'] !== 'answered'
      && value['evidenceOutcome'] !== 'partial'
      && value['evidenceOutcome'] !== 'researching'
      && value['evidenceOutcome'] !== 'blocked')
    || (value['nextQuestion'] !== undefined && typeof value['nextQuestion'] !== 'string')
    || (value['missingInputs'] !== undefined && !stringList(value['missingInputs']))) return false

  return value['priorityActions'].every((action) => isRecord(action)
    && nonEmptyString(action['title'])
    && stringList(action['evidenceRefs']))
}

function isChickenbroResponse(value: unknown): boolean {
  if (!isRecord(value)
    || value['mode'] !== 'chickenbro'
    || !isRecord(value['session'])
    || !nonEmptyString(value['session']['sessionId'])
    || !optionalString(value['session']['title'])
    || !isChickenbroMessage(value['userMessage'], 'user')
    || !isChickenbroMessage(value['assistantMessage'], 'assistant')) return false

  const assistantMessage = value['assistantMessage'] as Readonly<Record<string, unknown>>
  if (!isChickenbroAssistantPayload(assistantMessage['payload'])) return false
  const job = value['job']
  return job === undefined || (isRecord(job) && nonEmptyString(job['jobId']) && nonEmptyString(job['status']))
}

function isChickenbroStreamEvent(value: unknown): value is ChickenbroStreamEvent {
  if (!isRecord(value) || !nonEmptyString(value['type']) || !nonEmptyString(value['requestId'])) return false
  if (value['type'] === 'started') return nonEmptyString(value['sessionId'])
  if (value['type'] === 'status') return value['stage'] === 'preparing' || value['stage'] === 'generating'
  if (value['type'] === 'delta') return positiveInteger(value['sequence']) && nonEmptyTextChunk(value['text'])
  if (value['type'] === 'final') return isChickenbroResponse(value['response'])
  return value['type'] === 'failed' && nonEmptyString(value['code']) && typeof value['retryable'] === 'boolean'
}

function isChickenbroSessionSummary(value: unknown): value is ChickenbroSessionSummary {
  return isRecord(value)
    && nonEmptyString(value['sessionId'])
    && nonEmptyString(value['title'])
    && nonEmptyString(value['productPhase'])
    && nonEmptyString(value['createdAt'])
    && nonEmptyString(value['updatedAt'])
}

function isChickenbroTranscriptMessage(value: unknown): boolean {
  return isRecord(value)
    && (value['role'] === 'user' || value['role'] === 'assistant' || value['role'] === 'system')
    && nonEmptyString(value['content'])
    && optionalString(value['messageId'])
    && optionalString(value['status'])
    && optionalRecord(value['payload'])
}

function isChickenbroSessionListPayload(value: unknown): value is ChickenbroSessionListPayload {
  return isRecord(value)
    && Array.isArray(value['sessions'])
    && value['sessions'].every(isChickenbroSessionSummary)
    && (value['nextCursor'] === null || nonEmptyString(value['nextCursor']))
}

function isChickenbroSessionDetailPayload(value: unknown): boolean {
  return isRecord(value)
    && isChickenbroSessionSummary(value['session'])
    && Array.isArray(value['messages'])
    && value['messages'].every(isChickenbroTranscriptMessage)
}

function isSimcScenario(value: unknown): value is SimcOptionsPayload['scenarios'][number] {
  return isRecord(value)
    && nonEmptyString(value['key'])
    && nonEmptyString(value['label'])
    && nonEmptyString(value['fightStyle'])
    && value['status'] === 'supported'
    && positiveInteger(value['targets'])
    && positiveInteger(value['durationSeconds'])
}

function isSimcPreparationRow(value: unknown): boolean {
  return isRecord(value)
    && nonEmptyString(value['key'])
    && nonEmptyString(value['category'])
    && nonEmptyString(value['label'])
    && (value['defaultState'] === 'enabled'
      || value['defaultState'] === 'disabled'
      || value['defaultState'] === 'pending_evidence')
    && (value['evidenceState'] === 'verified' || value['evidenceState'] === 'partial')
    && (value['classKey'] === undefined || nonEmptyString(value['classKey']))
    && (value['specKey'] === undefined || nonEmptyString(value['specKey']))
    && typeof value['overrideSupported'] === 'boolean'
}

function isSimcSpecializationPolicy(value: unknown): boolean {
  if (!isRecord(value)
    || value['contractRevision'] !== 'simc-execution-support-v1'
    || value['status'] !== 'ready'
    || value['supportedSpecCount'] !== 26
    || value['unsupportedSpecCount'] !== 14
    || !Array.isArray(value['unsupportedSpecializations'])
    || value['unsupportedSpecializations'].length !== 14) return false
  const specializationIds: string[] = []
  for (const row of value['unsupportedSpecializations']) {
    if (!isRecord(row)
      || !nonEmptyString(row['specializationId'])
      || !row['specializationId'].includes(':')
      || !['tank', 'healer', 'support'].includes(String(row['role']))
      || row['code'] !== 'SIMC_SPECIALIZATION_UNSUPPORTED') return false
    specializationIds.push(row['specializationId'])
  }
  return new Set(specializationIds).size === specializationIds.length
}

function isSimcOptionsPayload(value: unknown): value is SimcOptionsPayload {
  if (!isRecord(value)
    || value['contractRevision'] !== 'simc-options-v1'
    || value['status'] !== 'ready'
    || !isSimcSpecializationPolicy(value['specializationPolicy'])
    || !isRecord(value['races'])
    || !Array.isArray(value['scenarios'])
    || !isRecord(value['preparation'])) return false
  const races = value['races']
  const preparation = value['preparation']
  const supportedKeys = races['supportedKeys']
  const defaults = races['defaultByClass']
  const scenarioKeys = value['scenarios'].map((scenario) => isRecord(scenario) ? scenario['key'] : undefined)
  const preparationRows = preparation['rows']
  const preparationScopeKeys = Array.isArray(preparationRows)
    ? preparationRows.map((row) => isRecord(row)
      ? [
          row['key'],
          row['classKey'] ?? '*',
          row['specKey'] ?? '*',
        ].join(':')
      : undefined)
    : []
  return races['status'] === 'supported'
    && uniqueNonEmptyStrings(supportedKeys)
    && nonEmptyString(races['defaultKey'])
    && supportedKeys.includes(races['defaultKey'])
    && isRecord(defaults)
    && Object.entries(defaults).every(([classKey, raceKey]) => (
      nonEmptyString(classKey) && nonEmptyString(raceKey) && supportedKeys.includes(raceKey)
    ))
    && value['scenarios'].length > 0
    && value['scenarios'].every(isSimcScenario)
    && uniqueNonEmptyStrings(scenarioKeys)
    && preparation['schemaRevision'] === 'simc-preparation-v1'
    && preparation['status'] === 'ready'
    && Array.isArray(preparation['rows'])
    && preparation['rows'].length > 0
    && preparation['rows'].every(isSimcPreparationRow)
    && uniqueNonEmptyStrings(preparationScopeKeys)
}

function fallbackSimcOptions(): SimcOptionsPayload {
  return {
    contractRevision: 'simc-options-v1',
    status: 'blocked',
    specializationPolicy: {
      contractRevision: 'simc-execution-support-v1',
      status: 'blocked',
      supportedSpecCount: 0,
      unsupportedSpecCount: 0,
      unsupportedSpecializations: [],
    },
    races: { status: 'blocked', defaultKey: '', supportedKeys: [], defaultByClass: {} },
    scenarios: [],
    preparation: { schemaRevision: 'simc-preparation-v1', status: 'blocked', rows: [] },
  }
}

export class SimulatorClient {
  constructor(
    private readonly transport: ApiTransport,
    private readonly storage: StorageAdapter = taroStorage,
  ) {}

  guestId(): string {
    const key = storageKey('simulator.guestId')
    const stored = this.storage.get<string>(key)
    if (stored) return stored
    const value = `guest-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
    this.storage.set(key, value)
    return value
  }

  analyze(
    request: Readonly<Record<string, unknown>>,
    options: SimulatorRequestOptions = {},
  ): Promise<ApiResult<SimulatorAnalysisResponse>> {
    const saveTask = request['saveTask'] === true
    const data = options.auth && options.allowInsecureGuestRequest && saveTask
      ? { ...request, guestId: this.guestId() }
      : request
    return this.transport.requestEndpoint('simulator.analyze', '/api/simulator/analyze', {
      data,
      auth: options.auth === true,
      allowInsecureGuestRequest: options.allowInsecureGuestRequest === true,
      fallback: () => ({
        mode: typeof request['mode'] === 'string' ? request['mode'] : 'simcraft',
        status: 'blocked',
        recommendations: ['后端暂时无法完成 SimC 需求确认，请稍后重试。'],
        simulation: { ran: false, available: false, error: 'backend confirmation unavailable' },
      }),
      validate: (value) => isSimulatorAnalysisForRequest(value, request),
    })
  }

  exactSimcConfirm(request: ExactSimcRequest): Promise<ApiResult<ExactSimcConfirmEnvelope>> {
    return this.transport.request('/api/simulator/exact/confirm', {
      method: 'POST',
      data: { ...request },
      auth: true,
      responseMode: 'structured-problem',
      fallback: () => exactSimcFallback('confirm'),
      validate: isExactSimcConfirmEnvelope,
    })
  }

  exactSimcSubmit(
    request: ExactSimcRequest,
    confirmation: ExactSimcConfirmation,
  ): Promise<ApiResult<ExactSimcSubmitEnvelope>> {
    return this.transport.request('/api/simulator/exact/submit', {
      method: 'POST',
      data: { request, confirmation },
      auth: true,
      responseMode: 'structured-problem',
      fallback: () => exactSimcFallback('submit'),
      validate: isExactSimcSubmitEnvelope,
    })
  }

  exactSimcRead(jobId: number): Promise<ApiResult<ExactSimcReadEnvelope>> {
    if (!positiveInteger(jobId)) {
      return Promise.resolve({
        payload: exactSimcFallback('read'),
        fromFallback: true,
        error: 'invalid Exact SimC job id',
      })
    }
    return this.transport.request(`/api/simulator/exact/job?id=${encodeURIComponent(String(jobId))}`, {
      method: 'GET',
      auth: true,
      responseMode: 'structured-problem',
      fallback: () => exactSimcFallback('read'),
      validate: isExactSimcReadEnvelope,
    })
  }

  options(): Promise<ApiResult<SimcOptionsPayload>> {
    return this.transport.requestEndpoint('simulator.simcOptions', '/api/simulator/simc/options', {
      fallback: fallbackSimcOptions,
      validate: isSimcOptionsPayload,
    })
  }

  tasks(): Promise<ApiResult<TaskListPayload>> {
    const query = `guest=1&guestId=${encodeURIComponent(this.guestId())}`
    return this.transport.requestEndpoint('simulator.tasks', `/api/simulator/tasks?${query}`, {
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({ tasks: [] }),
      validate: (value) => isRecord(value)
        && Array.isArray(value['tasks'])
        && value['tasks'].every(isSimulatorTaskRecord),
    })
  }

  task(id: string): Promise<ApiResult<TaskDetailPayload>> {
    const query = `id=${encodeURIComponent(id)}&guest=1&guestId=${encodeURIComponent(this.guestId())}`
    return this.transport.requestEndpoint('simulator.task', `/api/simulator/task?${query}`, {
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({ task: null }),
      validate: (value) => isRecord(value) && (
        value['task'] === null
        || isSimulatorTaskRecord(value['task'])
      ),
    })
  }

  chickenbroSessions(request: ChickenbroSessionListRequest = {}): Promise<ApiResult<ChickenbroSessionListPayload>> {
    const limit = request.limit ?? 20
    const cursor = request.cursor ? `&cursor=${encodeURIComponent(request.cursor)}` : ''
    const query = `guest=1&guestId=${encodeURIComponent(this.guestId())}&limit=${encodeURIComponent(String(limit))}${cursor}`
    return this.transport.requestEndpoint('chickenbro.sessions', `/api/chickenbro/sessions?${query}`, {
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({ sessions: [], nextCursor: null }),
      validate: isChickenbroSessionListPayload,
    })
  }

  chickenbroSession(sessionId: string): Promise<ApiResult<ChickenbroSessionDetailPayload>> {
    const query = `id=${encodeURIComponent(sessionId)}&guest=1&guestId=${encodeURIComponent(this.guestId())}`
    return this.transport.requestEndpoint('chickenbro.session', `/api/chickenbro/sessions?${query}`, {
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({ session: null, messages: [] }),
      validate: isChickenbroSessionDetailPayload,
    })
  }

  message(request: ChickenbroMessageRequest): Promise<ApiResult<ChickenbroResponse>> {
    const data = {
      message: request.message,
      ...(request.sessionId ? { sessionId: request.sessionId } : {}),
      ...(request.clientMessageId ? { clientMessageId: request.clientMessageId } : {}),
      guestId: this.guestId(),
    }
    return this.transport.requestEndpoint('chickenbro.messages', '/api/chickenbro/messages', {
      data,
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({
        mode: 'chickenbro',
        session: { sessionId: request.sessionId || '' },
        job: { jobId: '', status: 'failed' },
        userMessage: { role: 'user', content: request.message },
        assistantMessage: {
          role: 'assistant',
          content: '后端暂时无法连接炸鸡队长；当前不会使用本地假结论替代真实证据链。',
          payload: {
            answerSource: 'frontend_fallback', confidence: 'blocked', priorityActions: [],
            evidenceRefs: [], limitations: ['backend unavailable'],
          },
        },
      }),
      validate: isChickenbroResponse,
    })
  }

  streamMessage(request: ChickenbroMessageRequest, handlers: ChickenbroStreamHandlers): ApiStreamTask {
    const data = {
      message: request.message,
      ...(request.sessionId ? { sessionId: request.sessionId } : {}),
      ...(request.clientMessageId ? { clientMessageId: request.clientMessageId } : {}),
      guestId: this.guestId(),
    }
    const stream = this.transport.requestStreamEndpoint
    if (!stream) {
      handlers.onFailure('chunked response is unavailable')
      return { abort() {} }
    }
    const taskRef: { current: ApiStreamTask | undefined } = { current: undefined }
    let requestId = ''
    let expectedSequence = 1
    let terminal = false
    let cancelled = false
    const reject = () => {
      if (terminal) return
      terminal = true
      taskRef.current?.abort()
      handlers.onFailure('invalid chickenbro stream event')
    }
    const task = stream('chickenbro.messages.stream', '/api/chickenbro/messages/stream', {
      data,
      auth: true,
      allowInsecureGuestRequest: true,
      onEvent: (value) => {
        if (terminal || cancelled || !isChickenbroStreamEvent(value)) {
          reject()
          return
        }
        if (value.type === 'started') {
          if (requestId || (request.sessionId && value.sessionId !== request.sessionId)) {
            reject()
            return
          }
          requestId = value.requestId
        } else if (!requestId || value.requestId !== requestId) {
          reject()
          return
        } else if (value.type === 'delta') {
          if (value.sequence !== expectedSequence) {
            reject()
            return
          }
          expectedSequence += 1
        } else if (value.type === 'final' || value.type === 'failed') {
          terminal = true
        }
        handlers.onEvent(value)
      },
      onFailure: (error) => {
        if (terminal || cancelled) return
        if (!requestId && error === 'HTTP 503' && handlers.onFallback) {
          terminal = true
          void this.message(request).then(handlers.onFallback).catch(() => handlers.onFailure(error))
          return
        }
        terminal = true
        handlers.onFailure(error)
      },
    })
    taskRef.current = task
    return {
      abort() {
        cancelled = true
        taskRef.current?.abort()
      },
    }
  }
}
