import {
  isSimulationJobDetail,
  isSimulationJobPage,
  isSourceSnapshotView,
  isValidIdempotencyKey,
  isSimulationScenario,
  isSimulationRuntimeView,
  type SimulationRuntimeView,
  type SimulationScenario,
  type SimulationJobDetail,
  type SimulationJobPage,
  type SourceSnapshotView,
} from '@wow-mini/domain'

import type { ClientAuthContext } from './auth-context'
import type { ApiResult, ApiTransport, RequestData } from './transport'
import { apiV2Path } from './api-v2-prefix'


export interface SimcRequestOptions {
  auth: ClientAuthContext
  workbench?: boolean
  localizedReport?: boolean
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

export type SimulationScenarioRequest = SimulationScenario

export interface SimulationJobCreateRequest {
  snapshotId: string
  scenario: SimulationScenarioRequest
}

export interface SimcClient {
  getRuntime(options: SimcRequestOptions): Promise<ApiResult<SimulationRuntimeView>>
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
  if (!isSimulationScenario(value)) throw new TypeError('simulation scenario is invalid')
  return { ...value }
}

function workbenchPath(path: string, options: SimcRequestOptions): string {
  return options.workbench ? `${path}${path.includes('?') ? '&' : '?'}view=workbench&scenarioVersion=2${options.localizedReport ? '&reportLocale=zhCN' : ''}` : path
}

export function createSimcClient(transport: ApiTransport): SimcClient {
  const request = <T>(
    path: string,
    data: RequestData | undefined,
    options: SimcRequestOptions,
    config: {
      method?: 'GET' | 'POST'
      timeoutMs?: number
      mutating: boolean
      idempotencyKey?: string
      fallback: () => T
      validate: (value: unknown) => boolean
    },
  ): Promise<ApiResult<T>> => {
    return transport.request(workbenchPath(path, options), {
      ...(config.method === undefined ? {} : { method: config.method }),
      ...(data === undefined ? {} : { data }),
      ...(config.timeoutMs === undefined ? {} : { timeoutMs: config.timeoutMs }),
      header: {
        ...(config.idempotencyKey === undefined
          ? {}
          : { 'Idempotency-Key': config.idempotencyKey }),
      },
      auth: options.auth,
      responseMode: 'structured-problem',
      fallback: config.fallback,
      validate: config.validate,
    })
  }

  return {
    getRuntime(options) {
      return request(apiV2Path('/simc/runtime'), undefined, options, {
        mutating: false,
        fallback: () => ({ status: 'unavailable', version: null, gameVersion: null, build: null, sourceCommit: null, runtimeRevision: null }),
        validate: isSimulationRuntimeView,
      })
    },
    createSnapshot(createRequest, options) {
      return request(
        apiV2Path('/simc/snapshots'),
        { sourceUrl: sourceUrl(createRequest.sourceUrl) },
        options,
        {
          method: 'POST',
          // Source resolution may read a report, identity and character details.
          timeoutMs: 60000,
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
