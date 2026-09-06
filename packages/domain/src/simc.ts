import { isSimulationCharacter, isSimulationReport, isSimulationScenario, type SimulationCharacter, type SimulationReport, type SimulationScenario } from './simc-workbench'

export type SourceProvider = 'raiderio' | 'warcraftlogs'
export type SourceReadiness =
  | 'INVALID_LINK'
  | 'CHARACTER_NOT_FOUND'
  | 'ACCESS_RESTRICTED'
  | 'SNAPSHOT_UNAVAILABLE'
  | 'INCOMPLETE_FOR_SIMC'
  | 'READY_FOR_SIMC'

export type SimulationJobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
export type SimulationMetricName = 'dps' | 'hps'

export interface SourceSnapshotProvenance {
  sourceRevision: string | null
  sourceRawSha256: string
}

export interface SourceSnapshotView {
  character?: SimulationCharacter | null
  id: string
  provider: SourceProvider
  sourceUrl: string
  sourceKey: string
  revision: number
  readiness: SourceReadiness
  missingFields: readonly string[]
  blockers: readonly string[]
  fetchedAt: string
  provenance: SourceSnapshotProvenance
}

export interface SimulationJobSummary {
  character?: SimulationCharacter | null
  scenario?: SimulationScenario | null
  metric?: { name: SimulationMetricName; value: number } | null
  id: string
  snapshotId: string
  status: SimulationJobStatus
  scenarioHash: string
  compilerRevision: string
  runtimeRevision: string
  errorCode: string | null
  createdAt: string
  updatedAt: string
}

export interface SimulationAttemptView {
  attemptNumber: number
  startedAt: string
  finishedAt: string | null
  exitCode: number | null
  diagnosticCode: string | null
}

export interface SimulationResultProvenance {
  snapshotId: string
  sourceRevision: string
  sourceRawSha256: string
  profileSha256: string
  compilerRevision: string
  runtimeRevision: string
  scenarioHash: string
}

export interface SimulationResultView {
  report?: SimulationReport | null
  id: string
  profileSha256: string
  metricName: SimulationMetricName
  metricValue: number
  compilerRevision: string
  runtimeRevision: string
  provenance: SimulationResultProvenance
  createdAt: string
}

export interface SimulationJobDetail extends SimulationJobSummary {
  attempts: readonly SimulationAttemptView[]
  result: SimulationResultView | null
}

export interface SimulationJobPage {
  items: readonly SimulationJobSummary[]
  nextCursor: string | null
}


function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function exactKeys(value: Record<string, unknown>, keys: readonly string[], optional: readonly string[] = []): boolean {
  const actual = Object.keys(value)
  return keys.every(key => actual.includes(key)) && actual.every((key) => keys.includes(key) || optional.includes(key))
}

function workbenchSummary(value: Record<string, unknown>): boolean {
  const metric = value['metric']
  return (!('character' in value) || value['character'] === null || isSimulationCharacter(value['character']))
    && (!('scenario' in value) || value['scenario'] === null || isSimulationScenario(value['scenario']))
    && (!('metric' in value) || metric === null || (record(metric) && exactKeys(metric, ['name', 'value']) && (metric['name'] === 'dps' || metric['name'] === 'hps') && typeof metric['value'] === 'number' && Number.isFinite(metric['value']) && metric['value'] > 0))
}

function boundedString(value: unknown, maximum = 160): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= maximum
}

function isoDate(value: unknown): value is string {
  return boundedString(value, 128) && Number.isFinite(Date.parse(value))
}

function uuid(value: unknown): value is string {
  return typeof value === 'string'
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/iu.test(value)
}

function sha256(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/u.test(value)
}

function positiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value > 0
}

function code(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_.-]{1,128}$/u.test(value)
}

function codeList(value: unknown): value is readonly string[] {
  return Array.isArray(value) && value.length <= 64 && value.every(code)
}

function isSourceSnapshotProvenance(value: unknown): value is SourceSnapshotProvenance {
  if (!record(value) || !exactKeys(value, ['sourceRevision', 'sourceRawSha256'])) return false
  return (value['sourceRevision'] === null || boundedString(value['sourceRevision']))
    && sha256(value['sourceRawSha256'])
}

export function isSourceSnapshotView(value: unknown): value is SourceSnapshotView {
  if (!record(value) || !exactKeys(value, [
    'id',
    'provider',
    'sourceUrl',
    'sourceKey',
    'revision',
    'readiness',
    'missingFields',
    'blockers',
    'fetchedAt',
    'provenance',
  ], ['character'])) return false
  const readiness = value['readiness']
  return (!('character' in value) || value['character'] === null || isSimulationCharacter(value['character']))
    && uuid(value['id'])
    && (value['provider'] === 'raiderio' || value['provider'] === 'warcraftlogs')
    && boundedString(value['sourceUrl'], 2048)
    && /^https:\/\//u.test(value['sourceUrl'])
    && boundedString(value['sourceKey'], 512)
    && positiveInteger(value['revision'])
    && (
      readiness === 'INVALID_LINK'
      || readiness === 'CHARACTER_NOT_FOUND'
      || readiness === 'ACCESS_RESTRICTED'
      || readiness === 'SNAPSHOT_UNAVAILABLE'
      || readiness === 'INCOMPLETE_FOR_SIMC'
      || readiness === 'READY_FOR_SIMC'
    )
    && codeList(value['missingFields'])
    && codeList(value['blockers'])
    && isoDate(value['fetchedAt'])
    && isSourceSnapshotProvenance(value['provenance'])
}

