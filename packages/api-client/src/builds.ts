import type {
  BuildsDataStatus,
  BuildsDetailPayload,
  BuildsHomePayload,
  BuildsIntelPayload,
  BuildQuickAction,
  ClassOption,
  RaiderIOSourceStatus,
  RaiderIOSummary,
  SpecializationOption,
} from '@wow-mini/domain'

import {
  buildsHomeFallbackSnapshot,
  buildsIntelFallbackSnapshot,
} from './fallback-snapshots'
import { isNonEmptyString, isRecord } from './guards'
import type { ApiResult, ApiTransport } from './transport'

type ActionDisplayMeta = Required<Pick<
  BuildQuickAction,
  'phaseLabel' | 'actionLabel' | 'scopeLabel' | 'evidenceLabel' | 'impactLabel'
>>

type BuildsHomeWireSpecialization = Omit<SpecializationOption, 'name'> & { name?: string }
type BuildsHomeWireClass = Omit<ClassOption, 'specializations'> & {
  specializations: readonly BuildsHomeWireSpecialization[]
}
type BuildsHomeWirePayload = Omit<BuildsHomePayload, 'classOptions' | 'raiderio'> & {
  classOptions: readonly BuildsHomeWireClass[]
  raiderio?: RaiderIOSummary
}

const actionMeta: Readonly<Record<BuildQuickAction['key'], ActionDisplayMeta>> = {
  talents: { phaseLabel: '输入', actionLabel: '整理天赋', scopeLabel: '天赋树', evidenceLabel: 'WebSim / 模板', impactLabel: '决定构筑基础' },
  gear: { phaseLabel: '输入', actionLabel: '补齐装备', scopeLabel: '16 槽装备', evidenceLabel: '装备库 / 模板', impactLabel: '决定 SimC 可提交性' },
  simc: { phaseLabel: '验证', actionLabel: '模拟校验', scopeLabel: '固定模板', evidenceLabel: '天赋 + 装备', impactLabel: '生成可追踪任务' },
  tasks: { phaseLabel: '追踪', actionLabel: '查看任务', scopeLabel: '历史任务', evidenceLabel: 'SimC 结果', impactLabel: '继续复盘行动' },
}

const actionKeys = ['talents', 'gear', 'simc', 'tasks'] as const
const buildsDataStatuses = [
  'verified',
  'partial',
  'stale',
  'blocked',
  'missing_credentials',
  'pending_official_audit',
] as const satisfies readonly BuildsDataStatus[]
const raiderioSourceStatuses = [
  'synced',
  'verified',
  'partial',
  'stale',
  'blocked',
  'missing_credentials',
  'source_reference',
] as const satisfies readonly RaiderIOSourceStatus[]

const fallbackRaiderio: RaiderIOSummary = {
  sourceName: 'Raider.IO',
  sourceStatus: 'blocked',
  sourceStatusLabel: 'Raider.IO blocked',
  seasonSlug: '',
  region: '',
  checkedAt: '',
  expiresAt: '',
  analysisWindow: '',
  sampleCount: 0,
  maxKeyLevel: 0,
  bestScore: 0,
  numericValuesUsable: false,
  sourceUrl: 'https://raider.io/mythic-plus-rankings',
}

function isBuildsDataStatus(value: unknown): value is BuildsDataStatus {
  return typeof value === 'string' && (buildsDataStatuses as readonly string[]).includes(value)
}

function isRaiderIOSourceStatus(value: unknown): value is RaiderIOSourceStatus {
  return typeof value === 'string' && (raiderioSourceStatuses as readonly string[]).includes(value)
}

function hasOptionalStrings(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => value[key] === undefined || typeof value[key] === 'string')
}

function hasOptionalNonNegativeNumbers(value: Record<string, unknown>, keys: readonly string[]): boolean {
  return keys.every((key) => {
    const candidate = value[key]
    return candidate === undefined
      || (typeof candidate === 'number' && Number.isFinite(candidate) && candidate >= 0)
  })
}

function isSourceReference(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value['name'])
    && isNonEmptyString(value['url'])
    && (value['note'] === undefined || typeof value['note'] === 'string')
}

function isSourceReferenceList(value: unknown): boolean {
  return Array.isArray(value) && value.every(isSourceReference)
}

