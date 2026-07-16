import {
  storageKey,
  type ChickenbroResponse,
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
