import { describe, expect, it, vi } from 'vitest'

import { SimulatorClient } from './simulator'
import type { StorageAdapter } from './storage'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'

const taro = vi.hoisted(() => ({
  getStorageSync: vi.fn(() => ''),
  setStorageSync: vi.fn(),
  removeStorageSync: vi.fn(),
}))

vi.mock('@tarojs/taro', () => ({ default: taro }))

class MemoryStorage implements StorageAdapter {
  private readonly values = new Map<string, unknown>()

  get<T>(key: string): T | undefined { return this.values.get(key) as T | undefined }
  set<T>(key: string, value: T): void { this.values.set(key, value) }
  remove(key: string): void { this.values.delete(key) }
}

const unsupportedSimcSpecializations = [
  ['deathknight:blood', 'tank'],
  ['demonhunter:vengeance', 'tank'],
  ['druid:guardian', 'tank'],
  ['druid:restoration', 'healer'],
  ['evoker:augmentation', 'support'],
  ['evoker:preservation', 'healer'],
  ['monk:brewmaster', 'tank'],
  ['monk:mistweaver', 'healer'],
  ['paladin:holy', 'healer'],
  ['paladin:protection', 'tank'],
  ['priest:discipline', 'healer'],
  ['priest:holy', 'healer'],
  ['shaman:restoration', 'healer'],
  ['warrior:protection', 'tank'],
].map(([specializationId, role]) => ({
  specializationId,
  role,
  code: 'SIMC_SPECIALIZATION_UNSUPPORTED',
}))

const readySimcSpecializationPolicy = {
  contractRevision: 'simc-execution-support-v1',
  status: 'ready',
  supportedSpecCount: 26,
  unsupportedSpecCount: 14,
  unsupportedSpecializations: unsupportedSimcSpecializations,
}

