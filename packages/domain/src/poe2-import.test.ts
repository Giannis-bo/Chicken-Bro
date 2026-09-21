import { expect, it } from 'vitest'
import { isPoe2Import, type Poe2Import } from './poe2'

const validImport = (): Poe2Import => ({
  id: 'import-1',
  status: 'needs_input',
  provider: 'ninja',
  preview: { character: '玩個那個破大錘', level: 91 },
  issues: [{ code: 'POB_REQUIRED', path: 'source.pob', severity: 'blocking', message: '請貼上 PoB 代碼' }],
  nextAction: 'supply_source',
  buildId: null,
  baselineJobId: null,
  attempt: 1,
  updatedAt: '2026-09-20T00:00:00Z',
})

it('accepts every import status and nullable result identifiers', () => {
  const statuses: Poe2Import['status'][] = [
    'queued', 'fetching', 'mapping', 'validating',
    'needs_input', 'blocked', 'failed', 'cancelled',
  ]
  for (const status of statuses) {
    expect(isPoe2Import({ ...validImport(), status })).toBe(true)
  }
  expect(isPoe2Import({ ...validImport(), status: 'ready', buildId: 'build-1', baselineJobId: 'job-1' })).toBe(true)
})

it('rejects unknown states, malformed issues and owner fields', () => {
  expect(isPoe2Import({ ...validImport(), status: 'complete' })).toBe(false)
  expect(isPoe2Import({ ...validImport(), issues: [{ code: 'X', path: '', severity: 'fatal', message: 'x' }] })).toBe(false)
  expect(isPoe2Import({ ...validImport(), issues: [{ code: '', path: '', severity: 'warning', message: 'x' }] })).toBe(false)
  expect(isPoe2Import({ ...validImport(), userId: 'owner-secret' })).toBe(false)
  expect(isPoe2Import({ ...validImport(), provider: ['ninja'] })).toBe(false)
})

it('rejects ready imports without both build and successful baseline identities', () => {
  expect(isPoe2Import({ ...validImport(), status: 'ready' })).toBe(false)
  expect(isPoe2Import({ ...validImport(), status: 'ready', buildId: 'build-1' })).toBe(false)
  expect(isPoe2Import({ ...validImport(), status: 'ready', baselineJobId: 'job-1' })).toBe(false)
})
