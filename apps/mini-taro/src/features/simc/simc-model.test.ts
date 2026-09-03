import { describe, expect, it, vi } from 'vitest'

import type {
  ApiResult,
  ClientAuthContext,
  SimcClient,
  SimulationJobCreateRequest,
} from '@wow-mini/api-client'
import type {
  SimulationJobDetail,
  SimulationJobPage,
  SourceSnapshotView,
} from '@wow-mini/domain'

import { SimcModel, simulationPollDelay, shouldPollSimulationJob } from './simc-model'


const now = '2026-09-03T12:00:00.000Z'
const snapshot: SourceSnapshotView = {
  id: '00000000-0000-4000-8000-000000000601',
  provider: 'raiderio',
  sourceUrl: 'https://raider.io/characters/us/area-52/Stormsample',
  sourceKey: 'us|area-52|Stormsample',
  revision: 1,
  readiness: 'READY_FOR_SIMC',
  missingFields: [],
  blockers: [],
  fetchedAt: now,
  provenance: { sourceRevision: 'rio-1', sourceRawSha256: 'a'.repeat(64) },
}
const queued: SimulationJobDetail = {
  id: '00000000-0000-4000-8000-000000000602',
  snapshotId: snapshot.id,
  status: 'queued',
  scenarioHash: 'b'.repeat(64),
  compilerRevision: 'compiler-1',
  runtimeRevision: 'runtime-1',
  errorCode: null,
  createdAt: now,
  updatedAt: now,
  attempts: [],
  result: null,
}
const succeeded: SimulationJobDetail = {
  ...queued,
  status: 'succeeded',
  attempts: [{
    attemptNumber: 1,
    startedAt: now,
    finishedAt: now,
    exitCode: 0,
    diagnosticCode: 'SUCCEEDED',
  }],
  result: {
    id: '00000000-0000-4000-8000-000000000603',
    profileSha256: 'c'.repeat(64),
    metricName: 'dps',
    metricValue: 12345.5,
    compilerRevision: 'compiler-1',
    runtimeRevision: 'runtime-1',
    provenance: {
      snapshotId: snapshot.id,
      sourceRevision: 'rio-1',
      sourceRawSha256: 'a'.repeat(64),
      profileSha256: 'c'.repeat(64),
      compilerRevision: 'compiler-1',
      runtimeRevision: 'runtime-1',
      scenarioHash: 'b'.repeat(64),
    },
    createdAt: now,
  },
}

function success<T>(payload: T): ApiResult<T> {
  return { payload, fromFallback: false, error: '', httpStatus: 200 }
}

class FakeSimcClient implements SimcClient {
  readonly calls: Array<{ name: string; auth: ClientAuthContext }> = []
  readonly submitKeys: string[] = []
  jobReads: SimulationJobDetail[] = [queued]

  async createSnapshot(
    _request: Parameters<SimcClient['createSnapshot']>[0],
    options: Parameters<SimcClient['createSnapshot']>[1],
  ): Promise<ApiResult<SourceSnapshotView>> {
    this.calls.push({ name: 'snapshot', auth: options.auth })
    return success(snapshot)
  }

  async getSnapshot(
    _snapshotId: Parameters<SimcClient['getSnapshot']>[0],
    options: Parameters<SimcClient['getSnapshot']>[1],
  ): Promise<ApiResult<SourceSnapshotView>> {
    this.calls.push({ name: 'getSnapshot', auth: options.auth })
    return success(snapshot)
  }

  async listJobs(
    _request: Parameters<SimcClient['listJobs']>[0],
    options: Parameters<SimcClient['listJobs']>[1],
  ): Promise<ApiResult<SimulationJobPage>> {
    this.calls.push({ name: 'list', auth: options.auth })
    return success({ items: [queued], nextCursor: null })
  }

  async createJob(
    _request: SimulationJobCreateRequest,
    options: Parameters<SimcClient['createJob']>[1],
  ): Promise<ApiResult<SimulationJobDetail>> {
    this.calls.push({ name: 'submit', auth: options.auth })
    this.submitKeys.push(options.idempotencyKey)
    return success(queued)
  }

  async getJob(
    _jobId: Parameters<SimcClient['getJob']>[0],
    options: Parameters<SimcClient['getJob']>[1],
  ): Promise<ApiResult<SimulationJobDetail>> {
    this.calls.push({ name: 'getJob', auth: options.auth })
    return success(this.jobReads.shift() ?? succeeded)
  }
}

const auth: ClientAuthContext = { kind: 'mini', accessToken: 'mini-token' }

