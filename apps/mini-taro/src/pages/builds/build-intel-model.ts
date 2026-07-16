import type { BuildsIntelPayload, ReadinessState, SpecializationSummary } from '@wow-mini/domain'

export type BuildIntelFilterId = 'all' | 'damage' | 'tank' | 'healer' | 'support'
export type BuildIntelSortId = 'source' | 'name'
export type BuildIntelCardAction = 'none' | 'simulator' | 'copy_source' | 'retry' | 'reset_filter'

export interface BuildIntelFilterView {
  id: BuildIntelFilterId
  label: string
  count: number
}

export interface BuildIntelMetadataView {
  id: 'source' | 'window' | 'note'
  label: string
  value: string
  state: ReadinessState
}

export interface BuildIntelCardView {
  id: string
  kind: 'record' | 'state'
  title: string
  description: string
  iconUrl: string
  state: ReadinessState
  stateLabel: string
  metadata: readonly [BuildIntelMetadataView, BuildIntelMetadataView, BuildIntelMetadataView]
  primaryLabel: string
  primaryAction: BuildIntelCardAction
  secondaryLabel: string
  secondaryAction: BuildIntelCardAction
  specId: string
  sourceUrl: string
  loading: boolean
}

export interface BuildIntelViewModel {
  title: string
  description: string
  recordCountLabel: string
  state: ReadinessState
  stateLabel: string
  initialLoading: boolean
  refreshing: boolean
  filters: readonly BuildIntelFilterView[]
  activeFilter: BuildIntelFilterId
  filterLabel: string
  sortId: BuildIntelSortId
  sortLabel: string
  cards: readonly BuildIntelCardView[]
  visibleCardSlotCount: 3
  disclaimer: string
}

export interface BuildBuildIntelModelInput {
  payload?: BuildsIntelPayload
  routeState: ReadinessState
  activeFilter: BuildIntelFilterId
  sortId: BuildIntelSortId
  routeReason?: string
}

const filterDefinitions: readonly Pick<BuildIntelFilterView, 'id' | 'label'>[] = [
  { id: 'all', label: '全部专精' },
  { id: 'damage', label: '输出' },
  { id: 'tank', label: '坦克' },
  { id: 'healer', label: '治疗' },
  { id: 'support', label: '辅助' },
]

const disclaimer = '构筑情报仅聚合来源证据，不代表排名或推荐；请在天赋模拟器中验证。'

function normalized(value: string | undefined): string {
  return value?.trim() ?? ''
}

export function buildIntelRoleFilter(item: SpecializationSummary): Exclude<BuildIntelFilterId, 'all'> {
  const role = normalized(item.role).toLowerCase()
  if (role.includes('坦克') || role.includes('tank')) return 'tank'
  if (role.includes('治疗') || role.includes('healer') || role.includes('healing')) return 'healer'
  if (role.includes('辅助') || role.includes('support')) return 'support'
  return 'damage'
}

function responseState(payload: BuildsIntelPayload | undefined, routeState: ReadinessState): Pick<BuildIntelViewModel, 'state' | 'stateLabel'> {
  if (routeState === 'loading') return { state: 'loading', stateLabel: payload ? '刷新中' : '读取中' }
  if (routeState === 'stale') return { state: 'stale', stateLabel: '本地回退' }
  if (routeState === 'error') return { state: payload ? 'stale' : 'error', stateLabel: payload ? '刷新失败' : '请求失败' }
  if (routeState === 'blocked') return { state: 'blocked', stateLabel: '请求受限' }
  if (routeState === 'empty') return { state: 'empty', stateLabel: '暂无记录' }
  if (payload?.dataStatus === 'verified') return { state: 'ready', stateLabel: '来源已核验' }
  if (payload?.dataStatus === 'stale') return { state: 'stale', stateLabel: '数据过期' }
  if (payload?.dataStatus === 'blocked' || payload?.dataStatus === 'missing_credentials') {
    return { state: 'blocked', stateLabel: '来源受限' }
  }
  return { state: 'partial', stateLabel: '部分可用' }
}

