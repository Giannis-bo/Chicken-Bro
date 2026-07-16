import type {
  CommunityTemplateReference,
  GearEnhancementOption,
  GearItemReference,
  GearStatsPayload,
  ReadinessState,
  WebsimGearPayload,
} from '@wow-mini/domain'

export type GearViewState = 'ready' | 'partial' | 'blocked' | 'empty' | 'loading' | 'stale' | 'error'

export interface GearCandidateView {
  id: string
  label: string
  levelLabel: string
  sourceLabel: string
  statSummary: string
  iconUrl?: string
  state: 'ready' | 'partial' | 'blocked'
}

export interface GearSlotView {
  slot: string
  label: string
  selected: boolean
  candidateCount: number
  itemId: string
  itemLabel: string
  levelLabel: string
  iconUrl?: string
  state: 'ready' | 'partial' | 'empty'
}

export interface GearMetricView {
  id: string
  label: string
  value: string
  verified: boolean
}

export interface GearReadinessView {
  selectedCount: number
  readyCount: number
  requiredCount: number
  percent: number
  itemLevel: string
  itemLevelDetail: string
  state: GearViewState
  metrics: readonly GearMetricView[]
}

export interface GearEnhancementGroupView {
  id: 'socket' | 'enchant' | 'embellishment'
  label: string
  optionCount: number
  value: string
  state: 'ready' | 'empty' | 'blocked'
}

export interface GearEnhancementOptionView {
  id: string
  kind: GearEnhancementGroupView['id']
  label: string
  iconUrl?: string
  selected: boolean
}

export interface GearStatusView {
  id: 'catalog' | 'selection' | 'validation' | 'evidence'
  label: string
  detail: string
  actionLabel?: string
  state: GearViewState
}

const requiredSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand',
] as const

const canonicalSlotDefinitions = [
  { slot: 'head', label: '头部' },
  { slot: 'neck', label: '颈部' },
  { slot: 'shoulder', label: '肩部' },
  { slot: 'back', label: '背部' },
  { slot: 'chest', label: '胸部' },
  { slot: 'wrist', label: '腕部' },
  { slot: 'hands', label: '手部' },
  { slot: 'waist', label: '腰部' },
  { slot: 'legs', label: '腿部' },
  { slot: 'feet', label: '脚部' },
  { slot: 'finger1', label: '戒指 1' },
  { slot: 'finger2', label: '戒指 2' },
  { slot: 'trinket1', label: '饰品 1' },
  { slot: 'trinket2', label: '饰品 2' },
  { slot: 'main_hand', label: '主手' },
  { slot: 'off_hand', label: '副手' },
] as const

const metricFallbacks = [
  { id: 'primary', label: '主属性' },
  { id: 'stamina', label: '耐力' },
  { id: 'critical_strike', label: '暴击' },
  { id: 'haste', label: '急速' },
  { id: 'mastery', label: '精通' },
  { id: 'versatility', label: '全能' },
] as const

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function finiteNumber(value: unknown): number | null {
  const number = typeof value === 'number' ? value : Number.parseFloat(text(value))
  return Number.isFinite(number) && number > 0 ? number : null
}

function compatibilityStatus(item: GearItemReference): string {
  if (typeof item.compatibility === 'string') return item.compatibility
  return text(item.compatibility?.['status'])
}

export function gearItemId(item: GearItemReference | undefined): string {
  if (!item) return ''
  return String(item.itemId ?? item.id ?? '').trim()
}

export function gearItemName(item: GearItemReference | undefined): string {
  if (!item) return ''
  return text(item.displayName) || text(item.name) || text(item.itemName) || '未命名候选'
}

export function gearItemLevel(item: GearItemReference | undefined): number | null {
  if (!item) return null
  return finiteNumber(item.ilevel ?? item.itemLevel)
}

export function gearItemIconUrl(item: GearItemReference | undefined): string | undefined {
  const value = text(item?.iconUrl)
  return value || undefined
}

function gearItemState(item: GearItemReference | undefined): 'ready' | 'partial' | 'blocked' {
  if (!item) return 'blocked'
  if (compatibilityStatus(item) === 'incompatible') return 'blocked'
  if (item.simcReady === true && item.metadataStatus !== 'blocked') return 'ready'
  return 'partial'
}

export function gearCandidates(items: readonly GearItemReference[]): readonly GearCandidateView[] {
  return items.map((item, index) => {
    const level = gearItemLevel(item)
    const iconUrl = gearItemIconUrl(item)
    return {
      id: text(item.variantKey) || `${gearItemId(item) || 'candidate'}-${index}`,
      label: gearItemName(item),
      levelLabel: level ? `装等 ${Math.round(level)}` : '装等待核验',
      sourceLabel: text(item.source) || '来源待补充',
      statSummary: text(item.statSummary) || '属性待核验',
      ...(iconUrl ? { iconUrl } : {}),
      state: gearItemState(item),
    }
  })
}