describe('SimcModel', () => {
  it('rejects arbitrary HTTPS URLs before the provider client is called', async () => {
    const client = new FakeSimcClient()
    const model = new SimcModel(client, () => auth, { requestId: () => 'simc-request-0001' })

    const resolved = await model.resolveSource('https://example.com/characters/us/realm/name')

    expect(resolved).toBeNull()
    expect(model.get()).toMatchObject({ phase: 'blocked', errorCode: 'INVALID_LINK' })
    expect(client.calls).toEqual([])
  })

  it('resolves a real source and submits a referenced job with the same auth owner', async () => {
    const client = new FakeSimcClient()
    const model = new SimcModel(client, () => auth, { requestId: () => 'simc-request-0001' })

    await model.resolveSource(snapshot.sourceUrl)
    const job = await model.submitJob({ fightStyle: 'Patchwerk', desiredTargets: 1, iterations: 300 })

    expect(job?.id).toBe(queued.id)
    expect(model.get()).toMatchObject({ phase: 'ready', snapshot, activeJob: queued })
    expect(client.calls.map((call) => call.name)).toEqual(['snapshot', 'submit'])
    expect(client.calls.every((call) => call.auth === auth)).toBe(true)
  })

  it('polls only non-terminal jobs with bounded backoff and keeps semantic result identity', async () => {
    const client = new FakeSimcClient()
    client.jobReads = [{ ...queued, status: 'running' }, succeeded]
    const delays: number[] = []
    const model = new SimcModel(client, () => auth, {
      requestId: () => 'simc-request-0001',
      sleep: async (delay) => { delays.push(delay) },
    })

    const terminal = await model.pollJob(queued.id)

    expect(terminal).toEqual(succeeded)
    expect(delays).toEqual([1000])
    expect(model.get().activeJob?.result?.metricValue).toBe(12345.5)
    expect(model.get().activeJob?.result?.provenance.scenarioHash).toBe(queued.scenarioHash)
    expect(shouldPollSimulationJob(succeeded)).toBe(false)
    expect(simulationPollDelay(99)).toBe(10000)
  })

  it('does not submit an incomplete snapshot or fabricate a task', async () => {
    const client = new FakeSimcClient()
    const model = new SimcModel(client, () => auth, { requestId: () => 'simc-request-0001' })
    const incomplete: SourceSnapshotView = {
      ...snapshot,
      readiness: 'INCOMPLETE_FOR_SIMC',
      blockers: ['MISSING_TALENTS'],
    }
    client.createSnapshot = vi.fn(async () => success(incomplete))

    await model.resolveSource(snapshot.sourceUrl)
    const job = await model.submitJob({ fightStyle: 'Patchwerk' })

    expect(job).toBeNull()
    expect(model.get()).toMatchObject({
      phase: 'blocked',
      errorCode: 'SNAPSHOT_NOT_READY',
      activeJob: null,
    })
    expect(client.calls.some((call) => call.name === 'submit')).toBe(false)
  })

  it('reuses one submission identity after an uncertain response', async () => {
    const client = new FakeSimcClient()
    const requestId = vi.fn()
      .mockReturnValueOnce('simc-request-0001')
      .mockReturnValueOnce('simc-request-0002')
    let attempts = 0
    client.createJob = vi.fn(async (_request, options) => {
      client.calls.push({ name: 'submit', auth: options.auth })
      client.submitKeys.push(options.idempotencyKey)
      attempts += 1
      if (attempts === 1) {
        return {
          payload: queued,
          fromFallback: true,
          error: '网络结果不确定',
          problemCode: 'SIMC_REQUEST_FAILED',
          httpStatus: 0,
        }
      }
      return success(queued)
    })
    const model = new SimcModel(client, () => auth, { requestId })
    await model.resolveSource(snapshot.sourceUrl)

    const first = await model.submitJob({ fightStyle: 'Patchwerk', desiredTargets: 1 })
    const retried = await model.submitJob({ fightStyle: 'Patchwerk', desiredTargets: 1 })

    expect(first).toBeNull()
    expect(retried?.id).toBe(queued.id)
    expect(client.submitKeys).toEqual(['simc-request-0001', 'simc-request-0001'])
    expect(requestId).toHaveBeenCalledTimes(1)
  })

  it('coalesces concurrent submit taps into one server mutation', async () => {
    const client = new FakeSimcClient()
    const requestId = vi.fn(() => 'simc-request-0001')
    let finish!: (result: ApiResult<SimulationJobDetail>) => void
    client.createJob = vi.fn((_request, options) => {
      client.calls.push({ name: 'submit', auth: options.auth })
      client.submitKeys.push(options.idempotencyKey)
      return new Promise<ApiResult<SimulationJobDetail>>((resolve) => { finish = resolve })
    })
    const model = new SimcModel(client, () => auth, { requestId })
    await model.resolveSource(snapshot.sourceUrl)

    const first = model.submitJob({ fightStyle: 'Patchwerk', desiredTargets: 1 })
    const second = model.submitJob({ fightStyle: 'Patchwerk', desiredTargets: 1 })
    finish(success(queued))

    await expect(first).resolves.toEqual(queued)
    await expect(second).resolves.toEqual(queued)
    expect(client.submitKeys).toEqual(['simc-request-0001'])
    expect(requestId).toHaveBeenCalledTimes(1)
  })
})
