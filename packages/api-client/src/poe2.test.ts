import {expect, it, vi} from 'vitest'
import {createPoe2Client} from './poe2'
import type {ApiTransport, RequestOptions} from './transport'

it('keeps POE2 operations inside the configured Candidate and rejects fake completed results', async () => {
  vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-poe2-candidate')
  const calls: Array<{path: string; options: RequestOptions<unknown>}> = []
  const transport: ApiTransport = {
    async request(path, options) {
      calls.push({path, options: options as RequestOptions<unknown>})
      return {payload: options.fallback(), fromFallback: true, error: ''}
    },
    requestSse() {return {abort() {}}},
  }
  try {
    const client = createPoe2Client(transport)
    const auth = {kind: 'web' as const, csrfToken: 'csrf'}
    await client.calculate({buildId: 'build', changes: {}, idempotencyKey: 'stable-request'}, auth)
    await client.exportBuild('build/one', auth)
    expect(calls.map(call => call.path)).toEqual(['/api/v2-poe2-candidate/poe2/jobs', '/api/v2-poe2-candidate/poe2/builds/build%2Fone/export'])
    expect(calls[0]?.options.auth).toEqual(auth)
    expect(calls[0]?.options.data).toEqual({buildId: 'build', changes: {}, idempotencyKey: 'stable-request'})
    expect(calls[0]?.options.validate?.({status: 'succeeded', result: {stats: {Life: 100}}})).toBe(false)
    await client.importBuild({source: 'share-code'}, auth)
    expect(calls[2]?.options.timeoutMs).toBe(65000)
    await client.getTree('build/one', auth, 'job/one')
    expect(calls[3]?.path).toBe('/api/v2-poe2-candidate/poe2/builds/build%2Fone/tree?jobId=job%2Fone')
    expect(calls[3]?.options.auth).toEqual(auth)
    expect(calls[3]?.options.timeoutMs).toBe(65000)
    expect(calls[0]?.options.validate?.({id: 'j', buildId: 'b', changes: {}, status: 'queued', errorCode: null,
      result: null, createdAt: '2026-09-18T00:00:00Z', updatedAt: '2026-09-18T00:00:00Z'})).toBe(true)
  } finally {vi.unstubAllGlobals()}
})