function isSeasonDungeon(value: unknown): boolean {
  return isRecord(value)
    && isNonEmptyString(value['id'])
    && isNonEmptyString(value['name'])
    && hasOptionalStrings(value, ['dungeonId', 'instanceId', 'shortName'])
    && (value['timerSeconds'] === undefined
      || (typeof value['timerSeconds'] === 'number' && Number.isFinite(value['timerSeconds']) && value['timerSeconds'] >= 0))
    && (value['sourceRefs'] === undefined || isSourceReferenceList(value['sourceRefs']))
}

function isSeasonRaid(value: unknown): boolean {
  return isRecord(value)
    && typeof value['id'] === 'string'
    && isNonEmptyString(value['name'])
    && hasOptionalStrings(value, ['raidId', 'instanceId', 'category'])
}

function isSeasonSnapshot(value: unknown): boolean {
  if (!isRecord(value)
    || !(isNonEmptyString(value['id']) || isNonEmptyString(value['seasonId']))
    || !(isNonEmptyString(value['label']) || isNonEmptyString(value['seasonLabel']))
    || !(isNonEmptyString(value['revision']) || isNonEmptyString(value['seasonRevision']))
    || !isNonEmptyString(value['verifiedAt'])
    || !isNonEmptyString(value['expiresAt'])
    || !isBuildsDataStatus(value['dataStatus'])
    || !isSourceReferenceList(value['sourceRefs'])
    || !hasOptionalStrings(value, ['id', 'seasonId', 'label', 'seasonLabel', 'revision', 'seasonRevision', 'locale'])) return false

  if (value['errors'] !== undefined
    && (!Array.isArray(value['errors']) || !value['errors'].every((error) => typeof error === 'string'))) return false
  if (value['dungeons'] !== undefined
    && (!Array.isArray(value['dungeons']) || !value['dungeons'].every(isSeasonDungeon))) return false
  if (value['raids'] !== undefined
    && (!Array.isArray(value['raids']) || !value['raids'].every(isSeasonRaid))) return false
  return true
}

function isRaiderIOSummary(value: unknown): value is RaiderIOSummary {
  if (!isRecord(value)
    || !isNonEmptyString(value['sourceName'])
    || !isRaiderIOSourceStatus(value['sourceStatus'])
    || typeof value['sourceStatusLabel'] !== 'string'
    || !isNonEmptyString(value['sourceUrl'])) return false

  const stringFields = ['seasonSlug', 'region', 'checkedAt', 'expiresAt', 'analysisWindow'] as const
  if (!stringFields.every((key) => typeof value[key] === 'string')) return false
  if (!['sampleCount', 'maxKeyLevel', 'bestScore'].every((key) => {
    const candidate = value[key]
    return typeof candidate === 'number' && Number.isFinite(candidate) && candidate >= 0
  })) return false
  if (value['numericValuesUsable'] !== undefined && typeof value['numericValuesUsable'] !== 'boolean') return false
  return value['numericValuesUsable'] !== true
    || (['synced', 'verified'].includes(value['sourceStatus']) && Number(value['sampleCount']) > 0)
}

function isBuildQuickAction(value: unknown): value is BuildQuickAction {
  return isRecord(value)
    && actionKeys.includes(value['key'] as BuildQuickAction['key'])
    && isNonEmptyString(value['title'])
    && isNonEmptyString(value['desc'])
    && hasOptionalStrings(value, ['phaseLabel', 'actionLabel', 'scopeLabel', 'evidenceLabel', 'impactLabel'])
}

function hasAllBuildQuickActions(value: unknown): value is readonly BuildQuickAction[] {
  if (!Array.isArray(value) || value.length !== actionKeys.length || !value.every(isBuildQuickAction)) return false
  const keys = new Set(value.map((action) => action.key))
  return keys.size === actionKeys.length && actionKeys.every((key) => keys.has(key))
}

