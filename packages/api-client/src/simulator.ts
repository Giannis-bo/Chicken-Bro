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

function isSimcOptionsPayload(value: unknown): value is SimcOptionsPayload {
  if (!isRecord(value)
    || value['contractRevision'] !== 'simc-options-v1'
    || value['status'] !== 'ready'
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
      validate: (value) => isRecord(value) && typeof value['status'] === 'string' && Array.isArray(value['recommendations']),
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
      validate: (value) => isRecord(value) && Array.isArray(value['tasks']),
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
        || (isRecord(value['task']) && typeof value['task']['taskId'] === 'string')
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
      validate: (value) => isRecord(value)
        && value['mode'] === 'chickenbro'
        && isRecord(value['session'])
        && isRecord(value['assistantMessage']),
    })
  }
}
