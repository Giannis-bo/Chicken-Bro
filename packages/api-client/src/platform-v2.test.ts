import { describe, expect, it, vi } from 'vitest'

import type { ApiTransport, RequestOptions } from './transport'
import { PlatformV2Client } from './platform-v2'


function recordingTransport(payload: unknown): ApiTransport & { paths: string[] } {
  const paths: string[] = []
  return {
    paths,
    async request<T>(path: string, options: RequestOptions<T>) {
      paths.push(path)
      void options
      return { payload: payload as T, fromFallback: false, error: '' }
    },
    async requestEndpoint<T>(endpointId: string, path: string, options: Omit<RequestOptions<T>, 'method'>) {
      void endpointId
      void path
      void options
      throw new Error('endpoint registry is not used by the v2 health client')
    },
  }
}


describe('platform v2 health client', () => {
  it('uses the isolated candidate prefix for readiness', async () => {
    vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-candidate')
    try {
      const transport = recordingTransport({
        status: 'ready',
        requestId: '00000000-0000-4000-8000-000000000001',
        components: {},
      })

      await new PlatformV2Client(transport).readiness()

      expect(transport.paths).toEqual(['/api/v2-candidate/health/readiness'])
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('reads only the v2 readiness endpoint and never promotes fallback', async () => {
    const transport = recordingTransport({
      status: 'partial',
      requestId: '00000000-0000-4000-8000-000000000001',
      components: { worker: { status: 'unconfigured', code: 'WORKER_NOT_CONFIGURED' } },
    })
    const result = await new PlatformV2Client(transport).readiness()
    expect(transport.paths).toEqual(['/api/v2/health/readiness'])
    expect(result.fromFallback).toBe(false)
    expect(result.payload.status).toBe('partial')
  })
})
