import {expect, it, vi} from 'vitest'
import {createPoe2Client} from './poe2'
import type {ApiTransport, RequestOptions} from './transport'
it('uses authenticated strict import contracts for all five operations', async () => {
  vi.stubGlobal('__WOW_API_V2_PREFIX__', '/api/v2-poe2-candidate')
  const calls: Array<{path: string; options: RequestOptions<unknown>}> = []
  const transport: ApiTransport = {async request(path, options) {calls.push({path, options: options as RequestOptions<unknown>}); return {payload: options.fallback(), fromFallback: true, error: ''}}, requestSse() {return {abort() {}}}}
  const client = createPoe2Client(transport), auth = {kind: 'web' as const, csrfToken: 'test'}
  try {
    await client.createImport({provider: 'ninja', url: 'https://poe.ninja/poe2/profile/a/b/character/c', idempotencyKey: 'key'}, auth)
    await client.getImport('id/1', auth)
    await client.supplyImportSource('id/1', {source: 'xml', idempotencyKey: 'key2'}, auth)
    await client.retryImport('id/1', {idempotencyKey: 'key3'}, auth)
    await client.cancelImport('id/1', auth)
    expect(calls.map(c => c.path)).toEqual(['', '/id%2F1', '/id%2F1/source', '/id%2F1/retry', '/id%2F1/cancel'].map(p => '/api/v2-poe2-candidate/poe2/imports' + p))
    const packet = {id: 'i', status: 'needs_input', provider: 'ninja', preview: null, issues: [], nextAction: 'supply_pob', buildId: null, baselineJobId: null, attempt: 0, updatedAt: '2026-09-20T00:00:00Z'}
    for (const call of calls) {expect(call.options.auth).toEqual(auth); expect(call.options.responseMode).toBe('structured-problem'); expect(call.options.validate?.(packet)).toBe(true); expect(call.options.validate?.({...packet, status: 'ready'})).toBe(false); expect(call.options.validate?.({...packet, ownerId: 'x'})).toBe(false)}
    expect(calls[0]?.options.data).toMatchObject({provider: 'ninja'})
    expect(calls[4]?.options).toMatchObject({method: 'POST', data: {}})
  } finally {vi.unstubAllGlobals()}
})
