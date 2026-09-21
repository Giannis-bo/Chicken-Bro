import {isPoe2Build, isPoe2Job, isPoe2Comparison, type Poe2Build, type Poe2Job, type Poe2Changes, type Poe2Comparison} from '@wow-mini/domain'
import type {ClientAuthContext} from './auth-context'
import type {ApiResult, ApiTransport, RequestData} from './transport'
import {apiV2Path} from './api-v2-prefix'
import {isPoe2Import, type Poe2Import, type Poe2CreateImportRequest} from '@wow-mini/domain'
import {isPoe2Tree, type Poe2Tree} from '@wow-mini/domain'

export interface Poe2Client {
  getTree(buildId: string, auth: ClientAuthContext, jobId?: string): Promise<ApiResult<Poe2Tree | null>>
  createImport(body: Poe2CreateImportRequest, auth: ClientAuthContext): Promise<ApiResult<Poe2Import | null>>
  getImport(importId: string, auth: ClientAuthContext): Promise<ApiResult<Poe2Import | null>>
  supplyImportSource(importId: string, body: {source: string; idempotencyKey: string}, auth: ClientAuthContext): Promise<ApiResult<Poe2Import | null>>
  retryImport(importId: string, body: {idempotencyKey: string}, auth: ClientAuthContext): Promise<ApiResult<Poe2Import | null>>
  cancelImport(importId: string, auth: ClientAuthContext): Promise<ApiResult<Poe2Import | null>>
  listBuilds(auth: ClientAuthContext): Promise<ApiResult<{items: Poe2Build[]}>>
  deleteBuild(id: string, auth: ClientAuthContext): Promise<ApiResult<{deleted: boolean}>>
  importBuild(body: {source: string; title?: string; gameVersion?: string; league?: string}, auth: ClientAuthContext): Promise<ApiResult<Poe2Build | null>>
  getBuild(id: string, auth: ClientAuthContext): Promise<ApiResult<Poe2Build | null>>
  listJobs(buildId: string, auth: ClientAuthContext): Promise<ApiResult<{items: Poe2Job[]}>>
  calculate(body: {buildId: string; changes: Poe2Changes; idempotencyKey: string}, auth: ClientAuthContext): Promise<ApiResult<Poe2Job | null>>
  getJob(id: string, auth: ClientAuthContext): Promise<ApiResult<Poe2Job | null>>
  compare(jobIds: [string, string], auth: ClientAuthContext): Promise<ApiResult<Poe2Comparison | null>>
  exportBuild(id: string, auth: ClientAuthContext): Promise<ApiResult<{exportCode: string}>>
  craftingLink(itemText: string, auth: ClientAuthContext): Promise<ApiResult<{url: string}>>
}

const record = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const id = (value: string): string => {
  if (!value || value.length > 128) throw new Error('无效记录标识')
  return encodeURIComponent(value)
}
export function createPoe2Client(transport: ApiTransport): Poe2Client {
  const request = <T>(path: string, auth: ClientAuthContext, fallback: () => T,
    validate: (v: unknown) => boolean, body?: RequestData, timeoutMs?: number): Promise<ApiResult<T>> => transport.request(apiV2Path('/poe2' + path), {
      auth, responseMode: 'structured-problem', fallback, validate,
      ...(timeoutMs === undefined ? {} : {timeoutMs}),
      ...(body === undefined ? {} : {method: 'POST' as const, data: body}),
    })
  return {
    getTree: (buildId, auth, jobId) => request('/builds/' + id(buildId) + '/tree' + (jobId ? '?jobId=' + id(jobId) : ''), auth, () => null, isPoe2Tree, undefined, 65000),
    createImport: (body, auth) => request('/imports', auth, () => null, isPoe2Import, {...body}),
    getImport: (importId, auth) => request('/imports/' + id(importId), auth, () => null, isPoe2Import),
    supplyImportSource: (importId, body, auth) => request('/imports/' + id(importId) + '/source', auth, () => null, isPoe2Import, body),
    retryImport: (importId, body, auth) => request('/imports/' + id(importId) + '/retry', auth, () => null, isPoe2Import, body),
    cancelImport: (importId, auth) => request('/imports/' + id(importId) + '/cancel', auth, () => null, isPoe2Import, {}),
    listBuilds: auth => request('/builds', auth, () => ({items: []}), v => record(v) && Array.isArray(v['items']) && v['items'].every(isPoe2Build)),
    deleteBuild: (buildId, auth) => request('/builds/' + id(buildId) + '/delete', auth, () => ({deleted: false}), v => record(v) && v['deleted'] === true, {}),
    importBuild: (body, auth) => request('/builds', auth, () => null, isPoe2Build, body, 65000),
    getBuild: (buildId, auth) => request('/builds/' + id(buildId), auth, () => null, isPoe2Build),
    listJobs: (buildId, auth) => request('/jobs?buildId=' + id(buildId), auth, () => ({items: []}), v => record(v) && Array.isArray(v['items']) && v['items'].every(isPoe2Job)),
    calculate: (body, auth) => request('/jobs', auth, () => null, isPoe2Job, body as unknown as RequestData),
    getJob: (jobId, auth) => request('/jobs/' + id(jobId), auth, () => null, isPoe2Job),
    compare: (jobIds, auth) => request('/compare', auth, () => null, isPoe2Comparison, {jobIds}),
    exportBuild: (buildId, auth) => request('/builds/' + id(buildId) + '/export', auth, () => ({exportCode: ''}), v => record(v) && typeof v['exportCode'] === 'string' && Boolean(v['exportCode'])),
    craftingLink: (itemText, auth) => request('/crafting/import-link', auth, () => ({url: ''}), v => record(v) && typeof v['url'] === 'string' && v['url'].startsWith('https://beta.craftofexile.com/?'), {itemText}),
  }
}
