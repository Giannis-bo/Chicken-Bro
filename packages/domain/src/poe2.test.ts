import { expect, it } from 'vitest'
import { isPoe2Build, isPoe2Job } from './poe2'

it('accepts a build summary and refuses owner-bearing or malformed responses', () => {
  const build = {id: 'a', title: '我的 BD', gameVersion: '0.5', league: '', sourceType: 'pob', inputSha256: 'a'.repeat(64), engineVersion: 'v0.23.1', summary: {}, createdAt: '2026-09-18T00:00:00Z'}
  expect(isPoe2Build(build)).toBe(true)
  expect(isPoe2Build({...build, userId: 'secret-owner'})).toBe(false)
  expect(isPoe2Build({...build, summary: null})).toBe(false)
})

it('refuses successful jobs without numeric results or provenance', () => {
  const job = {id: 'a', buildId: 'b', status: 'succeeded', changes: {}, errorCode: null, createdAt: '2026-09-18T00:00:00Z', updatedAt: '2026-09-18T00:00:00Z', result: null}
  expect(isPoe2Job(job)).toBe(false)
  expect(isPoe2Job({...job, status: 'queued'})).toBe(true)
  expect(isPoe2Job({...job, result: {stats: {Life: Number.NaN}}})).toBe(false)
})
