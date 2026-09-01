import { describe, expect, it } from 'vitest'

import { isPlatformReadinessEnvelope } from './platform-v2'


describe('platform v2 readiness contract', () => {
  it('accepts an honest partial component map', () => {
    expect(isPlatformReadinessEnvelope({
      status: 'partial',
      requestId: '00000000-0000-4000-8000-000000000001',
      components: {
        database: { status: 'ready', code: '' },
        simc: { status: 'unconfigured', code: 'SIMC_NOT_CONFIGURED' },
      },
    })).toBe(true)
  })

  it('rejects unknown states and missing request identity', () => {
    expect(isPlatformReadinessEnvelope({ status: 'green', components: {} })).toBe(false)
    expect(isPlatformReadinessEnvelope({
      status: 'partial',
      requestId: 'not-a-uuid',
      components: { worker: { status: 'unconfigured', code: 'WORKER_NOT_CONFIGURED' } },
    })).toBe(false)
  })
})