function itemState(item: SpecializationSummary, routeState: ReadinessState): Pick<BuildIntelCardView, 'state' | 'stateLabel'> {
  if (routeState === 'stale' || routeState === 'error') return { state: 'stale', stateLabel: '本地回退' }
  if (item.dataStatus === 'blocked' || item.dataStatus === 'missing_credentials') {
    return { state: 'blocked', stateLabel: '来源受限' }
  }
  if (item.dataStatus === 'verified') return { state: 'ready', stateLabel: '条目已核验' }
  if (normalized(item.sourceUrl)) return { state: 'source_reference', stateLabel: '来源参考' }
  return { state: 'partial', stateLabel: '来源待补充' }
}

function numericEvidenceUsable(item: SpecializationSummary): boolean {
  return item.raiderio?.numericValuesUsable === true
    && item.raiderio.sourceStatus !== 'blocked'
    && (item.sampleCount ?? item.raiderio.sampleCount) > 0
}

function evidenceNote(item: SpecializationSummary): string {
  const explicit = normalized(item.sourceNote)
  if (explicit) return explicit
  if (!numericEvidenceUsable(item)) return item.raiderioSourceStatus === 'blocked' || item.raiderio?.sourceStatus === 'blocked'
    ? '数值来源受限'
    : '仅来源线索'
  return '数值可验证'
}

function cardDescription(item: SpecializationSummary): string {
  const explicit = normalized(item.desc)
  if (explicit) return explicit
  const identity = [normalized(item.className), normalized(item.specName), normalized(item.role)].filter(Boolean).join(' · ')
  return identity ? `${identity}；当前仅展示可追溯的来源记录。` : '当前仅展示可追溯的来源记录。'
}

function recordCard(
  item: SpecializationSummary,
  payload: BuildsIntelPayload,
  routeState: ReadinessState,
): BuildIntelCardView {
  const sourceName = normalized(item.sourceName)
  const sourceUrl = normalized(item.sourceUrl)
  const analysisWindow = normalized(item.analysisWindow) || normalized(payload.analysisWindow)
  const sourceState: ReadinessState = sourceUrl ? 'source_reference' : 'blocked'
  const windowState: ReadinessState = analysisWindow ? 'source_reference' : 'unknown'
  const note = evidenceNote(item)
  const cardStatus = itemState(item, routeState)

  return {
    id: item.id,
    kind: 'record',
    title: normalized(item.title) || normalized(item.specName) || '未命名专精记录',
    description: cardDescription(item),
    iconUrl: normalized(item.iconUrl) || normalized(item.specIconUrl),
    ...cardStatus,
    metadata: [
      { id: 'source', label: '来源参考', value: sourceName || '来源待补充', state: sourceState },
      { id: 'window', label: '分析窗口', value: analysisWindow || '窗口待补充', state: windowState },
      { id: 'note', label: '证据备注', value: note, state: numericEvidenceUsable(item) ? 'ready' : 'partial' },
    ],
    primaryLabel: '进入模拟器',
    primaryAction: item.id ? 'simulator' : 'none',
    secondaryLabel: sourceUrl ? '复制来源' : '来源不可用',
    secondaryAction: sourceUrl ? 'copy_source' : 'none',
    specId: item.id,
    sourceUrl,
    loading: false,
  }
}

