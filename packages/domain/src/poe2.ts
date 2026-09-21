export interface Poe2Build {
  id: string
  title: string
  gameVersion: string
  league: string
  sourceType: string
  inputSha256: string
  engineVersion: string
  summary: Record<string, unknown>
  createdAt: string
  source?: string
}

export interface Poe2Changes {
  skillGroups?: Array<{index: number; gems: Array<{name: string; level: number; quality: number}>}>
  level?: number
  mainSocketGroup?: number
  items?: Array<{slot: string; text: string}>
  config?: Record<string, string | boolean | number>
  allocateNodes?: number[]
  deallocateNodes?: number[]
}

export interface Poe2Result {
  skillSetup?: Array<{index: number; source: 'configured' | 'tree' | 'item' | 'generated'; slot: string; gems: Array<{name: string; level: number; kind: 'skill' | 'support' | 'unknown'}>}>
  stats: Record<string, number>
  inputSha256: string
  outputSha256: string
  engineVersion: string
  exportCode: string
  summary: Record<string, unknown>
  effectiveConfig: Record<string, unknown>
  unsupported: string[]
  skills: Array<{index: number; label: string; gems: Array<{name: string; level: number}>}>
  allocatedNodes: number[]
  scope: string
  changes: Poe2Changes
}

export interface Poe2Job {
  id: string
  buildId: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  changes: Poe2Changes
  errorCode: string | null
  createdAt: string
  updatedAt: string
  result: Poe2Result | null
}

export interface Poe2Comparison {
  metrics: Record<string, {baseline: number; candidate: number; delta: number; percent: number | null}>
  baselineChanges: Poe2Changes
  candidateChanges: Poe2Changes
  engineVersion: string
  scope: string
}

export type Poe2ImportProvider = 'wegame' | 'ninja'
export type Poe2ImportStatus = 'queued' | 'fetching' | 'mapping' | 'validating' | 'ready'
  | 'needs_input' | 'blocked' | 'failed' | 'cancelled'
export type Poe2ImportIssueSeverity = 'info' | 'warning' | 'error' | 'blocking'

export interface Poe2ImportIssue {
  code: string
  path: string
  severity: Poe2ImportIssueSeverity
  message: string
}

export interface Poe2Import {
  id: string
  status: Poe2ImportStatus
  provider: Poe2ImportProvider
  preview: Record<string, unknown> | null
  issues: Poe2ImportIssue[]
  nextAction: string | null
  buildId: string | null
  baselineJobId: string | null
  attempt: number
  updatedAt: string
}

export interface Poe2CreateImportRequest {
  provider: Poe2ImportProvider
  url: string
  idempotencyKey: string
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
const text = (value: unknown): value is string => typeof value === 'string'
const date = (value: unknown): boolean => text(value) && Number.isFinite(Date.parse(value))
const ownerFree = (value: Record<string, unknown>): boolean => !['userId', 'user_id', 'owner', 'ownerId'].some(key => key in value)

export function isPoe2Build(value: unknown): value is Poe2Build {
  return record(value) && ownerFree(value) && text(value['id']) && Boolean(value['id'])
    && ['title', 'gameVersion', 'league', 'sourceType', 'engineVersion'].every(key => text(value[key]))
    && typeof value['inputSha256'] === 'string' && /^[a-f0-9]{64}$/u.test(value['inputSha256'])
    && record(value['summary']) && date(value['createdAt'])
    && (!('source' in value) || text(value['source']))
}

export function isPoe2Result(value: unknown): value is Poe2Result {
  return record(value) && ownerFree(value) && record(value['stats'])
    && Object.values(value['stats']).every(n => typeof n === 'number' && Number.isFinite(n))
    && ['inputSha256', 'outputSha256', 'engineVersion', 'exportCode', 'scope'].every(key => text(value[key]) && Boolean(value[key]))
    && record(value['summary']) && record(value['effectiveConfig']) && record(value['changes'])
    && Array.isArray(value['unsupported']) && value['unsupported'].every(text)
    && Array.isArray(value['skills']) && Array.isArray(value['allocatedNodes'])
    && (value['skillSetup'] === undefined || (Array.isArray(value['skillSetup']) && value['skillSetup'].every(g =>
      record(g) && Number.isInteger(g['index']) && text(g['slot']) && ['configured', 'tree', 'item', 'generated'].includes(String(g['source']))
      && Array.isArray(g['gems']) && g['gems'].every(gem => record(gem) && text(gem['name'])
        && typeof gem['level'] === 'number' && Number.isFinite(gem['level']) && ['skill', 'support', 'unknown'].includes(String(gem['kind']))))))
}

export function isPoe2Job(value: unknown): value is Poe2Job {
  return record(value) && ownerFree(value) && text(value['id']) && Boolean(value['id']) && text(value['buildId'])
    && ['queued', 'running', 'succeeded', 'failed'].includes(String(value['status']))
    && record(value['changes']) && (value['errorCode'] === null || text(value['errorCode'])) && date(value['createdAt']) && date(value['updatedAt'])
    && (value['status'] === 'succeeded' ? isPoe2Result(value['result']) : value['result'] === null)
}

export function isPoe2Comparison(value: unknown): value is Poe2Comparison {
  return record(value) && record(value['metrics']) && text(value['engineVersion']) && text(value['scope'])
    && record(value['baselineChanges']) && record(value['candidateChanges'])
    && Object.values(value['metrics']).every(metric => record(metric)
      && ['baseline', 'candidate', 'delta'].every(key => typeof metric[key] === 'number' && Number.isFinite(metric[key]))
      && (metric['percent'] === null || typeof metric['percent'] === 'number' && Number.isFinite(metric['percent'])))
}

const importStatuses: Poe2ImportStatus[] = [
  'queued', 'fetching', 'mapping', 'validating', 'ready',
  'needs_input', 'blocked', 'failed', 'cancelled',
]
const importSeverities: Poe2ImportIssueSeverity[] = ['info', 'warning', 'error', 'blocking']

function isPoe2ImportIssue(value: unknown): value is Poe2ImportIssue {
  return record(value) && text(value['code']) && Boolean(value['code'])
    && text(value['path']) && importSeverities.includes(value['severity'] as Poe2ImportIssueSeverity)
    && text(value['message']) && Boolean(value['message'])
}

export function isPoe2Import(value: unknown): value is Poe2Import {
  if (!record(value) || !ownerFree(value)
    || !text(value['id']) || !value['id']
    || !importStatuses.includes(value['status'] as Poe2ImportStatus)
    || !text(value['provider']) || !['wegame', 'ninja'].includes(value['provider'])
    || !(value['preview'] === null || record(value['preview']))
    || !Array.isArray(value['issues']) || !value['issues'].every(isPoe2ImportIssue)
    || !(value['nextAction'] === null || text(value['nextAction']))
    || !(value['buildId'] === null || text(value['buildId']) && Boolean(value['buildId']))
    || !(value['baselineJobId'] === null || text(value['baselineJobId']) && Boolean(value['baselineJobId']))
    || !Number.isInteger(value['attempt']) || Number(value['attempt']) < 0
    || !date(value['updatedAt'])) return false
  return value['status'] !== 'ready' || Boolean(value['buildId']) && Boolean(value['baselineJobId'])
}
