import type {
  ApiResult,
  ClientAuthContext,
  SimcClient,
  SimulationScenarioRequest,
} from '@wow-mini/api-client'
import type {
  SimulationJobDetail,
  SimulationJobSummary,
  SourceSnapshotView,
} from '@wow-mini/domain'


export type SimcModelPhase = 'idle' | 'loading' | 'ready' | 'submitting' | 'signed_out' | 'blocked'

export interface SimcModelState {
  phase: SimcModelPhase
  snapshot: SourceSnapshotView | null
  jobs: readonly SimulationJobSummary[]
  nextCursor: string | null
  activeJob: SimulationJobDetail | null
  errorCode: string
  errorMessage: string
  retryable: boolean
}

export interface SimcModelDependencies {
  requestId?: () => string
  sleep?: (delayMs: number) => Promise<void>
  maxPolls?: number
}

export interface SimulationPollOptions {
  cancelled?: () => boolean
}

type SimcListener = (state: SimcModelState) => void

const initialState: SimcModelState = {
  phase: 'idle',
  snapshot: null,
  jobs: [],
  nextCursor: null,
  activeJob: null,
  errorCode: '',
  errorMessage: '',
  retryable: false,
}

let fallbackRequestSequence = 0

function defaultRequestId(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  fallbackRequestSequence += 1
  return `simc-${Date.now()}-${fallbackRequestSequence}`
}

function idempotencyKey(value: string): string {
  const normalized = value.replace(/[^A-Za-z0-9._~-]/gu, '-').slice(0, 96)
  return normalized.length >= 8 ? normalized : `simc-${normalized || 'request'}`
}

function submissionIdentity(snapshotId: string, scenario: SimulationScenarioRequest): string {
  return JSON.stringify({
    snapshotId,
    fightStyle: scenario.fightStyle ?? null,
    desiredTargets: scenario.desiredTargets ?? null,
    iterations: scenario.iterations ?? null,
  })
}

function defaultSleep(delayMs: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, delayMs))
}

function resultProblem(result: ApiResult<unknown>, fallback: string): { code: string; message: string } {
  return {
    code: result.problemCode || 'SIMC_REQUEST_FAILED',
    message: result.error || fallback,
  }
}

export function shouldPollSimulationJob(job: SimulationJobDetail): boolean {
  return job.status === 'queued' || job.status === 'running'
}

export function simulationPollDelay(attempt: number): number {
  const boundedAttempt = Math.min(Math.max(Math.trunc(attempt), 0), 10)
  return Math.min(1000 * (2 ** boundedAttempt), 10000)
}

function positiveQueryValue(value: string | null): boolean {
  return value === null || /^[1-9][0-9]{0,8}$/u.test(value)
}