export function gearSlots(
  payload: WebsimGearPayload | undefined,
  equipped: Readonly<Record<string, GearItemReference>>,
  selectedSlot: string,
): readonly GearSlotView[] {
  const payloadSlots = new Map((payload?.slots ?? []).map((slot) => [slot.slot, slot]))
  return canonicalSlotDefinitions.map((fallback) => {
    const slot = payloadSlots.get(fallback.slot) ?? fallback
    const item = equipped[slot.slot]
    const candidateGroup = payload?.replacementCandidates.find((group) => group.slot === slot.slot)
    const level = gearItemLevel(item)
    const iconUrl = gearItemIconUrl(item)
    return {
      slot: slot.slot,
      label: slot.label,
      selected: selectedSlot === slot.slot,
      candidateCount: candidateGroup?.items.length ?? 0,
      itemId: gearItemId(item),
      itemLabel: item ? gearItemName(item) : '槽位',
      levelLabel: level ? `${Math.round(level)}` : '',
      ...(iconUrl ? { iconUrl } : {}),
      state: item ? (gearItemState(item) === 'ready' ? 'ready' : 'partial') : 'empty',
    }
  })
}

function verifiedMetrics(stats: GearStatsPayload | undefined): readonly GearMetricView[] {
  if (!stats || stats.statStatus === 'blocked') {
    return metricFallbacks.map((item) => ({ ...item, value: '待校验', verified: false }))
  }
  const values = [stats.primary, stats.stamina, ...stats.secondary].filter((item): item is NonNullable<typeof item> => Boolean(item))
  return metricFallbacks.map((fallback) => {
    const match = values.find((item) => item.key === fallback.id || item.label === fallback.label)
    return {
      ...fallback,
      value: match ? String(match.value) : '未提供',
      verified: Boolean(match),
    }
  })
}

export function gearReadiness(
  equipped: Readonly<Record<string, GearItemReference>>,
  stats: GearStatsPayload | undefined,
  routeState: ReadinessState,
): GearReadinessView {
  const selectedItems = Object.entries(equipped).filter(([, item]) => Boolean(gearItemId(item)))
  const readyCount = requiredSlots.filter((slot) => gearItemState(equipped[slot]) === 'ready').length
  const levels = selectedItems.map(([, item]) => gearItemLevel(item)).filter((value): value is number => value !== null)
  const averageLevel = levels.length ? Math.round(levels.reduce((sum, value) => sum + value, 0) / levels.length) : null
  const selectedCount = selectedItems.length
  const requiredCount = requiredSlots.length
  const state: GearViewState = routeState === 'loading'
    ? 'loading'
    : routeState === 'error' || routeState === 'blocked' || routeState === 'stale'
      ? routeState
      : selectedCount === 0
        ? 'empty'
        : readyCount === requiredCount && stats?.statStatus !== 'blocked'
          ? 'ready'
          : 'partial'
  return {
    selectedCount,
    readyCount,
    requiredCount,
    percent: Math.round((readyCount / requiredCount) * 100),
    itemLevel: averageLevel === null ? '--' : String(averageLevel),
    itemLevelDetail: averageLevel === null ? '待配置' : `${levels.length} 件有装等证据`,
    state,
    metrics: verifiedMetrics(stats),
  }
}

const enhancementDefinitions = [
  { id: 'socket', label: '宝石', key: 'socketOptions' },
  { id: 'enchant', label: '附魔', key: 'enchantOptions' },
  { id: 'embellishment', label: '装饰', key: 'embellishmentOptions' },
] as const

function optionIdentity(option: GearEnhancementOption, index: number): string {
  return text(option.id) || text(option.optionKey) || `option-${index}`
}

function optionLabel(option: GearEnhancementOption): string {
  return text(option.displayLabel) || text(option.label) || text(option.displayName) || text(option.name) || '未命名增强项'
}

export function gearEnhancementOptions(
  item: GearItemReference | undefined,
  enhancements: Readonly<Record<string, string>>,
  slot: string,
): readonly GearEnhancementOptionView[] {
  return enhancementDefinitions.flatMap((definition) => {
    const options = item?.[definition.key] ?? []
    return options.map((option, index) => {
      const id = optionIdentity(option, index)
      const iconUrl = text(option.iconUrl)
      return {
        id,
        kind: definition.id,
        label: optionLabel(option),
        ...(iconUrl ? { iconUrl } : {}),
        selected: enhancements[`${slot}:${definition.id}`] === id,
      }
    })
  })
}

