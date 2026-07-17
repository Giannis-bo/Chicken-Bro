import type {
  BuildsHomePayload,
  ReadinessState,
  VerifiedWowObjectReference,
} from '@wow-mini/domain'
import type { ProductionAssetId } from '@wow-mini/assets-manifest'

import { findSpecSelection, type SpecSelection } from '../_shared/build-context'
import { cachedDataPresentation } from '../_shared/data-presentation'

export type BuildsHomeEvidenceId = 'talents' | 'gear' | 'simc' | 'tasks'
export type BuildsHomeWorkflowId = 'input' | 'validation' | 'tracking'

export interface BuildsHomeEvidenceView {
  id: BuildsHomeEvidenceId
  title: string
  detail: string
  value: string
  state: ReadinessState
  stateLabel: string
  disabled: boolean
  glyphAssetId: ProductionAssetId
  fallbackGlyphAssetId: ProductionAssetId
}

export interface BuildsHomeWorkflowView {
  id: BuildsHomeWorkflowId
  title: string
  detail: string
  state: ReadinessState
  stateLabel: string
  disabled: boolean
  glyphAssetId: ProductionAssetId
  fallbackGlyphAssetId: ProductionAssetId
}

export interface BuildsHomeViewModel {
  title: string
  headerSourceLabel: string
  initialLoading: boolean
  refreshing: boolean
  retryAvailable: boolean
  healthState: ReadinessState
  selection: SpecSelection | null
  specialization: {
    title: string
    description: string
    sourceLabel: string
    state: ReadinessState
    stateLabel: string
    identity: VerifiedWowObjectReference | null
  }
  evidenceItems: readonly BuildsHomeEvidenceView[]
  workspace: {
    title: string
    statusLabel: string
    summary: string
    detail: string
    state: ReadinessState
    disabled: boolean
    actionLabel: string
    actionMode: 'enter' | 'retry'
  }
  workflow: readonly BuildsHomeWorkflowView[]
}

export interface BuildBuildsHomeModelInput {
  payload?: BuildsHomePayload
  routeState: ReadinessState
  selectedSpecId?: string
}

const evidenceDefinitions = [
  {
    id: 'talents',
    title: '天赋',
    value: '进入后校验',
    glyphAssetId: 'builds-evidence-medallion.talents',
    fallbackGlyphAssetId: 'quick-action-talents-glyph.default',
  },
  {
    id: 'gear',
    title: '装备',
    value: '进入后校验',
    glyphAssetId: 'builds-evidence-medallion.gear',
    fallbackGlyphAssetId: 'quick-action-gear-glyph.default',
  },
  {
    id: 'simc',
    title: 'SimC',
    value: '进入后校验',
    glyphAssetId: 'builds-evidence-medallion.simc',
    fallbackGlyphAssetId: 'quick-action-simc-glyph.default',
  },
  {
    id: 'tasks',
    title: '任务',
    value: '进入后查看',
    glyphAssetId: 'builds-evidence-medallion.tasks',
    fallbackGlyphAssetId: 'utility-glyph-family.records',
  },
] as const

const defaultActionDetail: Readonly<Record<BuildsHomeEvidenceId, string>> = {
  talents: '读取并整理真实天赋输入',
  gear: '读取并补齐真实装备输入',
  simc: '固定输入后进行模拟校验',
  tasks: '查看已提交任务与真实结果',
}

function normalizedPayloadStatus(payload: BuildsHomePayload): string {
  return payload.dataStatus || payload.currentSeason?.dataStatus || ''
}

function healthState(payload: BuildsHomePayload | undefined, routeState: ReadinessState): ReadinessState {
  if (routeState === 'loading') return 'loading'
  if (routeState === 'error' || routeState === 'blocked' || routeState === 'empty' || routeState === 'stale') return routeState
  if (!payload) return 'empty'

  const status = normalizedPayloadStatus(payload)
  if (status === 'blocked') return 'blocked'
  if (status === 'stale') return 'stale'
  if (status === 'partial') return 'partial'
  if (payload.raiderio?.sourceStatus === 'blocked' || payload.raiderio?.sourceStatus === 'stale') return 'partial'
  return status === 'verified' ? 'source_reference' : 'unknown'
}