export function isSupportedCharacterSourceUrl(value: string): boolean {
  if (!value || value.length > 2048) return false
  try {
    const parsed = new URL(value.trim())
    if (
      parsed.protocol !== 'https:'
      || parsed.username
      || parsed.password
      || (parsed.port && parsed.port !== '443')
    ) return false
    const host = parsed.hostname.toLowerCase()
    const path = parsed.pathname.split('/').filter(Boolean).map(decodeURIComponent)
    if (host === 'raider.io' || host === 'www.raider.io') {
      const normalized = path.length === 5
        && path[1]?.toLowerCase() === 'characters'
        && /^[a-z]{2}(?:-[a-z]{2})?$/iu.test(path[0] ?? '')
        ? path.slice(1)
        : path
      return normalized.length === 4
        && normalized[0]?.toLowerCase() === 'characters'
        && normalized.slice(1).every((part) => Boolean(part) && !part.includes('\0'))
        && !parsed.search
        && !parsed.hash
    }
    if (host === 'warcraftlogs.com' || host === 'www.warcraftlogs.com') {
      if (
        path.length < 2
        || path.length > 3
        || path[0]?.toLowerCase() !== 'reports'
        || !/^[A-Za-z0-9]{4,128}$/u.test(path[1] ?? '')
      ) return false
      const query = new URLSearchParams(parsed.search)
      const fragment = new URLSearchParams(parsed.hash.replace(/^#/u, ''))
      const keys = new Set([...query.keys(), ...fragment.keys()])
      if ([...keys].some((key) => key !== 'fight' && key !== 'source')) return false
      for (const key of ['fight', 'source']) {
        const values = [...query.getAll(key), ...fragment.getAll(key)]
        if (values.length > 1 || !positiveQueryValue(values[0] ?? null)) return false
      }
      return true
    }
    return false
  } catch {
    return false
  }
}

export class SimcModel {
  private state: SimcModelState = initialState
  private readonly listeners = new Set<SimcListener>()
  private readonly requestId: () => string
  private readonly sleep: (delayMs: number) => Promise<void>
  private readonly maxPolls: number
  private pendingSubmission: { identity: string; idempotencyKey: string } | null = null
  private submitInFlight: Promise<SimulationJobDetail | null> | null = null
  private sourceGeneration = 0
  private jobsGeneration = 0
  private activeJobGeneration = 0
  private operationGeneration = 0

  constructor(
    private readonly client: SimcClient,
    private readonly authProvider: () => ClientAuthContext,
    dependencies: SimcModelDependencies = {},
  ) {
    this.requestId = dependencies.requestId ?? defaultRequestId
    this.sleep = dependencies.sleep ?? defaultSleep
    this.maxPolls = Math.min(Math.max(dependencies.maxPolls ?? 8, 1), 20)
  }

  get(): SimcModelState {
    return this.state
  }

  subscribe(listener: SimcListener): () => void {
    this.listeners.add(listener)
    listener(this.state)
    return () => this.listeners.delete(listener)
  }

  async resolveSource(sourceUrl: string): Promise<SourceSnapshotView | null> {
    const operationGeneration = this.operationGeneration + 1
    this.operationGeneration = operationGeneration
    const generation = this.sourceGeneration + 1
    this.sourceGeneration = generation
    this.activeJobGeneration += 1
    if (!isSupportedCharacterSourceUrl(sourceUrl)) {
      this.update({ snapshot: null, activeJob: null })
      this.fail('INVALID_LINK', '只接受 Raider.IO 或 Warcraft Logs 的角色链接', false)
      return null
    }
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    this.update({
      phase: 'loading',
      snapshot: null,
      activeJob: null,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    let result: ApiResult<SourceSnapshotView>
    try {
      result = await this.client.createSnapshot({ sourceUrl }, { auth })
    } catch (error) {
      if (
        generation === this.sourceGeneration
        && operationGeneration === this.operationGeneration
      ) {
        this.fail('INVALID_LINK', error instanceof Error ? error.message : '角色链接无效', false)
      }
      return null
    }
    if (generation !== this.sourceGeneration) return null
    if (result.fromFallback) {
      if (operationGeneration === this.operationGeneration) {
        this.apiFailure(result, '角色快照读取失败')
      }
      return null
    }
    this.update({
      snapshot: result.payload,
      ...(operationGeneration === this.operationGeneration
        ? { phase: 'ready' as const, errorCode: '', errorMessage: '', retryable: false }
        : {}),
    })
    return result.payload
  }

  async loadJobs(cursor?: string): Promise<void> {
    const operationGeneration = this.operationGeneration + 1
    this.operationGeneration = operationGeneration
    const generation = this.jobsGeneration + 1
    this.jobsGeneration = generation
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    this.update({ phase: 'loading', errorCode: '', errorMessage: '', retryable: false })
    const result = await this.client.listJobs({ ...(cursor ? { cursor } : {}), limit: 20 }, { auth })
    if (generation !== this.jobsGeneration) return
    if (result.fromFallback) {
      if (operationGeneration === this.operationGeneration) {
        this.apiFailure(result, '模拟任务历史加载失败')
      }
      return
    }
    const jobs = cursor
      ? [...this.state.jobs, ...result.payload.items]
      : [...result.payload.items]
    const byId = new Map(jobs.map((job) => [job.id, job]))
    this.update({
      jobs: [...byId.values()],
      nextCursor: result.payload.nextCursor,
      ...(operationGeneration === this.operationGeneration
        ? { phase: 'ready' as const, errorCode: '', errorMessage: '', retryable: false }
        : {}),
    })
  }

  submitJob(scenario: SimulationScenarioRequest): Promise<SimulationJobDetail | null> {
    if (this.submitInFlight) return this.submitInFlight
    const operation = this.submitJobOnce(scenario)
    const tracked = operation.finally(() => { this.submitInFlight = null })
    this.submitInFlight = tracked
    return tracked
  }

  private async submitJobOnce(scenario: SimulationScenarioRequest): Promise<SimulationJobDetail | null> {
    const operationGeneration = this.operationGeneration + 1
    this.operationGeneration = operationGeneration
    const snapshot = this.state.snapshot
    if (!snapshot || snapshot.readiness !== 'READY_FOR_SIMC') {
      this.fail('SNAPSHOT_NOT_READY', '角色快照尚不满足 SimC 执行条件', false)
      return null
    }
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    const identity = submissionIdentity(snapshot.id, scenario)
    const pending = this.pendingSubmission?.identity === identity
      ? this.pendingSubmission
      : { identity, idempotencyKey: idempotencyKey(this.requestId()) }
    this.pendingSubmission = pending
    const activeJobGeneration = this.activeJobGeneration + 1
    this.activeJobGeneration = activeJobGeneration
    this.update({ phase: 'submitting', errorCode: '', errorMessage: '', retryable: false })
    let result: ApiResult<SimulationJobDetail>
    try {
      result = await this.client.createJob(
        { snapshotId: snapshot.id, scenario },
        { auth, idempotencyKey: pending.idempotencyKey },
      )
    } catch (error) {
      if (
        activeJobGeneration === this.activeJobGeneration
        && operationGeneration === this.operationGeneration
      ) {
        this.fail('SCENARIO_INVALID', error instanceof Error ? error.message : '模拟场景无效', false)
      }
      return null
    }
    if (result.fromFallback) {
      if (
        activeJobGeneration === this.activeJobGeneration
        && operationGeneration === this.operationGeneration
      ) {
        this.apiFailure(result, '模拟任务提交失败')
      }
      return null
    }
    if (this.pendingSubmission === pending) this.pendingSubmission = null
    this.update({
      ...(activeJobGeneration === this.activeJobGeneration ? { activeJob: result.payload } : {}),
      jobs: [
        result.payload,
        ...this.state.jobs.filter((job) => job.id !== result.payload.id),
      ],
      ...(operationGeneration === this.operationGeneration
        ? { phase: 'ready' as const, errorCode: '', errorMessage: '', retryable: false }
        : {}),
    })
    return (
      activeJobGeneration === this.activeJobGeneration
      && operationGeneration === this.operationGeneration
    ) ? result.payload : null
  }

  async loadJob(jobId: string): Promise<SimulationJobDetail | null> {
    const operationGeneration = this.operationGeneration + 1
    this.operationGeneration = operationGeneration
    const generation = this.activeJobGeneration + 1
    this.activeJobGeneration = generation
    return this.loadJobForGeneration(jobId, generation, operationGeneration)
  }

  private async loadJobForGeneration(
    jobId: string,
    generation: number,
    operationGeneration: number,
    cancelled?: () => boolean,
  ): Promise<SimulationJobDetail | null> {
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    const result = await this.client.getJob(jobId, { auth })
    if (generation !== this.activeJobGeneration || cancelled?.()) return null
    if (result.fromFallback) {
      if (operationGeneration === this.operationGeneration) {
        this.apiFailure(result, '模拟任务读取失败')
      }
      return null
    }
    this.update({
      activeJob: result.payload,
      ...(operationGeneration === this.operationGeneration
        ? { phase: 'ready' as const, errorCode: '', errorMessage: '', retryable: false }
        : {}),
    })
    return result.payload
  }

  async pollJob(
    jobId: string,
    options: SimulationPollOptions = {},
  ): Promise<SimulationJobDetail | null> {
    const operationGeneration = this.operationGeneration + 1
    this.operationGeneration = operationGeneration
    const generation = this.activeJobGeneration + 1
    this.activeJobGeneration = generation
    for (let attempt = 0; attempt < this.maxPolls; attempt += 1) {
      if (generation !== this.activeJobGeneration || options.cancelled?.()) return null
      const job = await this.loadJobForGeneration(
        jobId,
        generation,
        operationGeneration,
        options.cancelled,
      )
      if (!job || !shouldPollSimulationJob(job)) return job
      if (attempt === this.maxPolls - 1) {
        if (
          generation === this.activeJobGeneration
          && operationGeneration === this.operationGeneration
          && !options.cancelled?.()
        ) {
          this.fail('SIMC_POLL_LIMIT', '任务仍在运行，请稍后手动刷新', true)
        }
        return null
      }
      await this.sleep(simulationPollDelay(attempt))
    }
    return null
  }

  dispose(): void {
    this.sourceGeneration += 1
    this.jobsGeneration += 1
    this.activeJobGeneration += 1
    this.operationGeneration += 1
    this.listeners.clear()
  }

  private apiFailure(result: ApiResult<unknown>, fallback: string): void {
    const problem = resultProblem(result, fallback)
    if (problem.code === 'AUTH_REQUIRED' || result.httpStatus === 401) {
      this.update({
        phase: 'signed_out',
        errorCode: 'AUTH_REQUIRED',
        errorMessage: '小程序登录已失效，请重新登录',
        retryable: true,
      })
      return
    }
    this.fail(problem.code, problem.message, true)
  }

  private authFailure(error: unknown): void {
    this.update({
      phase: 'signed_out',
      errorCode: error instanceof Error ? error.message : 'MINI_SESSION_REQUIRED',
      errorMessage: '小程序登录已失效，请重新登录',
      retryable: true,
    })
  }

  private fail(code: string, message: string, retryable: boolean): void {
    this.update({
      phase: 'blocked',
      errorCode: code,
      errorMessage: message,
      retryable,
    })
  }

  private update(patch: Partial<SimcModelState>): void {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener(this.state))
  }
}