function isWireSpecialization(
  value: unknown,
  className: string,
  websimClassKey: string,
): value is BuildsHomeWireSpecialization {
  if (!isRecord(value)
    || !isNonEmptyString(value['id'])
    || value['className'] !== className
    || value['websimClassKey'] !== websimClassKey
    || !isNonEmptyString(value['websimSpecKey'])
    || !isNonEmptyString(value['role'])
    || !isNonEmptyString(value['sourceName'])
    || !isNonEmptyString(value['sourceUrl'])
    || !(isNonEmptyString(value['name']) || isNonEmptyString(value['specName']) || isNonEmptyString(value['title']))) return false

  if (!hasOptionalStrings(value, [
    'name',
    'specId',
    'title',
    'specName',
    'classKey',
    'specKey',
    'heroKey',
    'heroLabel',
    'status',
    'classSlug',
    'specSlug',
    'iconUrl',
    'classIconUrl',
    'specIconUrl',
    'desc',
    'sourceName',
    'sourceUrl',
    'sourceNote',
    'publishedAt',
    'analysisWindow',
  ])) return false
  if (value['dataStatus'] !== undefined && !isBuildsDataStatus(value['dataStatus'])) return false
  if (value['raiderio'] !== undefined && !isRaiderIOSummary(value['raiderio'])) return false
  if (value['raiderioSourceStatus'] !== undefined && !isRaiderIOSourceStatus(value['raiderioSourceStatus'])) return false
  return hasOptionalNonNegativeNumbers(value, ['sampleCount', 'maxKeyLevel', 'bestScore'])
}

function isWireClassOption(value: unknown): value is BuildsHomeWireClass {
  if (!isRecord(value)
    || !isNonEmptyString(value['name'])
    || !isNonEmptyString(value['websimClassKey'])
    || !hasOptionalStrings(value, ['id', 'iconUrl'])
    || !Array.isArray(value['specializations'])
    || value['specializations'].length === 0) return false
  return value['specializations'].every((specialization) => (
    isWireSpecialization(specialization, value['name'] as string, value['websimClassKey'] as string)
  ))
}

function isSpecializationSummary(value: unknown): boolean {
  if (!isRecord(value)
    || !isNonEmptyString(value['id'])
    || !isNonEmptyString(value['className'])
    || !isNonEmptyString(value['specName'])
    || !isNonEmptyString(value['role'])
    || !isNonEmptyString(value['title'])) return false
  if (value['raiderio'] !== undefined && !isRaiderIOSummary(value['raiderio'])) return false
  if (value['raiderioSourceStatus'] !== undefined && !isRaiderIOSourceStatus(value['raiderioSourceStatus'])) return false
  return hasOptionalNonNegativeNumbers(value, ['sampleCount', 'maxKeyLevel', 'bestScore'])
}

export function isBuildsHomePayload(value: unknown): value is BuildsHomeWirePayload {
  if (!isRecord(value)
    || !isNonEmptyString(value['navTitle'])
    || !isNonEmptyString(value['kicker'])
    || !isNonEmptyString(value['title'])
    || !isNonEmptyString(value['desc'])
    || !isNonEmptyString(value['lastAnalyzedAt'])
    || !isNonEmptyString(value['analysisWindow'])
    || !isNonEmptyString(value['seasonId'])
    || !isNonEmptyString(value['seasonLabel'])
    || !isNonEmptyString(value['seasonRevision'])
    || !isNonEmptyString(value['verifiedAt'])
    || !isNonEmptyString(value['expiresAt'])
    || !isNonEmptyString(value['locale'])
    || !isBuildsDataStatus(value['dataStatus'])
    || !hasAllBuildQuickActions(value['quickActions'])
    || !Array.isArray(value['classOptions'])
    || !value['classOptions'].every(isWireClassOption)
    || !Array.isArray(value['featuredSpecializations'])
    || !value['featuredSpecializations'].every(isSpecializationSummary)
    || !isSourceReferenceList(value['trustedSources'])
    || !isSourceReferenceList(value['sourceRefs'])
    || !isSeasonSnapshot(value['currentSeason'])
    || !isRaiderIOSummary(value['raiderio'])) return false

  if (value['blockedReason'] !== undefined && typeof value['blockedReason'] !== 'string') return false
  if (value['raiderioError'] !== undefined && typeof value['raiderioError'] !== 'string') return false
  if (['blocked', 'missing_credentials', 'pending_official_audit'].includes(value['dataStatus'])
    && !isNonEmptyString(value['blockedReason'])) return false

  const season = value['currentSeason']
  if (!isRecord(season) || season['dataStatus'] !== value['dataStatus']) return false
  const seasonId = season['seasonId'] || season['id']
  const seasonLabel = season['seasonLabel'] || season['label']
  const seasonRevision = season['seasonRevision'] || season['revision']
  return value['seasonId'] === seasonId
    && value['seasonLabel'] === seasonLabel
    && value['seasonRevision'] === seasonRevision
    && value['verifiedAt'] === season['verifiedAt']
    && value['expiresAt'] === season['expiresAt']
    && (season['locale'] === undefined || value['locale'] === season['locale'])
}

