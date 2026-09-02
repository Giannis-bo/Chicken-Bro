import { describe, expect, it } from 'vitest'

import {
  isSimulationJobDetail,
  isSimulationJobPage,
  isSourceSnapshotView,
} from './simc'


const snapshotId = '00000000-0000-4000-8000-000000000401'
const jobId = '00000000-0000-4000-8000-000000000402'
const resultId = '00000000-0000-4000-8000-000000000403'
const timestamp = '2026-09-03T11:00:00+00:00'
const scenarioHash = 'a'.repeat(64)
const profileHash = 'b'.repeat(64)

const summary = {
  id: jobId,
  snapshotId,
  status: 'succeeded',
  scenarioHash,
  compilerRevision: 'chickenbro-simc-compiler-v1',
  runtimeRevision: 'simc:current:abc',
  errorCode: null,
  createdAt: timestamp,
  updatedAt: timestamp,
}

const result = {
  id: resultId,
  profileSha256: profileHash,
  metricName: 'dps',
  metricValue: 12345.5,
  compilerRevision: summary.compilerRevision,
  runtimeRevision: summary.runtimeRevision,
  provenance: {
    snapshotId,
    sourceRevision: 'rio-profile-2026-09-01',
    sourceRawSha256: 'c'.repeat(64),
    profileSha256: profileHash,
    compilerRevision: summary.compilerRevision,
    runtimeRevision: summary.runtimeRevision,
    scenarioHash,
  },
  createdAt: timestamp,
}


describe('formal SimC domain guards', () => {
  it('accepts exact bounded snapshot, job page, and detail contracts', () => {
    expect(isSourceSnapshotView({
      id: snapshotId,
      provider: 'raiderio',
      sourceUrl: 'https://raider.io/characters/us/area-52/Stormsample',
      sourceKey: 'us|area-52|Stormsample',
      revision: 1,
      readiness: 'READY_FOR_SIMC',
      missingFields: [],
      blockers: [],
      fetchedAt: timestamp,
      provenance: {
        sourceRevision: 'rio-profile-2026-09-01',
        sourceRawSha256: 'c'.repeat(64),
      },
    })).toBe(true)
    expect(isSimulationJobPage({ items: [summary], nextCursor: null })).toBe(true)
    expect(isSimulationJobDetail({
      ...summary,
      attempts: [{
        attemptNumber: 1,
        startedAt: timestamp,
        finishedAt: timestamp,
        exitCode: 0,
        diagnosticCode: 'SUCCEEDED',
      }],
      result,
    })).toBe(true)
  })

  it('rejects owner/internal expansion, oversized pages, and non-finite results', () => {
    expect(isSimulationJobPage({
      items: Array.from({ length: 51 }, () => summary),
      nextCursor: null,
    })).toBe(false)
    expect(isSimulationJobDetail({
      ...summary,
      userId: snapshotId,
      attempts: [],
      result,
    })).toBe(false)
    expect(isSimulationJobDetail({
      ...summary,
      attempts: [{
        attemptNumber: 1,
        startedAt: timestamp,
        finishedAt: timestamp,
        exitCode: 0,
        diagnosticCode: 'SUCCEEDED',
        workerId: 'private-worker',
      }],
      result,
    })).toBe(false)
    expect(isSimulationJobDetail({
      ...summary,
      attempts: [],
      result: { ...result, metricValue: Number.POSITIVE_INFINITY },
    })).toBe(false)
  })

  it('rejects mismatched immutable result identity', () => {
    expect(isSimulationJobDetail({
      ...summary,
      attempts: [],
      result: {
        ...result,
        runtimeRevision: 'simc:other',
      },
    })).toBe(false)
    expect(isSimulationJobDetail({
      ...summary,
      attempts: [],
      result: {
        ...result,
        provenance: { ...result.provenance, scenarioHash: 'd'.repeat(64) },
      },
    })).toBe(false)
  })
})
