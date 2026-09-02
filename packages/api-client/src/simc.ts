import {
  isSimulationJobDetail,
  isSimulationJobPage,
  isSourceSnapshotView,
  isValidIdempotencyKey,
  type SimulationJobDetail,
  type SimulationJobPage,
  type SourceSnapshotView,
} from '@wow-mini/domain'

import { clientAuthRequest, type ClientAuthContext } from './auth-context'
import type { ApiResult, ApiTransport, RequestData } from './transport'
import { apiV2Path } from './api-v2-prefix'


export interface SimcRequestOptions {
  auth: ClientAuthContext
}

export interface SimcJobMutationOptions extends SimcRequestOptions {
  idempotencyKey: string
}

export interface SourceSnapshotCreateRequest {
  sourceUrl: string
}

export interface SimulationJobListRequest {
  cursor?: string
  limit?: number
}

export interface SimulationScenarioRequest {
  fightStyle?: string
  desiredTargets?: number
  iterations?: number
}

export interface SimulationJobCreateRequest {
  snapshotId: string
  scenario: SimulationScenarioRequest
}

export interface SimcClient {
  createSnapshot(
    request: SourceSnapshotCreateRequest,
    options: SimcRequestOptions,
  ): Promise<ApiResult<SourceSnapshotView>>
  getSnapshot(snapshotId: string, options: SimcRequestOptions): Promise<ApiResult<SourceSnapshotView>>
  listJobs(
    request: SimulationJobListRequest,
    options: SimcRequestOptions,
  ): Promise<ApiResult<SimulationJobPage>>
  createJob(
    request: SimulationJobCreateRequest,
    options: SimcJobMutationOptions,
  ): Promise<ApiResult<SimulationJobDetail>>
  getJob(jobId: string, options: SimcRequestOptions): Promise<ApiResult<SimulationJobDetail>>
}


function emptySnapshot(): SourceSnapshotView {
  return {
    id: '',
    provider: 'raiderio',
    sourceUrl: '',
    sourceKey: '',
    revision: 0,
    readiness: 'SNAPSHOT_UNAVAILABLE',
    missingFields: [],
    blockers: [],
    fetchedAt: '',
    provenance: { sourceRevision: null, sourceRawSha256: '' },
  }
}

function emptyJobPage(): SimulationJobPage {
  return { items: [], nextCursor: null }
}

function emptyJobDetail(): SimulationJobDetail {
  return {
    id: '',
    snapshotId: '',
    status: 'failed',
    scenarioHash: '',
    compilerRevision: '',
    runtimeRevision: '',
    errorCode: 'SIMC_UNAVAILABLE',
    createdAt: '',
    updatedAt: '',
    attempts: [],
    result: null,
  }
}

function boundedIdentifier(value: string, label: string): string {
  const normalized = value.trim()
  if (!normalized || normalized.length > 128 || /\s/u.test(normalized)) {
    throw new TypeError(`${label} is invalid`)
  }
  return normalized
}

function sourceUrl(value: string): string {
  const normalized = value.trim()
  if (!normalized || normalized.length > 2048) throw new TypeError('source URL is invalid')
  try {
    if (new URL(normalized).protocol !== 'https:') throw new TypeError('source URL is invalid')
  } catch {
    throw new TypeError('source URL is invalid')
  }
  return normalized
}

function scenario(value: SimulationScenarioRequest): SimulationScenarioRequest {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new TypeError('simulation scenario is invalid')
  }
  const keys = Object.keys(value)
  if (keys.some((key) => !['fightStyle', 'desiredTargets', 'iterations'].includes(key))) {
    throw new TypeError('simulation scenario is invalid')
  }
  if (
    value.fightStyle !== undefined
    && (typeof value.fightStyle !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9 _-]{0,63}$/u.test(value.fightStyle))
  ) throw new TypeError('simulation scenario is invalid')
  if (
    value.desiredTargets !== undefined
    && (!Number.isInteger(value.desiredTargets) || value.desiredTargets < 1 || value.desiredTargets > 20)
  ) throw new TypeError('simulation scenario is invalid')
  if (
    value.iterations !== undefined
    && (!Number.isInteger(value.iterations) || value.iterations < 1 || value.iterations > 10000)
  ) throw new TypeError('simulation scenario is invalid')
  return { ...value }
}

export function createSimcClient(transport: ApiTransport): SimcClient {
  const request = <T>(
    path: string,
    data: RequestData | undefined,
    options: SimcRequestOptions,
    config: {
      method?: 'GET' | 'POST'
      mutating: boolean
      idempotencyKey?: string
      fallback: () => T
      validate: (value: unknown) => boolean
    },
  ): Promise<ApiResult<T>> => {
    const auth = clientAuthRequest(options.auth, { mutating: config.mutating })
    return transport.request(path, {
      ...(config.method === undefined ? {} : { method: config.method }),
      ...(data === undefined ? {} : { data }),
      header: {
        ...auth.header,
        ...(config.idempotencyKey === undefined
          ? {}
          : { 'Idempotency-Key': config.idempotencyKey }),
      },
      credentials: auth.credentials,
      baseUrl: auth.baseUrl,
      auth: false,
      attachAnalyticsHeaders: false,
      responseMode: 'structured-problem',
      fallback: config.fallback,
      validate: config.validate,
    })
  }

  return {
    createSnapshot(createRequest, options) {
      return request(
        apiV2Path('/simc/snapshots'),
        { sourceUrl: sourceUrl(createRequest.sourceUrl) },
        options,
        {
          method: 'POST',
          mutating: true,
          fallback: emptySnapshot,
          validate: isSourceSnapshotView,
        },
      )
    },

    getSnapshot(snapshotId, options) {
      const id = boundedIdentifier(snapshotId, 'snapshot id')
      return request(
        apiV2Path(`/simc/snapshots/${encodeURIComponent(id)}`),
        undefined,
        options,
        {
          mutating: false,
          fallback: emptySnapshot,
          validate: isSourceSnapshotView,
        },
      )
    },

    listJobs(listRequest, options) {
      const query = new URLSearchParams()
      if (listRequest.cursor !== undefined) query.set('cursor', listRequest.cursor)
      if (listRequest.limit !== undefined) query.set('limit', String(listRequest.limit))
      const encoded = query.toString()
      return request(
        apiV2Path(`/simc/jobs${encoded ? `?${encoded}` : ''}`),
        undefined,
        options,
        {
          mutating: false,
          fallback: emptyJobPage,
          validate: isSimulationJobPage,
        },
      )
    },

    createJob(createRequest, options) {
      const snapshotId = boundedIdentifier(createRequest.snapshotId, 'snapshot id')
      if (!isValidIdempotencyKey(options.idempotencyKey)) {
        throw new TypeError('idempotency key is invalid')
      }
      return request(
        apiV2Path('/simc/jobs'),
        { snapshotId, scenario: scenario(createRequest.scenario) },
        options,
        {
          method: 'POST',
          mutating: true,
          idempotencyKey: options.idempotencyKey,
          fallback: emptyJobDetail,
          validate: isSimulationJobDetail,
        },
      )
    },

    getJob(jobId, options) {
      const id = boundedIdentifier(jobId, 'job id')
      return request(
        apiV2Path(`/simc/jobs/${encodeURIComponent(id)}`),
        undefined,
        options,
        {
          mutating: false,
          fallback: emptyJobDetail,
          validate: isSimulationJobDetail,
        },
      )
    },
  }
}
