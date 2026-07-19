import type {
  BuildTemplate,
  BuildsHomePayload,
  ReadinessState,
  VerifiedWowObjectReference,
  WebsimGearPayload,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

import { findSpecSelection, scenarioOptions, specObject, type SpecSelection } from '../_shared/build-context'
import { cachedDataPresentation } from '../_shared/data-presentation'

export type WorkbenchModuleId = 'talents' | 'gear' | 'simc' | 'assistant'

export interface WorkbenchSourceResult {
  fromFallback: boolean
  error: string
}

export interface WorkbenchDataSources {
  home: WorkbenchSourceResult
  talents: WorkbenchSourceResult
  gear: WorkbenchSourceResult
  talentTemplates: WorkbenchSourceResult
  gearTemplates: WorkbenchSourceResult
}

export interface CurrentSpecWorkbenchPayload {
  home: BuildsHomePayload
  talents: WebsimTalentsPayload
  gear: WebsimGearPayload
  talentTemplates: readonly BuildTemplate[]
  gearTemplates: readonly BuildTemplate[]
  sources: WorkbenchDataSources
}

export interface WorkbenchModuleView {
  id: WorkbenchModuleId
  title: string
  summary: string
  detail: string
  state: ReadinessState
  stateLabel: string
  actionLabel: string
  disabled: boolean
}

export interface WorkbenchEvidenceView {
  id: string
  label: string
  value: string
  detail: string
  state: ReadinessState
  stateLabel: string
  sourceCountLabel: string
  blockerCountLabel: string
  revisionLabel: string
  actionLabel: string
}

export interface CurrentSpecWorkbenchModel {
  initialLoading: boolean
  selection: SpecSelection | null
  identity: VerifiedWowObjectReference | null
  identityState: ReadinessState
  identitySourceLabel: string
  title: string
  contextDetail: string
  scenarioKey: string
  scenarioLabel: string
  overallState: ReadinessState
  overallLabel: string
  readinessHeadline: string
  readinessReasons: readonly string[]
  overallDetail: string
  modules: readonly WorkbenchModuleView[]
  evidence: readonly WorkbenchEvidenceView[]
  blockers: readonly string[]
  primaryAction: {
    kind: 'module' | 'retry'
    moduleId: WorkbenchModuleId
    label: string
    disabled: boolean
  }
}

export interface BuildCurrentSpecWorkbenchModelInput {
  payload?: CurrentSpecWorkbenchPayload
  routeState: ReadinessState
  selectedSpecId?: string
  scenarioKey?: string
}

function unique(values: readonly (string | undefined)[]): readonly string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value?.trim())).map((value) => value.trim()))]
}

function routeDegradedState(routeState: ReadinessState): ReadinessState | null {
  if (routeState === 'loading') return 'loading'
  if (routeState === 'error' || routeState === 'blocked' || routeState === 'empty' || routeState === 'stale') return routeState
  return null
}

function sourceState(
  routeState: ReadinessState,
  source: WorkbenchSourceResult | undefined,
  available: boolean,
  partial: boolean,
): ReadinessState {
  const degraded = routeDegradedState(routeState)
  if (degraded) return degraded
  if (source?.fromFallback) return available ? 'stale' : 'blocked'
  if (available && !partial) return 'ready'
  if (available || partial) return 'partial'
  return 'blocked'
}

function stateLabel(state: ReadinessState): string {
  const labels: Readonly<Record<ReadinessState, string>> = {
    loading: '读取中',
    empty: '暂无数据',
    error: '请求失败',
    blocked: '存在阻断',
    partial: '部分可用',
    ready: '可继续',
    stale: cachedDataPresentation.stateLabel,
    source_reference: '来源参考',
    unknown: '待校验',
  }
  return labels[state]
}

function templateState(
  routeState: ReadinessState,
  templates: readonly BuildTemplate[],
  sources: readonly (WorkbenchSourceResult | undefined)[],
): ReadinessState {
  const degraded = routeDegradedState(routeState)
  if (degraded && degraded !== 'stale') return degraded
  const fallback = sources.some((source) => source?.fromFallback)
  if (fallback) return templates.length ? 'stale' : 'blocked'
  return templates.length ? 'ready' : 'empty'
}