function headerSourceLabel(selection: SpecSelection | null, state: ReadinessState): string {
  if (selection) return selection.spec.sourceName || '来源参考'
  return state === 'loading' ? '来源读取中' : '来源不可用'
}

function dataStateLabel(state: ReadinessState): string {
  if (state === 'loading') return '来源同步中'
  if (state === 'partial') return '部分可用'
  if (state === 'stale') return cachedDataPresentation.stateLabel
  if (state === 'blocked' || state === 'error' || state === 'empty') return '来源受限'
  return '来源参考'
}

function sourceLabel(selection: SpecSelection | null): string {
  if (!selection) return '来源信息不可用'
  const source = selection.spec.sourceName || '来源参考'
  const publishedAt = selection.spec.publishedAt
  return publishedAt ? `${source} · ${publishedAt}` : source
}

function selectionIdentity(
  selection: SpecSelection | null,
  state: ReadinessState,
): VerifiedWowObjectReference | null {
  if (!selection) return null
  const iconUrl = selection.spec.specIconUrl || selection.spec.iconUrl
  const sourceUrl = selection.spec.sourceUrl
  const sourceReferenced = Boolean(
    iconUrl
      && sourceUrl
      && state !== 'loading'
      && state !== 'stale'
      && state !== 'blocked'
      && state !== 'error',
  )
  return {
    objectType: 'spec',
    objectId: selection.specId,
    name: selection.label,
    ...(iconUrl ? { iconUrl } : {}),
    ...(sourceUrl ? { sourceUrl } : {}),
    verified: sourceReferenced,
    trust: sourceReferenced
      ? { level: 'source_referenced', sourceLabel: selection.spec.sourceName, sourceUrl }
      : { level: 'unknown', reason: '专精图标当前只保留中性占位' },
  }
}

function degradedActionState(
  routeState: ReadinessState,
  pageHealth: ReadinessState,
  actionAvailable: boolean,
): Pick<BuildsHomeEvidenceView, 'state' | 'stateLabel' | 'value'> {
  if (routeState === 'loading') return { state: 'loading', stateLabel: '读取中', value: '正在校验' }
  if (!actionAvailable) return { state: 'blocked', stateLabel: '入口不可用', value: '不可用' }
  if (pageHealth === 'stale') return { state: 'stale', stateLabel: cachedDataPresentation.stateLabel, value: '进入后重试' }
  if (pageHealth === 'blocked' || pageHealth === 'error' || pageHealth === 'empty') {
    return { state: pageHealth, stateLabel: '数据受限', value: '不可用' }
  }
  return { state: 'unknown', stateLabel: '未校验', value: '进入后校验' }
}

function workflowState(
  id: BuildsHomeWorkflowId,
  pageHealth: ReadinessState,
  available: boolean,
): Pick<BuildsHomeWorkflowView, 'state' | 'stateLabel'> {
  if (pageHealth === 'loading') return { state: 'loading', stateLabel: '读取中' }
  if (!available || pageHealth === 'blocked' || pageHealth === 'error' || pageHealth === 'empty') {
    return { state: 'blocked', stateLabel: '不可用' }
  }
  if (pageHealth === 'stale') return { state: 'stale', stateLabel: '需重试' }
  if (id === 'tracking') return { state: 'unknown', stateLabel: '进入后查看' }
  return { state: 'unknown', stateLabel: id === 'input' ? '待校验' : '待开始' }
}