function normalizeAction(action: BuildQuickAction): BuildQuickAction {
  const meta = actionMeta[action.key]
  return {
    ...action,
    phaseLabel: isNonEmptyString(action.phaseLabel) ? action.phaseLabel : meta.phaseLabel,
    actionLabel: isNonEmptyString(action.actionLabel) ? action.actionLabel : meta.actionLabel,
    scopeLabel: isNonEmptyString(action.scopeLabel) ? action.scopeLabel : meta.scopeLabel,
    evidenceLabel: isNonEmptyString(action.evidenceLabel) ? action.evidenceLabel : meta.evidenceLabel,
    impactLabel: isNonEmptyString(action.impactLabel) ? action.impactLabel : meta.impactLabel,
  }
}

function normalizedSpecializationName(specialization: BuildsHomeWireSpecialization): string {
  for (const candidate of [specialization.name, specialization.specName, specialization.title]) {
    if (isNonEmptyString(candidate)) return candidate.trim()
  }
  return ''
}

function normalizeRaiderIO(summary: RaiderIOSummary): RaiderIOSummary {
  const numericValuesUsable = summary.numericValuesUsable === true
    && ['synced', 'verified'].includes(summary.sourceStatus)
    && summary.sampleCount > 0
  return { ...summary, numericValuesUsable }
}

function normalizeHome(payload: BuildsHomeWirePayload, fromFallback: boolean): BuildsHomePayload {
  const sourceRaiderio = payload.raiderio
  const raiderio = normalizeRaiderIO(fromFallback
    ? sourceRaiderio
      ? ['synced', 'verified', 'source_reference'].includes(sourceRaiderio.sourceStatus)
        ? { ...sourceRaiderio, sourceStatus: 'stale' as const, sourceStatusLabel: 'Raider.IO stale' }
        : sourceRaiderio
      : fallbackRaiderio
    : sourceRaiderio ?? fallbackRaiderio)
  return {
    ...payload,
    quickActions: payload.quickActions.map(normalizeAction),
    classOptions: payload.classOptions.map((classOption) => ({
      ...classOption,
      specializations: classOption.specializations.map((specialization) => ({
        ...specialization,
        name: normalizedSpecializationName(specialization),
      })),
    })),
    currentSeason: {
      ...payload.currentSeason,
      dataStatus: fromFallback ? 'stale' : payload.currentSeason.dataStatus ?? payload.dataStatus,
    },
    dataStatus: fromFallback ? 'stale' : payload.dataStatus,
    raiderio,
  }
}

function isBuildsIntel(value: unknown): value is BuildsIntelPayload {
  return isRecord(value) && Array.isArray(value['items'])
}

function isBuildsDetail(value: unknown): value is BuildsDetailPayload {
  return isRecord(value)
    && typeof value['id'] === 'string'
    && isRecord(value['details'])
}

function fallbackDetail(specId: string): BuildsDetailPayload {
  const summary = buildsIntelFallbackSnapshot.items.find((item) => item.id === specId)
    ?? buildsIntelFallbackSnapshot.items[0]
  return {
    id: specId,
    className: summary?.className ?? '',
    specName: summary?.specName ?? '',
    role: summary?.role ?? '',
    title: summary?.title ?? specId,
    status: 'blocked',
    desc: '后端不可用，专精详情未加载。',
    dataStatus: 'blocked',
    details: {},
  }
}

export interface BuildsClient {
  home(): Promise<ApiResult<BuildsHomePayload>>
  intel(): Promise<ApiResult<BuildsIntelPayload>>
  detail(specId: string): Promise<ApiResult<BuildsDetailPayload>>
}

export function createBuildsClient(transport: ApiTransport): BuildsClient {
  return {
    home() {
      return transport.requestEndpoint<BuildsHomeWirePayload>('builds.home', '/api/builds/home', {
        fallback: () => normalizeHome(buildsHomeFallbackSnapshot, true),
        validate: isBuildsHomePayload,
      }).then((result) => ({
        ...result,
        payload: normalizeHome(result.payload, result.fromFallback),
      }))
    },
    intel() {
      return transport.requestEndpoint('builds.intel', '/api/builds/intel', {
        fallback: () => buildsIntelFallbackSnapshot,
        validate: isBuildsIntel,
      })
    },
    detail(specId) {
      return transport.requestEndpoint('builds.detail', `/api/builds/detail?id=${encodeURIComponent(specId)}`, {
        fallback: () => fallbackDetail(specId),
        validate: isBuildsDetail,
      })
    },
  }
}