function isSimulationJobSummaryRecord(value: unknown): value is SimulationJobSummary {
  if (!record(value) || !exactKeys(value, [
    'id',
    'snapshotId',
    'status',
    'scenarioHash',
    'compilerRevision',
    'runtimeRevision',
    'errorCode',
    'createdAt',
    'updatedAt',
  ], ['character', 'scenario', 'metric'])) return false
  const status = value['status']
  return workbenchSummary(value) && uuid(value['id'])
    && uuid(value['snapshotId'])
    && (
      status === 'queued'
      || status === 'running'
      || status === 'succeeded'
      || status === 'failed'
      || status === 'cancelled'
    )
    && sha256(value['scenarioHash'])
    && boundedString(value['compilerRevision'])
    && boundedString(value['runtimeRevision'])
    && (value['errorCode'] === null || code(value['errorCode']))
    && isoDate(value['createdAt'])
    && isoDate(value['updatedAt'])
}

function isSimulationAttemptView(value: unknown): value is SimulationAttemptView {
  if (!record(value) || !exactKeys(value, [
    'attemptNumber',
    'startedAt',
    'finishedAt',
    'exitCode',
    'diagnosticCode',
  ])) return false
  return positiveInteger(value['attemptNumber'])
    && isoDate(value['startedAt'])
    && (value['finishedAt'] === null || isoDate(value['finishedAt']))
    && (value['exitCode'] === null || (typeof value['exitCode'] === 'number' && Number.isInteger(value['exitCode'])))
    && (value['diagnosticCode'] === null || code(value['diagnosticCode']))
}

function isSimulationResultProvenance(value: unknown): value is SimulationResultProvenance {
  if (!record(value) || !exactKeys(value, [
    'snapshotId',
    'sourceRevision',
    'sourceRawSha256',
    'profileSha256',
    'compilerRevision',
    'runtimeRevision',
    'scenarioHash',
  ])) return false
  return uuid(value['snapshotId'])
    && boundedString(value['sourceRevision'])
    && sha256(value['sourceRawSha256'])
    && sha256(value['profileSha256'])
    && boundedString(value['compilerRevision'])
    && boundedString(value['runtimeRevision'])
    && sha256(value['scenarioHash'])
}

function isSimulationResultView(value: unknown): value is SimulationResultView {
  if (!record(value) || !exactKeys(value, [
    'id',
    'profileSha256',
    'metricName',
    'metricValue',
    'compilerRevision',
    'runtimeRevision',
    'provenance',
    'createdAt',
  ], ['report'])) return false
  return (!('report' in value) || value['report'] === null || (isSimulationReport(value['report']) && value['report'].metric.name === value['metricName'] && value['report'].metric.value === value['metricValue']))
    && uuid(value['id'])
    && sha256(value['profileSha256'])
    && (value['metricName'] === 'dps' || value['metricName'] === 'hps')
    && typeof value['metricValue'] === 'number'
    && Number.isFinite(value['metricValue'])
    && value['metricValue'] > 0
    && boundedString(value['compilerRevision'])
    && boundedString(value['runtimeRevision'])
    && isSimulationResultProvenance(value['provenance'])
    && isoDate(value['createdAt'])
}

export function isSimulationJobPage(value: unknown): value is SimulationJobPage {
  if (!record(value) || !exactKeys(value, ['items', 'nextCursor'])) return false
  return Array.isArray(value['items'])
    && value['items'].length <= 50
    && value['items'].every(isSimulationJobSummaryRecord)
    && (value['nextCursor'] === null || boundedString(value['nextCursor'], 1024))
}

export function isSimulationJobDetail(value: unknown): value is SimulationJobDetail {
  if (!record(value) || !exactKeys(value, [
    'id',
    'snapshotId',
    'status',
    'scenarioHash',
    'compilerRevision',
    'runtimeRevision',
    'errorCode',
    'createdAt',
    'updatedAt',
    'attempts',
    'result',
  ], ['character', 'scenario', 'metric'])) return false
  if (!workbenchSummary(value)) return false
  const summary: Record<string, unknown> = {
    id: value['id'],
    snapshotId: value['snapshotId'],
    status: value['status'],
    scenarioHash: value['scenarioHash'],
    compilerRevision: value['compilerRevision'],
    runtimeRevision: value['runtimeRevision'],
    errorCode: value['errorCode'],
    createdAt: value['createdAt'],
    updatedAt: value['updatedAt'],
  }
  if (
    !isSimulationJobSummaryRecord(summary)
    || !Array.isArray(value['attempts'])
    || value['attempts'].length > 20
    || !value['attempts'].every(isSimulationAttemptView)
  ) return false
  if (value['result'] === null) return value['status'] !== 'succeeded'
  if (value['status'] !== 'succeeded' || !isSimulationResultView(value['result'])) return false
  const result = value['result']
  return result.compilerRevision === value['compilerRevision']
    && result.runtimeRevision === value['runtimeRevision']
    && result.profileSha256 === result.provenance.profileSha256
    && result.provenance.snapshotId === value['snapshotId']
    && result.provenance.compilerRevision === value['compilerRevision']
    && result.provenance.runtimeRevision === value['runtimeRevision']
    && result.provenance.scenarioHash === value['scenarioHash']
}

export function isSimulationJobSummary(value: unknown): value is SimulationJobSummary {
  return isSimulationJobSummaryRecord(value)
}