export function buildBuildsHomeModel({
  payload,
  routeState,
  selectedSpecId,
}: BuildBuildsHomeModelInput): BuildsHomeViewModel {
  const pageHealth = healthState(payload, routeState)
  const selection = payload ? findSpecSelection(payload, selectedSpecId) : null
  const actions = new Map((payload?.quickActions ?? []).map((action) => [action.key, action]))
  const initialLoading = routeState === 'loading' && !payload
  const refreshing = routeState === 'loading' && Boolean(payload)

  const evidenceItems: readonly BuildsHomeEvidenceView[] = evidenceDefinitions.map((definition) => {
    const action = actions.get(definition.id)
    const actionState = degradedActionState(routeState, pageHealth, Boolean(action))
    return {
      ...definition,
      detail: action?.desc || (initialLoading ? '正在读取真实入口' : defaultActionDetail[definition.id]),
      ...actionState,
      value: definition.id === 'tasks' && actionState.state === 'unknown' ? '进入后查看' : actionState.value,
      disabled: !selection || !action || actionState.state === 'blocked' || actionState.state === 'error' || actionState.state === 'empty',
    }
  })

  const inputAvailable = Boolean(actions.get('talents') && actions.get('gear') && selection)
  const validationAvailable = Boolean(actions.get('simc') && selection)
  const trackingAvailable = Boolean(actions.get('tasks'))
  const workflowDefinitions = [
    {
      id: 'input',
      title: '输入',
      detail: '整理天赋与装备输入',
      available: inputAvailable,
      glyphAssetId: 'builds-workflow-medallion.input',
      fallbackGlyphAssetId: 'utility-glyph-family.document',
    },
    {
      id: 'validation',
      title: '验证',
      detail: '固定输入后进行 SimC 校验',
      available: validationAvailable,
      glyphAssetId: 'builds-workflow-medallion.validation',
      fallbackGlyphAssetId: 'utility-glyph-family.shield',
    },
    {
      id: 'tracking',
      title: '追踪',
      detail: '进入任务列表追踪真实结果',
      available: trackingAvailable,
      glyphAssetId: 'builds-workflow-medallion.tracking',
      fallbackGlyphAssetId: 'utility-glyph-family.records',
    },
  ] as const
  const workflow: readonly BuildsHomeWorkflowView[] = workflowDefinitions.map(({ available, ...definition }) => ({
    ...definition,
    ...workflowState(definition.id, pageHealth, available),
    disabled: !available || pageHealth === 'blocked' || pageHealth === 'error' || pageHealth === 'empty',
  }))

  const hasSelection = Boolean(selection)
  const workspaceRetryMode = pageHealth === 'blocked' || pageHealth === 'error' || pageHealth === 'empty'
  const workspaceDisabled = workspaceRetryMode ? false : !hasSelection
  const workspaceState = pageHealth === 'source_reference' ? 'source_reference' : pageHealth

  return {
    title: payload?.navTitle || '职业专精',
    headerSourceLabel: headerSourceLabel(selection, pageHealth),
    initialLoading,
    refreshing,
    retryAvailable: pageHealth === 'stale' || pageHealth === 'blocked' || pageHealth === 'error' || pageHealth === 'empty',
    healthState: pageHealth,
    selection,
    specialization: {
      title: selection?.label || (initialLoading ? '正在读取职业 · 专精' : '暂无可用专精'),
      description: selection?.spec.desc || payload?.desc || '选择专精后进入工作台校验天赋、装备与任务状态。',
      sourceLabel: sourceLabel(selection),
      state: selection ? (pageHealth === 'source_reference' ? 'source_reference' : pageHealth) : pageHealth,
      stateLabel: selection ? dataStateLabel(pageHealth) : '未选择专精',
      identity: selectionIdentity(selection, pageHealth),
    },
    evidenceItems,
    workspace: {
      title: '当前专精工作台',
      statusLabel: workspaceRetryMode
        ? '请求未完成'
        : workspaceDisabled
          ? '暂不可进入'
          : pageHealth === 'stale'
            ? '使用缓存进入'
            : '可进入工作台',
      summary: workspaceRetryMode
        ? '当前数据不可用，可在原位置重新请求'
        : selection
          ? '天赋、装备、SimC 与任务尚未在首页校验'
          : '未选择可用专精',
      detail: workspaceRetryMode
        ? '重试不会改变页面结构或伪造可用状态。'
        : '进入后读取真实输入、阻断原因与历史状态。',
      state: workspaceState,
      disabled: workspaceDisabled,
      actionLabel: workspaceRetryMode ? '重试' : '进入工作台',
      actionMode: workspaceRetryMode ? 'retry' : 'enter',
    },
    workflow,
  }
}
