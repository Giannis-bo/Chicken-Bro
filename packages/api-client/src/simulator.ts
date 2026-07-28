import {
  storageKey,
  type ChickenbroResponse,
  type SimcOptionsPayload,
  type SimulatorAnalysisResponse,
  type SimulatorTaskRecord,
} from '@wow-mini/domain'

import { isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiResult, ApiTransport } from './transport'

export interface TaskListPayload { tasks: readonly SimulatorTaskRecord[] }
export interface TaskDetailPayload { task: SimulatorTaskRecord | null }

export interface SimulatorRequestOptions {
  auth?: boolean
  allowInsecureGuestRequest?: boolean
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim() === value && value.length > 0
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
    || !optionalString(value['nextQuestion'])
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
  const preparationKeys = Array.isArray(preparationRows)
    ? preparationRows.map((row) => isRecord(row) ? row['key'] : undefined)
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
    && uniqueNonEmptyStrings(preparationKeys)
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

  message(request: Readonly<Record<string, unknown>>): Promise<ApiResult<ChickenbroResponse>> {
    const data = { ...request, guestId: this.guestId() }
    return this.transport.requestEndpoint('chickenbro.messages', '/api/chickenbro/messages', {
      data,
      auth: true,
      allowInsecureGuestRequest: true,
      fallback: () => ({
        mode: 'chickenbro',
        session: { sessionId: typeof request['sessionId'] === 'string' ? request['sessionId'] : '' },
        job: { jobId: '', status: 'failed' },
        userMessage: { role: 'user', content: typeof request['message'] === 'string' ? request['message'] : '' },
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
}
