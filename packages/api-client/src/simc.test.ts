import { describe, expect, it, vi } from 'vitest'

import { createSimcClient } from './simc'
import type { ApiResult, ApiTransport, RequestOptions } from './transport'


class RecordingTransport implements ApiTransport {
  readonly requests: Array<{ path: string; options: RequestOptions<unknown> }> = []

  async request<T>(path: string, options: RequestOptions<T>): Promise<ApiResult<T>> {
    this.requests.push({ path, options: options as RequestOptions<unknown> })
    return {
      payload: options.fallback(),
      fromFallback: false,
      error: '',
      httpStatus: 200,
    }
  }

}


describe('formal SimC client', () => {
  it('opts into the same zhCN report for Web sessions without putting ownership in the URL', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    for (const auth of [{ kind: 'web' as const, csrfToken: 'mini' }, { kind: 'web' as const, csrfToken: 'csrf' }]) {
      await client.getJob('job-one', { auth, workbench: true, localizedReport: true })
    }
    expect(transport.requests.map(call => call.path)).toEqual(Array(2).fill('/api/v2/simc/jobs/job-one?view=workbench&scenarioVersion=2&reportLocale=zhCN'))
  })
  it('allows bounded multi-provider source reads without extending ordinary requests', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'csrf' }
    await client.createSnapshot({ sourceUrl: 'https://cn.warcraftlogs.com/reports/CPGWvnJ2t9QMRrA1#fight=1&source=4' }, { auth })
    await client.listJobs({}, { auth })
    expect(transport.requests[0]?.options.timeoutMs).toBe(60000)
    expect(transport.requests[1]?.options.timeoutMs).toBeUndefined()
  })

  it('opts into bounded workbench context and preserves actual scenario options', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'csrf' }
    const scenario = { fightStyle: 'HeavyMovement', desiredTargets: 2, iterations: 1000, maxTime: 240, varyCombatLength: .2, targetError: .5, raidBuffs: true, bloodlust: false }
    await client.createJob({ snapshotId: 'snapshot-one', scenario }, { auth, workbench: true, idempotencyKey: 'workbench-create-1' })
    expect(transport.requests[0]?.path).toBe('/api/v2/simc/jobs?view=workbench&scenarioVersion=2')
    expect(transport.requests[0]?.options.data).toEqual({ snapshotId: 'snapshot-one', scenario })
    await client.getRuntime({ auth })
    expect(transport.requests[1]?.path).toBe('/api/v2/simc/runtime')
    expect(() => client.createJob({ snapshotId: 'snapshot-one', scenario: {targetError: NaN} }, { auth, idempotencyKey: 'workbench-create-2' })).toThrow()
  })
  it('uses the isolated candidate prefix for every formal SimC route', async () => {
    vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-candidate')
    try {
      const transport = new RecordingTransport()
      const client = createSimcClient(transport)
      const auth = { kind: 'web' as const, csrfToken: 'web-csrf' }

      await client.listJobs({}, { auth })

      expect(transport.requests[0]?.path).toBe('/api/v2-candidate/simc/jobs')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('uses only formal paths and delegates Web credentials to the transport', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'web-csrf' }

    await client.createSnapshot(
      { sourceUrl: 'https://raider.io/characters/us/area-52/Stormsample' },
      { auth },
    )
    await client.getSnapshot('snapshot/one', { auth })
    await client.listJobs({ limit: 20 }, { auth })
    await client.createJob(
      {
        snapshotId: 'snapshot-one',
        scenario: { fightStyle: 'Patchwerk', desiredTargets: 1, iterations: 300 },
      },
      { auth, idempotencyKey: 'simc-request-one' },
    )
    await client.getJob('job/one', { auth })

    expect(transport.requests.map((call) => call.path)).toEqual([
      '/api/v2/simc/snapshots',
      '/api/v2/simc/snapshots/snapshot%2Fone',
      '/api/v2/simc/jobs?limit=20',
      '/api/v2/simc/jobs',
      '/api/v2/simc/jobs/job%2Fone',
    ])
    for (const call of transport.requests) {
      expect(call.path).not.toContain('/prototype/')
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header?.['Authorization']).toBeUndefined()
    }
    expect(transport.requests[3]?.options.header?.['Idempotency-Key']).toBe('simc-request-one')
  })

  it('delegates Web Cookie and CSRF credentials to the transport', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    const auth = { kind: 'web' as const, csrfToken: 'web-csrf' }

    await client.getSnapshot('snapshot-one', { auth })
    await client.listJobs({}, { auth })
    await client.getJob('job-one', { auth })
    await client.createSnapshot(
      { sourceUrl: 'https://raider.io/characters/us/area-52/Stormsample' },
      { auth },
    )
    await client.createJob(
      { snapshotId: 'snapshot-one', scenario: { fightStyle: 'Patchwerk' } },
      { auth, idempotencyKey: 'web-simc-one' },
    )

    expect(transport.requests.slice(0, 4).map((call) => call.options.header)).toEqual([{}, {}, {}, {}])
    expect(transport.requests[4]?.options.header).toEqual({
      'Idempotency-Key': 'web-simc-one',
    })
    for (const call of transport.requests) {
      expect(call.options.auth).toEqual(auth)
      expect(call.options.credentials).toBeUndefined()
      expect(call.options.baseUrl).toBeUndefined()
      expect(call.options.header?.['Authorization']).toBeUndefined()
      expect(call.options.header?.['X-CSRF-Token']).toBeUndefined()
    }
  })
})