function stateCard(
  index: number,
  mode: 'loading' | 'empty' | 'error' | 'blocked' | 'filtered',
  routeReason?: string,
): BuildIntelCardView {
  const content = {
    loading: {
      title: '正在读取构筑情报',
      description: '正在同步真实来源与分析窗口。',
      state: 'loading' as const,
      stateLabel: '读取中',
      primaryLabel: '读取中',
      primaryAction: 'none' as const,
    },
    empty: {
      title: '暂无构筑情报',
      description: '当前接口没有返回可引用的专精记录。',
      state: 'empty' as const,
      stateLabel: '暂无记录',
      primaryLabel: '暂无记录',
      primaryAction: 'none' as const,
    },
    error: {
      title: index === 0 ? '构筑情报读取失败' : '等待构筑情报',
      description: routeReason || '请重试当前来源请求。',
      state: 'error' as const,
      stateLabel: '请求失败',
      primaryLabel: index === 0 ? '重试' : '等待重试',
      primaryAction: index === 0 ? 'retry' as const : 'none' as const,
    },
    blocked: {
      title: index === 0 ? '构筑情报请求受限' : '来源记录不可用',
      description: routeReason || '当前来源暂时不可用。',
      state: 'blocked' as const,
      stateLabel: '请求受限',
      primaryLabel: index === 0 ? '重试' : '暂不可用',
      primaryAction: index === 0 ? 'retry' as const : 'none' as const,
    },
    filtered: {
      title: index === 0 ? '暂无此职责记录' : '等待匹配记录',
      description: '当前筛选没有返回专精情报，可以切换职责查看。',
      state: 'empty' as const,
      stateLabel: '筛选为空',
      primaryLabel: index === 0 ? '查看全部' : '暂无记录',
      primaryAction: index === 0 ? 'reset_filter' as const : 'none' as const,
    },
  }[mode]

  return {
    id: `${mode}-slot-${index + 1}`,
    kind: 'state',
    title: content.title,
    description: content.description,
    iconUrl: '',
    state: content.state,
    stateLabel: content.stateLabel,
    metadata: [
      { id: 'source', label: '来源参考', value: mode === 'loading' ? '读取中' : '不可用', state: content.state },
      { id: 'window', label: '分析窗口', value: mode === 'loading' ? '读取中' : '不可用', state: content.state },
      { id: 'note', label: '证据备注', value: content.stateLabel, state: content.state },
    ],
    primaryLabel: content.primaryLabel,
    primaryAction: content.primaryAction,
    secondaryLabel: '来源不可用',
    secondaryAction: 'none',
    specId: '',
    sourceUrl: '',
    loading: mode === 'loading',
  }
}

function stateCards(mode: Parameters<typeof stateCard>[1], routeReason?: string): readonly BuildIntelCardView[] {
  return Array.from({ length: 3 }, (_, index) => stateCard(index, mode, routeReason))
}

function padVisibleSlots(cards: readonly BuildIntelCardView[]): readonly BuildIntelCardView[] {
  if (cards.length >= 3) return cards
  return [
    ...cards,
    ...Array.from({ length: 3 - cards.length }, (_, index) => stateCard(cards.length + index, 'filtered')),
  ]
}

export function buildBuildIntelModel({
  payload,
  routeState,
  activeFilter,
  sortId,
  routeReason,
}: BuildBuildIntelModelInput): BuildIntelViewModel {
  const items = payload?.items ?? []
  const initialLoading = routeState === 'loading' && !payload
  const response = responseState(payload, routeState)
  const filters = filterDefinitions.map((definition) => ({
    ...definition,
    count: definition.id === 'all'
      ? items.length
      : items.filter((item) => buildIntelRoleFilter(item) === definition.id).length,
  }))
  const filtered = activeFilter === 'all'
    ? [...items]
    : items.filter((item) => buildIntelRoleFilter(item) === activeFilter)
  const sorted = sortId === 'name'
    ? filtered.map((item, index) => ({ item, index })).sort((left, right) => {
        const difference = (left.item.title || left.item.specName).localeCompare(
          right.item.title || right.item.specName,
          'zh-CN',
        )
        return difference || left.index - right.index
      }).map(({ item }) => item)
    : filtered

  let cards: readonly BuildIntelCardView[]
  if (initialLoading) cards = stateCards('loading')
  else if (!payload && routeState === 'blocked') cards = stateCards('blocked', routeReason)
  else if (!payload && routeState === 'error') cards = stateCards('error', routeReason)
  else if (!payload || items.length === 0) cards = stateCards('empty')
  else if (sorted.length === 0) cards = stateCards('filtered')
  else cards = padVisibleSlots(sorted.map((item) => recordCard(item, payload, routeState)))

  const activeFilterView = filters.find((filter) => filter.id === activeFilter) ?? filters[0]

  return {
    title: normalized(payload?.title) || '构筑情报',
    description: normalized(payload?.desc) || '汇总可追溯的专精构筑来源，进入模拟器后再验证与调整。',
    recordCountLabel: payload ? `${items.length} 条来源记录` : '-- 条来源记录',
    ...response,
    initialLoading,
    refreshing: routeState === 'loading' && Boolean(payload),
    filters,
    activeFilter,
    filterLabel: `${activeFilterView?.label ?? '全部专精'} · ${activeFilterView?.count ?? 0}`,
    sortId,
    sortLabel: sortId === 'source' ? '来源顺序' : '专精名称',
    cards,
    visibleCardSlotCount: 3,
    disclaimer,
  }
}