export function gearEnhancementGroups(
  item: GearItemReference | undefined,
  enhancements: Readonly<Record<string, string>>,
  slot: string,
): readonly GearEnhancementGroupView[] {
  return enhancementDefinitions.map((definition) => {
    const options = item?.[definition.key] ?? []
    const selected = enhancements[`${slot}:${definition.id}`]
    const selectedOption = options.find((option, index) => optionIdentity(option, index) === selected)
    return {
      id: definition.id,
      label: definition.label,
      optionCount: options.length,
      value: selectedOption ? optionLabel(selectedOption) : options.length ? `${options.length} 项可选` : '待配置',
      state: selectedOption ? 'ready' : options.length ? 'empty' : 'blocked',
    }
  })
}

export function templateGearItems(template: CommunityTemplateReference | undefined): Readonly<Record<string, GearItemReference>> | null {
  if (!template?.gearItems?.length) return null
  const equipped: Record<string, GearItemReference> = {}
  for (const item of template.gearItems) {
    const slot = text(item['slot'])
    if (slot && gearItemId(item)) equipped[slot] = item
  }
  return Object.keys(equipped).length ? equipped : null
}

function localizedGearReason(reason: string | undefined, fallback: string): string {
  const value = text(reason)
  if (!value) return fallback
  if (/backend unavailable|service unavailable|fetch failed|network/iu.test(value)) return '后端校验暂不可用'
  if (/incomplete|missing|required|empty/iu.test(value)) return '装备或天赋输入尚未完整'
  if (/talent|encoding|simc/iu.test(value)) return '天赋编码或 SimC 输入待验证'
  return fallback
}

function checkedAtLabel(checkedAt: string | undefined): string {
  const value = text(checkedAt)
  if (!value) return '尚无后端检查时间'
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/u.exec(value)
  if (!match) return '后端检查时间已记录'
  const [, , month, day, hour, minute] = match
  return `后端检查 ${Number(month)}月${Number(day)}日 ${hour}:${minute}`
}

export function gearStatusDeck(
  payload: WebsimGearPayload | undefined,
  readiness: GearReadinessView,
  stats: GearStatsPayload | undefined,
  routeState: ReadinessState,
  routeReason: string,
): readonly GearStatusView[] {
  const catalogState: GearViewState = routeState === 'loading'
    ? 'loading'
    : routeState === 'error'
      ? 'error'
      : payload?.catalogStatus === 'verified'
        ? 'ready'
        : payload?.catalogStatus === 'blocked'
          ? 'blocked'
          : 'partial'
  const catalogCandidateCount = payload?.replacementCandidates.reduce((sum, group) => sum + group.items.length, 0) ?? 0
  const catalogSlotCount = payload?.slots.length ?? 0
  const catalogDetail = routeReason
    ? localizedGearReason(routeReason, '装备目录暂不可用')
    : payload?.catalogBlockers[0]
      ? localizedGearReason(payload.catalogBlockers[0], '装备目录暂不可用')
      : catalogState === 'ready'
        ? `${catalogCandidateCount} 个候选 · ${catalogSlotCount} 个槽位`
        : '等待装备目录'
  return [
    {
      id: 'catalog',
      label: catalogState === 'loading' ? '目录加载中' : catalogState === 'ready' ? '装备目录可用' : '装备目录受限',
      detail: catalogDetail,
      ...(catalogState === 'error' ? { actionLabel: '重试' } : {}),
      state: catalogState,
    },
    {
      id: 'selection',
      label: readiness.selectedCount ? `已选 ${readiness.selectedCount} 件` : '暂无装备数据',
      detail: readiness.selectedCount ? `${readiness.readyCount}/${readiness.requiredCount} 槽可写入 SimC` : '选择槽位后配置真实候选',
      actionLabel: readiness.selectedCount ? '继续配置' : '前往配置',
      state: readiness.selectedCount ? readiness.state : 'empty',
    },
    {
      id: 'validation',
      label: stats && stats.statStatus !== 'blocked' ? '属性已校验' : '属性校验受限',
      detail: localizedGearReason(stats?.blockers[0], '需要完整装备与已验证天赋编码'),
      actionLabel: '重新校验',
      state: stats && stats.statStatus !== 'blocked' ? 'ready' : 'blocked',
    },
    {
      id: 'evidence',
      label: payload?.dataStatus === 'verified' ? '来源证据可用' : '信息待补充',
      detail: checkedAtLabel(payload?.checkedAt),
      state: payload?.dataStatus === 'verified' ? 'ready' : 'partial',
    },
  ]
}
