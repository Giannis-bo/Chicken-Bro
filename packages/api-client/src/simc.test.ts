import { describe, expect, it, vi } from 'vitest'

import type { EndpointId } from '@wow-mini/domain'

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

  requestEndpoint<T>(
    _endpointId: EndpointId,
    path: string,
    options: Omit<RequestOptions<T>, 'method'>,
  ): Promise<ApiResult<T>> {
    return this.request(path, options)
  }
}


describe('formal SimC client', () => {
  it('uses the isolated candidate prefix for every formal SimC route', async () => {
    vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-candidate')
    try {
      const transport = new RecordingTransport()
      const client = createSimcClient(transport)
      const auth = { kind: 'mini' as const, accessToken: 'mini-token' }

      await client.listJobs({}, { auth })

      expect(transport.requests[0]?.path).toBe('/api/v2-candidate/simc/jobs')
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('uses only formal paths and explicit Mini Bearer credentials', async () => {
    const transport = new RecordingTransport()
    const client = createSimcClient(transport)
    const auth = { kind: 'mini' as const, accessToken: 'mini-token' }

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
      expect(call.options.auth).toBe(false)
      expect(call.options.credentials).toBe('omit')
      expect(call.options.baseUrl).toBe('default')
      expect(call.options.header?.['Authorization']).toBe('Bearer mini-token')
    }
    expect(transport.requests[3]?.options.header?.['Idempotency-Key']).toBe('simc-request-one')
  })

  it('uses Web Cookie credentials and CSRF only on writes', async () => {
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

    expect(transport.requests.slice(0, 3).map((call) => call.options.header)).toEqual([{}, {}, {}])
    expect(transport.requests[3]?.options.header).toEqual({ 'X-CSRF-Token': 'web-csrf' })
    expect(transport.requests[4]?.options.header).toEqual({
      'X-CSRF-Token': 'web-csrf',
      'Idempotency-Key': 'web-simc-one',
    })
    for (const call of transport.requests) {
      expect(call.options.credentials).toBe('include')
      expect(call.options.baseUrl).toBe('web-auth')
      expect(call.options.header?.['Authorization']).toBeUndefined()
    }
  })
})