function templateSummary(
  templates: readonly BuildTemplate[],
  state: ReadinessState,
): string {
  if (state === 'loading') return '正在读取模板'
  if (state === 'blocked') return '远端模板受限，本地暂无模板'
  if (state === 'stale') return `仅本地模板 ${templates.length} 个`
  if (state === 'empty') return '尚未保存模板'
  return `可用模板 ${templates.length} 个`
}

function scenario(inputKey?: string): { key: string; title: string } {
  const selected = scenarioOptions.find((item) => item.key === inputKey) ?? scenarioOptions[0]
  return selected ?? { key: 'single', title: '单体' }
}

function sourceCountLabel(count: number, fallback: boolean): string {
  return !fallback && count > 0 ? `来源 ${count}` : '来源 --'
}

function blockerCountLabel(count: number): string {
  return `阻断 ${count}`
}

function compactRevisionLabel(value: string | undefined, prefix: string): string {
  if (!value) return '待核验'
  if (value.length <= 8) return value
  const revision = value.match(/(?:^|[-_])v?(\d+(?:\.\d+)*)$/i)?.[1]
  return revision ? `${prefix} v${revision}` : '已修订'
}

function readinessHeadline(state: ReadinessState): string {
  const labels: Readonly<Record<ReadinessState, string>> = {
    loading: '正在读取当前输入',
    empty: '当前专精没有可用输入',
    error: '工作台读取失败',
    blocked: '当前不可提交模拟',
    partial: '仍有输入未就绪',
    ready: '输入已通过准备检查',
    stale: cachedDataPresentation.activeDetail,
    source_reference: '输入来源已建立',
    unknown: '输入状态待校验',
  }
  return labels[state]
}