describe('SimulatorClient task contract', () => {
  it('treats a backend task:null response as a verified empty result', async () => {
    const requestEndpoint = vi.fn(async <T>(
      _endpointId: string,
      _path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ) => {
      const payload = { task: null }
      const valid = options.validate?.(payload) ?? false
      return valid
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
    })
    const transport = { requestEndpoint } as unknown as ApiTransport
    const client = new SimulatorClient(transport, new MemoryStorage())

    const result = await client.task('missing-task')

    expect(result).toEqual({ payload: { task: null }, fromFallback: false, error: '' })
  })

  it('accepts only typed owner-scoped task records for list and detail responses', async () => {
    const validTask = {
      taskId: 'task-1',
      status: 'queued',
      mode: 'simcraft_template',
      question: '',
      recommendations: [],
      createdAt: '2026-07-19T00:00:00Z',
      updatedAt: '2026-07-19T00:00:00Z',
      request: { buildContext: {} },
      analysis: { mode: 'simcraft_template', status: 'queued', recommendations: [] },
      simcReportSummary: { state: 'queued', title: '任务', build: {}, scenario: {} },
    }
    const invalidTasks: readonly unknown[] = [
      { ...validTask, taskId: 42 },
      { ...validTask, status: null },
      { ...validTask, recommendations: '稍后重试' },
      { ...validTask, request: [] },
      { ...validTask, analysis: { mode: 'simcraft_template', status: 1, recommendations: [] } },
      { ...validTask, simcReportSummary: 'queued' },
    ]
    const call = async (payload: unknown, detail: boolean) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      const client = new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
      return detail ? client.task('task-1') : client.tasks()
    }

    expect((await call({ tasks: [validTask] }, false)).fromFallback).toBe(false)
    expect((await call({ task: validTask }, true)).fromFallback).toBe(false)
    for (const invalidTask of invalidTasks) {
      expect((await call({ tasks: [invalidTask] }, false)).fromFallback).toBe(true)
      expect((await call({ task: invalidTask }, true)).fromFallback).toBe(true)
    }
  })

  it('reads the backend-owned SimC options contract without local option fallbacks', async () => {
    const payload = {
      contractRevision: 'simc-options-v1',
      status: 'ready',
      specializationPolicy: readySimcSpecializationPolicy,
      races: {
        status: 'supported',
        defaultKey: 'zandalari_troll',
        supportedKeys: ['zandalari_troll'],
        defaultByClass: { mage: 'zandalari_troll' },
      },
      scenarios: [{
        key: 'backend_raid', label: 'Backend raid', fightStyle: 'Patchwerk',
        targets: 7, durationSeconds: 417, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1',
        status: 'ready',
        rows: [
          {
            key: 'backend_rule', category: 'backend', label: 'Backend rule',
            defaultState: 'enabled', evidenceState: 'verified', overrideSupported: true,
          },
          {
            key: 'rogue_poisons', category: 'spec_combat_preparation',
            classKey: 'rogue', specKey: 'assassination', label: 'Rogue poisons',
            defaultState: 'pending_evidence', evidenceState: 'partial', overrideSupported: false,
          },
          {
            key: 'rogue_poisons', category: 'spec_combat_preparation',
            classKey: 'rogue', specKey: 'outlaw', label: 'Rogue poisons',
            defaultState: 'pending_evidence', evidenceState: 'partial', overrideSupported: false,
          },
        ],
      },
    }
    const calls: Array<{ endpoint: string; path: string }> = []
    const requestEndpoint = vi.fn(async <T>(
      endpoint: string,
      path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ): Promise<ApiResult<T>> => {
      calls.push({ endpoint, path })
      return options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
    })
    const client = new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
    const options = (client as unknown as {
      options?: () => Promise<ApiResult<typeof payload>>
    }).options

    expect(options).toBeTypeOf('function')
    if (!options) return
    const result = await options.call(client)

    expect(calls).toEqual([{
      endpoint: 'simulator.simcOptions',
      path: '/api/simulator/simc/options',
    }])
    expect(result.fromFallback).toBe(false)
    expect(result.payload.scenarios[0]).toMatchObject({ targets: 7, durationSeconds: 417 })
    expect(result.payload.preparation.rows[0]?.overrideSupported).toBe(true)
    expect(result.payload.preparation.rows.slice(1).map((row) => row.specKey)).toEqual([
      'assassination',
      'outlaw',
    ])
  })

  it('fails closed on incompatible, duplicate, or unbounded simc-options-v1 facts', async () => {
    const valid = {
      contractRevision: 'simc-options-v1', status: 'ready',
      specializationPolicy: readySimcSpecializationPolicy,
      races: {
        status: 'supported', defaultKey: 'human', supportedKeys: ['human', 'troll'],
        defaultByClass: { mage: 'human' },
      },
      scenarios: [{
        key: 'single', label: 'Single', fightStyle: 'Patchwerk', targets: 1,
        durationSeconds: 300, status: 'supported',
      }],
      preparation: {
        schemaRevision: 'simc-preparation-v1', status: 'ready',
        rows: [{
          key: 'optimal_raid', category: 'raid', label: 'Raid', defaultState: 'disabled',
          evidenceState: 'verified', overrideSupported: true,
        }],
      },
    }
    const invalid: readonly unknown[] = [
      { ...valid, status: 'partial' },
      { ...valid, specializationPolicy: undefined },
      { ...valid, specializationPolicy: { ...readySimcSpecializationPolicy, supportedSpecCount: 25 } },
      {
        ...valid,
        specializationPolicy: {
          ...readySimcSpecializationPolicy,
          unsupportedSpecializations: unsupportedSimcSpecializations.slice(1),
        },
      },
      {
        ...valid,
        specializationPolicy: {
          ...readySimcSpecializationPolicy,
          unsupportedSpecializations: [
            unsupportedSimcSpecializations[0],
            unsupportedSimcSpecializations[0],
            ...unsupportedSimcSpecializations.slice(2),
          ],
        },
      },
      { ...valid, races: { ...valid.races, status: 'ready' } },
      { ...valid, races: { ...valid.races, supportedKeys: [] } },
      { ...valid, races: { ...valid.races, supportedKeys: ['human', 'human'] } },
      { ...valid, races: { ...valid.races, defaultKey: 'orc' } },
      { ...valid, races: { ...valid.races, defaultByClass: { mage: 'orc' } } },
      { ...valid, scenarios: [{ ...valid.scenarios[0], key: '' }] },
      { ...valid, scenarios: [valid.scenarios[0], { ...valid.scenarios[0] }] },
      { ...valid, scenarios: [{ ...valid.scenarios[0], targets: 1.5 }] },
      { ...valid, scenarios: [{ ...valid.scenarios[0], durationSeconds: 0 }] },
      { ...valid, preparation: { ...valid.preparation, schemaRevision: 'simc-preparation-v0' } },
      { ...valid, preparation: { ...valid.preparation, status: 'partial' } },
      { ...valid, preparation: { ...valid.preparation, rows: [] } },
      { ...valid, preparation: { ...valid.preparation, rows: [valid.preparation.rows[0], { ...valid.preparation.rows[0] }] } },
      { ...valid, preparation: { ...valid.preparation, rows: [{ ...valid.preparation.rows[0], defaultState: 'automatic' }] } },
      { ...valid, preparation: { ...valid.preparation, rows: [{ ...valid.preparation.rows[0], evidenceState: 'ready' }] } },
    ]

    const results = await Promise.all(invalid.map(async (payload) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      return new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage()).options()
    }))

    expect(results.every((result) => result.fromFallback)).toBe(true)
    expect(results.every((result) => (
      result.payload.status === 'blocked'
      && result.payload.races.supportedKeys.length === 0
      && result.payload.scenarios.length === 0
      && result.payload.preparation.rows.length === 0
    ))).toBe(true)
  })

  it('accepts an empty optional next question while rejecting malformed assistant evidence', async () => {
    const valid = {
      mode: 'chickenbro',
      session: { sessionId: 'session-1', title: '证据检查' },
      job: { jobId: 'job-1', status: 'succeeded' },
      userMessage: { role: 'user', content: '当前缺什么证据？' },
      assistantMessage: {
        role: 'assistant',
        content: '当前需要补充可验证输入。',
        payload: {
          answerSource: 'deterministic_fallback',
          confidence: 'low',
          answerLayer: 'diagnostic',
          basisLabel: '需要证据确认',
          priorityActions: [{ title: '补充 SimC', evidenceRefs: ['simc://task/1'] }],
          evidenceRefs: ['simc://task/1'],
          limitations: ['missing_published_profile'],
          missingInputs: ['simc_or_wcl'],
          nextQuestion: '是否已有 SimC 报告？',
        },
      },
    }
    const invalid: readonly unknown[] = [
      { ...valid, session: { sessionId: 1 } },
      { ...valid, assistantMessage: { ...valid.assistantMessage, role: 'user' } },
      { ...valid, assistantMessage: { ...valid.assistantMessage, content: null } },
      { ...valid, assistantMessage: { ...valid.assistantMessage, payload: { ...valid.assistantMessage.payload, evidenceRefs: 'simc://task/1' } } },
      { ...valid, assistantMessage: { ...valid.assistantMessage, payload: { ...valid.assistantMessage.payload, priorityActions: [{ title: '', evidenceRefs: [] }] } } },
    ]
    const emptyNextQuestion = {
      ...valid,
      assistantMessage: {
        ...valid.assistantMessage,
        payload: { ...valid.assistantMessage.payload, nextQuestion: '' },
      },
    }
    const partialEvidenceOutcome = {
      ...valid,
      assistantMessage: {
        ...valid.assistantMessage,
        payload: { ...valid.assistantMessage.payload, evidenceOutcome: 'partial' },
      },
    }
    const invalidEvidenceOutcome = {
      ...valid,
      assistantMessage: {
        ...valid.assistantMessage,
        payload: { ...valid.assistantMessage.payload, evidenceOutcome: 'stale' },
      },
    }
    const responses = [emptyNextQuestion, partialEvidenceOutcome, invalidEvidenceOutcome, ...invalid]
    const results = await Promise.all(responses.map(async (payload) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      return new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
        .message({ message: '当前缺什么证据？', sessionId: '' })
    }))

    expect(results[0]?.fromFallback).toBe(false)
    expect(results[1]?.fromFallback).toBe(false)
    expect(results.slice(2).every((result) => result.fromFallback)).toBe(true)
  })

  it('forwards a stable client message id for Chickenbro retry de-duplication', async () => {
    let capturedData: unknown
    const requestEndpoint = async <T>(
      _endpoint: string,
      _path: string,
      options: Omit<RequestOptions<T>, 'method'>,
    ): Promise<ApiResult<T>> => {
      capturedData = options.data
      return { payload: options.fallback(), fromFallback: true, error: 'not needed for request contract' }
    }

    await new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
      .message({ message: 'frost death knight build', sessionId: 'session-1', clientMessageId: 'turn-1' })

    expect(capturedData).toMatchObject({
      message: 'frost death knight build',
      sessionId: 'session-1',
      clientMessageId: 'turn-1',
    })
  })

  it('forwards only monotonic, request-bound Chickenbro stream events and aborts malformed events', () => {
    let streamOptions: {
      onEvent: (event: unknown) => void
      onFailure: (error: string) => void
    } | undefined
    const abort = vi.fn()
    const requestStreamEndpoint = vi.fn((_endpoint: string, _path: string, options) => {
      streamOptions = options
      return { abort }
    })
    const client = new SimulatorClient({ requestStreamEndpoint } as unknown as ApiTransport, new MemoryStorage())
    const events: string[] = []
    const failures: string[] = []

    client.streamMessage(
      { message: '冰DK大秘境先排查什么？', sessionId: 'session-1', clientMessageId: 'turn-1' },
      { onEvent: (event) => events.push(event.type), onFailure: (error) => failures.push(error) },
    )
    streamOptions?.onEvent({ type: 'started', requestId: 'request-1', sessionId: 'session-1' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 1, text: '先检查资源。' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 1, text: '重复。' })

    expect(requestStreamEndpoint).toHaveBeenCalledWith(
      'chickenbro.messages.stream',
      '/api/chickenbro/messages/stream',
      expect.objectContaining({
        data: expect.objectContaining({ sessionId: 'session-1', clientMessageId: 'turn-1' }),
      }),
    )
    expect(events).toEqual(['started', 'delta'])
    expect(abort).toHaveBeenCalledOnce()
    expect(failures).toEqual(['invalid chickenbro stream event'])
  })

  it('preserves nonempty whitespace delta chunks so streamed markdown layout is not rejected', () => {
    let streamOptions: {
      onEvent: (event: unknown) => void
      onFailure: (error: string) => void
    } | undefined
    const abort = vi.fn()
    const requestStreamEndpoint = vi.fn((_endpoint: string, _path: string, options) => {
      streamOptions = options
      return { abort }
    })
    const client = new SimulatorClient({ requestStreamEndpoint } as unknown as ApiTransport, new MemoryStorage())
    const events: string[] = []
    const failures: string[] = []

    client.streamMessage(
      { message: '冰DK大秘境先排查什么？', sessionId: 'session-1', clientMessageId: 'turn-markdown-layout' },
      { onEvent: (event) => events.push(event.type), onFailure: (error) => failures.push(error) },
    )
    streamOptions?.onEvent({ type: 'started', requestId: 'request-1', sessionId: 'session-1' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 1, text: '先确认资源。' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 2, text: '\n\n' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 3, text: '再对齐爆发。' })

    expect(events).toEqual(['started', 'delta', 'delta', 'delta'])
    expect(failures).toEqual([])
    expect(abort).not.toHaveBeenCalled()
  })

  it('still rejects an empty delta chunk', () => {
    let streamOptions: {
      onEvent: (event: unknown) => void
      onFailure: (error: string) => void
    } | undefined
    const abort = vi.fn()
    const requestStreamEndpoint = vi.fn((_endpoint: string, _path: string, options) => {
      streamOptions = options
      return { abort }
    })
    const failures: string[] = []

    new SimulatorClient({ requestStreamEndpoint } as unknown as ApiTransport, new MemoryStorage()).streamMessage(
      { message: '冰DK大秘境先排查什么？', sessionId: 'session-1', clientMessageId: 'turn-empty-chunk' },
      { onEvent: vi.fn(), onFailure: (error) => failures.push(error) },
    )
    streamOptions?.onEvent({ type: 'started', requestId: 'request-1', sessionId: 'session-1' })
    streamOptions?.onEvent({ type: 'delta', requestId: 'request-1', sequence: 1, text: '' })

    expect(abort).toHaveBeenCalledOnce()
    expect(failures).toEqual(['invalid chickenbro stream event'])
  })

  it('falls back only for the server pre-stream unavailable response, never an ambiguous transport failure', async () => {
    let streamOptions: { onFailure: (error: string) => void } | undefined
    const requestStreamEndpoint = vi.fn((_endpoint: string, _path: string, options) => {
      streamOptions = options
      return { abort: vi.fn() }
    })
    const client = new SimulatorClient({ requestStreamEndpoint } as unknown as ApiTransport, new MemoryStorage())
    const fullMessage = vi.spyOn(client, 'message').mockResolvedValue({
      payload: {} as never,
      fromFallback: false,
      error: '',
    })
    const failures: string[] = []
    const fallback = vi.fn()

    client.streamMessage(
      { message: '冰DK大秘境先排查什么？', clientMessageId: 'turn-transport-failure' },
      { onEvent: vi.fn(), onFailure: (error) => failures.push(error), onFallback: fallback },
    )
    streamOptions?.onFailure('network down')
    await Promise.resolve()

    expect(fullMessage).not.toHaveBeenCalled()
    expect(failures).toEqual(['network down'])

    client.streamMessage(
      { message: '冰DK大秘境先排查什么？', clientMessageId: 'turn-pre-stream-unavailable' },
      { onEvent: vi.fn(), onFailure: (error) => failures.push(error), onFallback: fallback },
    )
    streamOptions?.onFailure('HTTP 503')
    await Promise.resolve()

    expect(fullMessage).toHaveBeenCalledWith({
      message: '冰DK大秘境先排查什么？',
      clientMessageId: 'turn-pre-stream-unavailable',
    })
    expect(fallback).toHaveBeenCalledOnce()
  })

  it('validates owner-scoped Chickenbro archive summaries and session details', async () => {
    const session = {
      sessionId: 'session-archive-1',
      title: '版本职业咨询',
      productPhase: 'retail',
      createdAt: '2026-08-01T00:00:00+00:00',
      updatedAt: '2026-08-01T01:00:00+00:00',
    }
    const validList = { sessions: [session], nextCursor: 'cursor-1' }
    const validDetail = {
      session,
      messages: [
        { messageId: 'message-1', role: 'user', content: '正式服火法怎么开爆发？', createdAt: '2026-08-01T00:00:00+00:00' },
        { messageId: 'message-2', role: 'assistant', content: '先确认当前版本和目标场景。', createdAt: '2026-08-01T00:01:00+00:00' },
      ],
    }
    const invalidList = [
      { sessions: [{ ...session, updatedAt: '' }], nextCursor: null },
      { sessions: [session], nextCursor: 1 },
    ]
    const invalidDetail = [
      { session: { ...session, productPhase: '' }, messages: [] },
      { session, messages: [{ role: 'assistant', content: '' }] },
    ]
    const run = async (payload: unknown, kind: 'list' | 'detail') => {
      const requestEndpoint = async <T>(
        endpoint: string,
        path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => {
        expect(endpoint).toBe(kind === 'list' ? 'chickenbro.sessions' : 'chickenbro.session')
        expect(path).toContain('/api/chickenbro/sessions?')
        expect(path).toContain('guest=1')
        return options.validate?.(payload)
          ? { payload: payload as T, fromFallback: false, error: '' }
          : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      }
      const client = new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage())
      return kind === 'list'
        ? client.chickenbroSessions({ limit: 1, cursor: 'cursor-0' })
        : client.chickenbroSession('session-archive-1')
    }

    expect((await run(validList, 'list')).fromFallback).toBe(false)
    expect((await run(validDetail, 'detail')).fromFallback).toBe(false)
    for (const payload of invalidList) expect((await run(payload, 'list')).fromFallback).toBe(true)
    for (const payload of invalidDetail) expect((await run(payload, 'detail')).fromFallback).toBe(true)
  })

  it('requires a complete confirmation response for the requested SimC mode', async () => {
    const valid = {
      mode: 'simcraft_template',
      status: 'template_ready',
      recommendations: [],
      request: { confirmOnly: true, saveTask: false },
      agent: { validation: { passed: true, errors: [], warnings: [] } },
      simulation: { ran: false, available: true },
      stages: [{ key: 'validation', status: 'completed' }],
    }
    const invalid: readonly unknown[] = [
      { ...valid, mode: 'simcraft_agent' },
      { ...valid, agent: undefined },
      { ...valid, agent: { validation: { passed: 'yes' } } },
      { ...valid, stages: ['completed'] },
      { ...valid, taskId: '' },
    ]
    const call = async (payload: unknown) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      return new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage()).analyze({
        mode: 'simcraft_template', confirmOnly: true, saveTask: false,
      })
    }

    expect((await call(valid)).fromFallback).toBe(false)
    for (const payload of invalid) expect((await call(payload)).fromFallback).toBe(true)
  })

  it('accepts a final saved SimC response only when the backend returns a non-empty task id', async () => {
    const valid = {
      mode: 'simcraft_template',
      status: 'queued',
      taskId: 'task-queued-1',
      recommendations: [],
      request: { confirmOnly: false, saveTask: true },
      agent: { validation: { passed: true }, status: 'simc_queued' },
      simulation: { ran: false, status: 'queued' },
    }
    const invalid: readonly unknown[] = [
      { ...valid, taskId: undefined },
      { ...valid, taskId: '' },
      { ...valid, request: undefined },
      { ...valid, simulation: undefined },
    ]
    const call = async (payload: unknown) => {
      const requestEndpoint = async <T>(
        _endpoint: string,
        _path: string,
        options: Omit<RequestOptions<T>, 'method'>,
      ): Promise<ApiResult<T>> => options.validate?.(payload)
        ? { payload: payload as T, fromFallback: false, error: '' }
        : { payload: options.fallback(), fromFallback: true, error: 'invalid payload' }
      return new SimulatorClient({ requestEndpoint } as unknown as ApiTransport, new MemoryStorage()).analyze({
        mode: 'simcraft_template', confirmOnly: false, saveTask: true,
      })
    }

    expect((await call(valid)).fromFallback).toBe(false)
    for (const payload of invalid) expect((await call(payload)).fromFallback).toBe(true)
  })
})
