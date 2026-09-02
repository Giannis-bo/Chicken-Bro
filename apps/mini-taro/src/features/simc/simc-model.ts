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
    if (!isSupportedCharacterSourceUrl(sourceUrl)) {
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
      this.fail('INVALID_LINK', error instanceof Error ? error.message : '角色链接无效', false)
      return null
    }
    if (result.fromFallback) {
      this.apiFailure(result, '角色快照读取失败')
      return null
    }
    this.update({ phase: 'ready', snapshot: result.payload })
    return result.payload
  }

  async loadJobs(cursor?: string): Promise<void> {
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return
    }
    this.update({ phase: 'loading', errorCode: '', errorMessage: '', retryable: false })
    const result = await this.client.listJobs({ ...(cursor ? { cursor } : {}), limit: 20 }, { auth })
    if (result.fromFallback) {
      this.apiFailure(result, '模拟任务历史加载失败')
      return
    }
    const jobs = cursor
      ? [...this.state.jobs, ...result.payload.items]
      : [...result.payload.items]
    const byId = new Map(jobs.map((job) => [job.id, job]))
    this.update({
      phase: 'ready',
      jobs: [...byId.values()],
      nextCursor: result.payload.nextCursor,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
  }

  async submitJob(scenario: SimulationScenarioRequest): Promise<SimulationJobDetail | null> {
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
    this.update({ phase: 'submitting', errorCode: '', errorMessage: '', retryable: false })
    let result: ApiResult<SimulationJobDetail>
    try {
      result = await this.client.createJob(
        { snapshotId: snapshot.id, scenario },
        { auth, idempotencyKey: idempotencyKey(this.requestId()) },
      )
    } catch (error) {
      this.fail('SCENARIO_INVALID', error instanceof Error ? error.message : '模拟场景无效', false)
      return null
    }
    if (result.fromFallback) {
      this.apiFailure(result, '模拟任务提交失败')
      return null
    }
    this.update({
      phase: 'ready',
      activeJob: result.payload,
      jobs: [
        result.payload,
        ...this.state.jobs.filter((job) => job.id !== result.payload.id),
      ],
    })
    return result.payload
  }

  async loadJob(jobId: string): Promise<SimulationJobDetail | null> {
    let auth: ClientAuthContext
    try {
      auth = this.authProvider()
    } catch (error) {
      this.authFailure(error)
      return null
    }
    const result = await this.client.getJob(jobId, { auth })
    if (result.fromFallback) {
      this.apiFailure(result, '模拟任务读取失败')
      return null
    }
    this.update({
      phase: 'ready',
      activeJob: result.payload,
      errorCode: '',
      errorMessage: '',
      retryable: false,
    })
    return result.payload
  }

  async pollJob(
    jobId: string,
    options: SimulationPollOptions = {},
  ): Promise<SimulationJobDetail | null> {
    for (let attempt = 0; attempt < this.maxPolls; attempt += 1) {
      if (options.cancelled?.()) return null
      const job = await this.loadJob(jobId)
      if (!job || !shouldPollSimulationJob(job)) return job
      if (attempt === this.maxPolls - 1) {
        this.fail('SIMC_POLL_LIMIT', '任务仍在运行，请稍后手动刷新', true)
        return null
      }
      await this.sleep(simulationPollDelay(attempt))
    }
    return null
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