export function buildCurrentSpecWorkbenchModel({
  payload,
  routeState,
  selectedSpecId,
  scenarioKey,
}: BuildCurrentSpecWorkbenchModelInput): CurrentSpecWorkbenchModel {
  const selectedScenario = scenario(scenarioKey)
  const selection = payload ? findSpecSelection(payload.home, selectedSpecId) : null
  const initialLoading = routeState === 'loading' && !payload
  const talentNodeCount = payload?.talents.nodes.length ?? 0
  const talentReadiness = payload?.talents.talentReadiness
  const talentSimcReady = talentReadiness?.simcReady === true
    || (payload?.talents.talentStatus === 'simc' && talentNodeCount > 0)
  const talentWarnings = unique([
    ...(payload?.talents.blockers ?? []),
    ...(talentReadiness?.blockers ?? []),
    ...(payload?.talents.errors ?? []),
  ])
  const talentState = sourceState(
    routeState,
    payload?.sources.talents,
    talentNodeCount > 0,
    !talentSimcReady || talentWarnings.length > 0,
  )

  const gearCatalogAvailable = payload?.gear.catalogStatus === 'verified'
  const gearState = sourceState(
    routeState,
    payload?.sources.gear,
    gearCatalogAvailable,
    gearCatalogAvailable,
  )
  const gearBlockers = unique([
    ...(payload?.gear.catalogBlockers ?? []),
    ...(gearCatalogAvailable && routeState !== 'loading'
      ? ['当前工作台没有后端校验过的装备草稿']
      : !initialLoading
        ? ['装备目录当前不可用']
        : []),
  ])

  const templates = [...(payload?.talentTemplates ?? []), ...(payload?.gearTemplates ?? [])]
  const templatesState = templateState(routeState, templates, [
    payload?.sources.talentTemplates,
    payload?.sources.gearTemplates,
  ])
  const simcReady = false
  const simcPartial = Boolean(selection && (talentSimcReady || gearCatalogAvailable))
  const simcState = sourceState(
    routeState,
    payload?.sources.gear.fromFallback || payload?.sources.talents.fromFallback
      ? { fromFallback: true, error: '' }
      : { fromFallback: false, error: '' },
    simcReady,
    simcPartial && !simcReady,
  )
  const assistantState: ReadinessState = initialLoading
    ? 'loading'
    : selection
      ? 'source_reference'
      : 'blocked'
  const templateStatusSummary = templateSummary(templates, templatesState)

  const modules: readonly WorkbenchModuleView[] = [
    {
      id: 'talents',
      title: '天赋',
      summary: initialLoading ? '读取天赋目录' : `${talentNodeCount} 个节点`,
      detail: talentSimcReady ? '编码输入可用于 SimC，描述完整性单独追踪' : '天赋输入尚未达到 SimC-ready',
      state: talentState,
      stateLabel: stateLabel(talentState),
      actionLabel: '整理天赋',
      disabled: !selection || talentState === 'loading' || talentState === 'blocked' || talentState === 'error',
    },
    {
      id: 'gear',
      title: '装备',
      summary: initialLoading ? '读取装备目录' : gearCatalogAvailable ? '当前装备待校验' : '装备目录不可用',
      detail: gearCatalogAvailable ? '进入装备页选择真实装备并由后端校验' : '当前没有可用的 canonical 装备目录',
      state: gearState,
      stateLabel: stateLabel(gearState),
      actionLabel: '补齐装备',
      disabled: !selection || gearState === 'loading' || gearState === 'blocked' || gearState === 'error',
    },
    {
      id: 'simc',
      title: 'SimC',
      summary: simcReady ? '提交前检查通过' : '仍有输入阻断',
      detail: simcReady ? '进入提交页进行最终 profile 校验' : '不会在输入不完整时生成模拟结论',
      state: simcState,
      stateLabel: stateLabel(simcState),
      actionLabel: '模拟校验',
      disabled: !selection || simcState === 'loading' || simcState === 'blocked' || simcState === 'error',
    },
    {
      id: 'assistant',
      title: '队长',
      summary: selection ? '带入专精与阻断' : '缺少专精上下文',
      detail: '只使用当前授权的工作台证据，不生成无来源数字',
      state: assistantState,
      stateLabel: stateLabel(assistantState),
      actionLabel: '询问阻断',
      disabled: !selection || assistantState === 'loading' || assistantState === 'blocked',
    },
  ]

  const hardBlockers = unique([
    ...(!selection && !initialLoading ? ['没有可用的职业专精映射'] : []),
    ...(!talentSimcReady && !initialLoading ? talentWarnings.length ? talentWarnings : ['天赋输入尚未达到 SimC-ready'] : []),
    ...(!initialLoading ? gearBlockers.length ? gearBlockers : ['装备输入尚未达到 SimC-ready'] : []),
  ])
  const talentSourceCount = payload?.sources.talents.fromFallback ? 0 : payload?.talents.sourceRefs?.length ?? 0
  const gearSourceCount = payload?.sources.gear.fromFallback ? 0 : payload?.gear.sourceRefs?.length ?? 0
  const simcSourceCount = talentSourceCount + gearSourceCount
  const evidence: readonly WorkbenchEvidenceView[] = [
    {
      id: 'talents', label: '天赋', value: initialLoading ? '读取中' : `${talentNodeCount} 个节点`,
      detail: talentWarnings.length ? `${talentWarnings.length} 项描述或规则缺口` : 'SimC 编码状态已读取',
      state: talentState, stateLabel: stateLabel(talentState),
      sourceCountLabel: sourceCountLabel(talentSourceCount, payload?.sources.talents.fromFallback ?? true),
      blockerCountLabel: blockerCountLabel(talentWarnings.length),
      revisionLabel: compactRevisionLabel(payload?.talents.talentSchemaRevision ?? talentReadiness?.schemaRevision, '天赋'),
      actionLabel: '进入',
    },
    {
      id: 'gear', label: '装备', value: initialLoading ? '读取中' : gearCatalogAvailable ? '草稿待校验' : '不可用',
      detail: gearBlockers.length ? `${gearBlockers.length} 项缺口或警告` : '必需槽字段已校验',
      state: gearState, stateLabel: stateLabel(gearState),
      sourceCountLabel: sourceCountLabel(gearSourceCount, payload?.sources.gear.fromFallback ?? true),
      blockerCountLabel: blockerCountLabel(gearBlockers.length),
      revisionLabel: compactRevisionLabel(payload?.gear.gearSchemaRevision ?? payload?.gear.gearCatalogRevision, '装备'),
      actionLabel: '进入',
    },
    {
      id: 'simc', label: 'SimC', value: simcReady ? '可提交前检查' : '输入未就绪',
      detail: simcReady ? '天赋与装备输入可进入最终校验' : '不会在输入不完整时生成模拟结论',
      state: simcState, stateLabel: stateLabel(simcState),
      sourceCountLabel: sourceCountLabel(simcSourceCount, simcSourceCount === 0),
      blockerCountLabel: blockerCountLabel(hardBlockers.length),
      revisionLabel: simcReady ? '当前输入' : '待输入',
      actionLabel: '进入',
    },
    {
      id: 'assistant', label: '队长', value: selection ? '当前工作台上下文' : '上下文不可用',
      detail: '只使用当前授权证据，不生成无来源数字',
      state: assistantState, stateLabel: stateLabel(assistantState),
      sourceCountLabel: '来源 --',
      blockerCountLabel: blockerCountLabel(hardBlockers.length),
      revisionLabel: selection ? '当前上下文' : '待选择',
      actionLabel: '进入',
    },
  ]
  const overallState: ReadinessState = initialLoading
    ? 'loading'
    : routeDegradedState(routeState)
      ?? (simcReady
        ? 'ready'
        : simcPartial
          ? 'partial'
          : 'blocked')
  const identityState: ReadinessState = initialLoading
    ? 'loading'
    : payload?.sources.home.fromFallback
      ? 'stale'
      : selection
        ? 'source_reference'
        : routeDegradedState(routeState) ?? 'blocked'
  const identitySourceLabel = selection
    ? selection.spec.sourceName || '来源参考'
    : identityState === 'loading'
      ? '读取来源'
      : '来源不可用'
  const sourceErrors = unique([
    payload?.sources.home.error,
    payload?.sources.talents.error,
    payload?.sources.gear.error,
  ])
  const readinessReasons = initialLoading
    ? ['正在读取天赋编码状态', '正在读取装备槽位与模板']
    : overallState === 'ready'
      ? ['天赋编码已通过当前后端检查', '装备必需槽位已通过当前后端检查']
      : overallState === 'error' || overallState === 'stale'
        ? unique([...sourceErrors, ...hardBlockers]).slice(0, 2)
        : hardBlockers.slice(0, 2)
  const retryRequired = !selection && !initialLoading
  const primaryModule = simcReady
    ? modules[2]
    : !talentSimcReady
      ? modules[0]
      : modules[1]

  return {
    initialLoading,
    selection,
    identity: selection ? specObject(selection, payload?.sources.home.fromFallback ? 'unknown' : 'source_referenced') : null,
    identityState,
    identitySourceLabel,
    title: selection?.label ?? (initialLoading ? '正在读取当前专精' : '当前专精不可用'),
    contextDetail: `${selectedScenario.title} · ${templateStatusSummary}`,
    scenarioKey: selectedScenario.key,
    scenarioLabel: selectedScenario.title,
    overallState,
    overallLabel: stateLabel(overallState),
    readinessHeadline: readinessHeadline(overallState),
    readinessReasons: readinessReasons.length ? readinessReasons : ['当前输入状态不可用', '请重新读取工作台'],
    overallDetail: simcReady ? '天赋与装备已通过当前后端提交前检查。' : '仍有真实输入未达到 SimC 提交条件。',
    modules,
    evidence,
    blockers: hardBlockers,
    primaryAction: {
      kind: retryRequired ? 'retry' : 'module',
      moduleId: primaryModule?.id ?? 'talents',
      label: retryRequired ? '重新读取工作台' : simcReady ? '进入 SimC 提交确认' : primaryModule?.actionLabel ?? '继续补齐输入',
      disabled: initialLoading,
    },
  }
}
