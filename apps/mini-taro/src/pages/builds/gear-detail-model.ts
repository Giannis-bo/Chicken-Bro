import type {
  CommunityTemplateReference,
  GearEnhancementOption,
  GearEnhancementSelection,
  GearItemReference,
  GearItemStaticStatsBySlot,
  GearProfileReadiness,
  GearReadiness,
  GearStatSnapshotPayload,
  GearStatsPayload,
  ReadinessState,
  WebsimGearPayload,
} from '@wow-mini/domain'

import {
  createCandidateDraft,
  gearCandidateEligibilityState,
  materializeCandidateDraft,
  packedEnhancementSelection,
  selectCandidateVariant,
} from './gear-detail-editor-model'

export type GearViewState = 'ready' | 'partial' | 'blocked' | 'empty' | 'loading' | 'stale' | 'error'

export interface GearCandidateView {
  id: string
  itemId: string
  label: string
  levelLabel: string
  sourceLabel: string
  statSummary: string
  badgeLabels: readonly string[]
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
  secondaryStatLabels: readonly string[]
  secondaryStatState: 'verified' | 'none' | 'unavailable'
  enhancementStates: readonly GearSlotEnhancementState[]
  levelLabel: string
  iconUrl?: string
  state: 'ready' | 'partial' | 'empty'
}

export interface GearSlotEnhancementState {
  id: 'socket' | 'enchant' | 'embellishment'
  label: string
  selected: boolean
  count: number
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
  selectedCount: number
  value: string
  state: 'ready' | 'empty' | 'blocked'
  availabilityLabel: '可用' | '不可用' | '待核验'
  disabled: boolean
}

export interface GearEnhancementOptionView {
  id: string
  kind: GearEnhancementGroupView['id']
  label: string
  iconUrl?: string
  selected: boolean
}

export type GearReplacementCandidateGroup =
  WebsimGearPayload['replacementCandidates'][number]

type GearEnhancementOptionKey = 'socketOptions' | 'enchantOptions' | 'embellishmentOptions'

const gearConfigEnchantExcludedCategories = new Set([
  'class_only_precombat',
  'class_only_weapon_enchant',
  'combat_preparation',
  'runeforge',
  'temporary_enchant',
])

const offhandWeaponEnchantTypes = new Set([
  'dagger',
  'fist_weapon',
  'one_handed_axe',
  'one_handed_mace',
  'one_handed_sword',
  'warglaive',
])

const gearEmbellishmentArmorSlots = new Set([
  'head',
  'shoulder',
  'back',
  'chest',
  'wrist',
  'hands',
  'waist',
  'legs',
  'feet',
])

const gearEmbellishmentJewelrySlots = new Set(['neck', 'finger1', 'finger2'])

const gearBuiltInEmbellishmentSources = new Set(['built_in', 'builtin', 'intrinsic', 'item'])

function optionPayload(option: GearEnhancementOption): Readonly<Record<string, unknown>> {
  const payload = option['payload']
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Readonly<Record<string, unknown>>
    : {}
}

function normalizedConfigKey(value: unknown): string {
  return text(value).toLowerCase().replace(/[^a-z0-9_]+/gu, '_').replace(/^_+|_+$/gu, '')
}

function optionValue(
  option: GearEnhancementOption,
  aliases: readonly string[],
): unknown {
  const payload = optionPayload(option)
  for (const alias of aliases) {
    const value = option[alias]
    if (value !== undefined && value !== null && value !== '') return value
  }
  for (const alias of aliases) {
    const value = payload[alias]
    if (value !== undefined && value !== null && value !== '') return value
  }
  return undefined
}

function optionIdentity(option: GearEnhancementOption): string {
  return text(option.optionKey) || text(option['option_key']) || text(option.id)
}

function verifiedEnhancementOption(option: GearEnhancementOption): boolean {
  return text(option.status) === 'verified' && Boolean(optionIdentity(option))
}

function enchantOptionExcludedFromGearConfig(option: GearEnhancementOption): boolean {
  const category = normalizedConfigKey(optionValue(option, [
    'configCategory',
    'config_category',
    'enchantCategory',
    'enchant_category',
    'category',
  ]))
  return gearConfigEnchantExcludedCategories.has(category)
    || optionValue(option, ['excludeFromGearConfig', 'exclude_from_gear_config', 'blocked']) === true
}

function enchantOptionAppliesToItem(
  option: GearEnhancementOption,
  item: GearItemReference,
  slot: string,
): boolean {
  if (enchantOptionExcludedFromGearConfig(option)) return false
  if (slot !== 'off_hand') return true
  const armorType = normalizedConfigKey(item['armorType'])
  const weaponType = normalizedConfigKey(item['weaponType'])
  const isShield = weaponType === 'shield' || armorType === 'shield'
  const isHeldOffhand = weaponType === 'held_in_off_hand' || weaponType === 'held_off_hand'
  const rule = normalizedConfigKey(optionValue(option, ['itemTypeRule', 'item_type_rule']))
  if (['any', 'any_equipment', 'equipment', 'gear', 'gear_slot'].includes(rule)) return true
  if (['shield', 'offhand_shield', 'off_hand_shield'].includes(rule)) return isShield
  if (['held_offhand', 'held_off_hand', 'holdable', 'invtype_holdable'].includes(rule)) return isHeldOffhand
  return offhandWeaponEnchantTypes.has(weaponType)
}

function embellishmentOptionAppliesToItem(
  option: GearEnhancementOption,
  item: GearItemReference,
  slot: string,
): boolean {
  const group = text(optionValue(option, ['slotGroup', 'slot_group'])).toLowerCase()
  if (!group) return true
  const armorType = normalizedConfigKey(item['armorType'])
  const weaponType = normalizedConfigKey(item['weaponType'])
  const isShield = slot === 'off_hand' && (weaponType === 'shield' || armorType === 'shield')
  const isHeldOffhand = slot === 'off_hand'
    && (weaponType === 'held_in_off_hand' || weaponType === 'held_off_hand')
  if (group === 'equipment') {
    return gearEmbellishmentArmorSlots.has(slot)
      || gearEmbellishmentJewelrySlots.has(slot)
      || slot === 'main_hand'
      || slot === 'off_hand'
  }
  if (group === 'jewelry') return gearEmbellishmentJewelrySlots.has(slot)
  if (group === 'armor') return gearEmbellishmentArmorSlots.has(slot) || isShield
  if (group === 'weapon' || group === 'weapon_offhand') return slot === 'main_hand' || isHeldOffhand
  if (group === 'weapon_armor') {
    return gearEmbellishmentArmorSlots.has(slot)
      || slot === 'main_hand'
      || isShield
      || isHeldOffhand
  }
  return false
}

function itemHasBuiltInEmbellishment(item: GearItemReference): boolean {
  if (item['hasBuiltInEmbellishment'] === true) return true
  if ([
    item['builtInEmbellishment'],
    item['intrinsicEmbellishment'],
    item['inherentEmbellishment'],
  ].some((value) => Boolean(text(value)))) return true
  return gearBuiltInEmbellishmentSources.has(
    normalizedConfigKey(item['embellishmentSource']),
  )
}

function enhancementOptionAppliesToItem(
  option: GearEnhancementOption,
  item: GearItemReference,
  slot: string,
  key: GearEnhancementOptionKey,
): boolean {
  if (!verifiedEnhancementOption(option)) return false
  if (key === 'enchantOptions') return enchantOptionAppliesToItem(option, item, slot)
  if (key === 'embellishmentOptions') {
    return !itemHasBuiltInEmbellishment(item)
      && embellishmentOptionAppliesToItem(option, item, slot)
  }
  return true
}

function compactGroupOptions(
  group: GearReplacementCandidateGroup,
  key: GearEnhancementOptionKey,
): readonly GearEnhancementOption[] {
  const value = (group as unknown as Readonly<Record<string, unknown>>)[key]
  return Array.isArray(value)
    ? value.filter((option): option is GearEnhancementOption => (
        Boolean(option) && typeof option === 'object' && !Array.isArray(option)
      ))
    : []
}

export function hydrateCompactSlotGroup(
  group: GearReplacementCandidateGroup | undefined,
): readonly GearItemReference[] {
  if (!group || !Array.isArray(group.items)) return []
  const socketOptions = compactGroupOptions(group, 'socketOptions')
  const enchantOptions = compactGroupOptions(group, 'enchantOptions')
  const embellishmentOptions = compactGroupOptions(group, 'embellishmentOptions')
  return group.items.map((item) => ({
    ...item,
    socketOptions: gearEnhancementSocketCount(item) !== null && gearEnhancementSocketCount(item)! > 0
      ? socketOptions.filter((option) => verifiedEnhancementOption(option))
      : [],
    enchantOptions: item.modCapabilities?.['canEnchant'] === true
      ? enchantOptions.filter((option) => enhancementOptionAppliesToItem(option, item, group.slot, 'enchantOptions'))
      : [],
    embellishmentOptions: item.modCapabilities?.['canEmbellish'] === true
      ? embellishmentOptions.filter((option) => enhancementOptionAppliesToItem(option, item, group.slot, 'embellishmentOptions'))
      : [],
  }))
}

export interface HydratedEnhancementDraftInput {
  readonly item: GearItemReference
  readonly selection: GearEnhancementSelection
}

function exactHydratedItem(
  items: readonly GearItemReference[],
  committed: GearItemReference,
): GearItemReference | undefined {
  const committedItemId = gearItemId(committed)
  const committedVariantKey = text(committed.variantKey)
  for (const item of items) {
    if (gearItemId(item) !== committedItemId) continue
    if (!committedVariantKey) return item
    const draft = createCandidateDraft('', item)
    if (!draft.requiresVariantSelection) {
      if (text(item.variantKey) === committedVariantKey) return item
      continue
    }
    const exactVariant = materializeCandidateDraft(
      selectCandidateVariant(draft, committedVariantKey),
    )
    if (exactVariant) return { ...item, ...exactVariant }
  }
  return undefined
}

export function gearEnhancementSocketCount(item: GearItemReference): number | null {
  const capabilities = item.modCapabilities
  if (!capabilities || typeof capabilities !== 'object' || Array.isArray(capabilities)) return null
  if (capabilities['hasSocket'] === false) return 0
  const count = capabilities['socketCount']
  return Number.isInteger(count) && Number(count) > 0 ? Number(count) : null
}

export function prepareHydratedEnhancementDraft(
  items: readonly GearItemReference[],
  committed: GearItemReference,
  confirmed: GearEnhancementSelection,
): HydratedEnhancementDraftInput | null {
  const item = exactHydratedItem(items, committed)
  if (
    !item
    || !Array.isArray(item.socketOptions)
    || !Array.isArray(item.enchantOptions)
    || !Array.isArray(item.embellishmentOptions)
  ) return null
  const socketCount = gearEnhancementSocketCount(item)
  if (socketCount === null) return null
  const selection = packedEnhancementSelection(confirmed)
  const socketOptionIds = new Set(item.socketOptions
    .filter(verifiedEnhancementOption)
    .map(optionIdentity))
  const enchantOptionIds = new Set(item.enchantOptions
    .filter(verifiedEnhancementOption)
    .map(optionIdentity))
  const embellishmentOptionIds = new Set(item.embellishmentOptions
    .filter(verifiedEnhancementOption)
    .map(optionIdentity))
  return {
    item,
    selection: {
      ...selection,
      gemOptionIds: selection.gemOptionIds
        .filter((id) => socketOptionIds.has(id))
        .slice(0, socketCount),
      enchantOptionId: enchantOptionIds.has(selection.enchantOptionId)
        ? selection.enchantOptionId
        : '',
      embellishmentOptionId: embellishmentOptionIds.has(selection.embellishmentOptionId)
        ? selection.embellishmentOptionId
        : '',
    },
  }
}

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
  { id: 'haste', label: '急速' },
  { id: 'critical_strike', label: '暴击' },
  { id: 'mastery', label: '精通' },
  { id: 'versatility', label: '全能' },
  { id: 'leech', label: '吸血' },
  { id: 'avoidance', label: '闪避' },
  { id: 'speed', label: '加速' },
] as const

const weaponTypeLabels: Readonly<Record<string, string>> = {
  dagger: '匕首',
  'fist weapon': '拳套',
  'one-handed axe': '单手斧',
  'one-handed mace': '单手锤',
  'one-handed sword': '单手剑',
  warglaive: '战刃',
  wand: '魔杖',
  'two-handed axe': '双手斧',
  'two-handed mace': '双手锤',
  'two-handed sword': '双手剑',
  polearm: '长柄武器',
  staff: '法杖',
  bow: '弓',
  crossbow: '弩',
  gun: '枪械',
  'held in off-hand': '副手物品',
  shield: '盾牌',
}

const statLabels: Readonly<Record<string, string>> = {
  strength: '力量',
  agility: '敏捷',
  intellect: '智力',
  stamina: '耐力',
  critical_strike: '暴击',
  haste: '急速',
  mastery: '精通',
  versatility: '全能',
  leech: '吸血',
  avoidance: '闪避',
  speed: '加速',
  armor: '护甲',
}

const secondaryStatKeys = new Set([
  'critical_strike',
  'haste',
  'mastery',
  'versatility',
  'leech',
  'avoidance',
  'speed',
])

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function finiteNumber(value: unknown): number | null {
  const number = typeof value === 'number' ? value : Number.parseFloat(text(value))
  return Number.isFinite(number) && number > 0 ? number : null
}

function normalizedKey(value: unknown): string {
  return text(value).toLowerCase().replace(/[\s/_-]+/gu, '')
}

type PrimaryStatKey = 'strength' | 'agility' | 'intellect'

function primaryStatKey(value: unknown): PrimaryStatKey | '' {
  const key = normalizedKey(value)
  if (key.includes('力量') || key.includes('strength') || key === 'str') return 'strength'
  if (key.includes('敏捷') || key.includes('agility') || key === 'agi') return 'agility'
  if (key.includes('智力') || key.includes('intellect') || key === 'int') return 'intellect'
  return ''
}

function canonicalStatKey(value: unknown, primaryKey: PrimaryStatKey | ''): string {
  const key = normalizedKey(value)
  if (!key) return ''
  if (key.includes('护甲') || key.includes('armor')) return 'armor'
  if (key.includes('耐力') || key.includes('stamina') || key === 'sta') return 'stamina'
  if (key.includes('急速') || key.includes('haste')) return 'haste'
  if (key.includes('暴击') || key.includes('爆击') || key.includes('critical') || key.includes('crit')) return 'critical_strike'
  if (key.includes('精通') || key.includes('mastery')) return 'mastery'
  if (key.includes('全能') || key.includes('versatility') || key === 'vers') return 'versatility'
  if (key.includes('吸血') || key.includes('leech') || key.includes('lifesteal')) return 'leech'
  if (key.includes('闪避') || key.includes('avoidance')) return 'avoidance'
  if (key.includes('加速') || key.includes('speed')) return 'speed'
  if (key.includes('主属性') || key.includes('primarystat')) return primaryKey
  if (key.includes('agiint') || key.includes('intagi') || key.includes('stragiint') || key.includes('strintagi')) return primaryKey
  if (key.includes('力量') || key.includes('strength') || key === 'str') return 'strength'
  if (key.includes('敏捷') || key.includes('agility') || key === 'agi') return 'agility'
  if (key.includes('智力') || key.includes('intellect') || key === 'int') return 'intellect'
  return ''
}

function itemPrimaryStatKey(item: GearItemReference): PrimaryStatKey | '' {
  return primaryStatKey(item['primaryStatKey'])
}

function numericValue(value: unknown): number | null {
  const match = text(value).replace(/,/gu, '').match(/[+-]?\d+(?:\.\d+)?/u)
  if (typeof value === 'number' && Number.isFinite(value)) return value
  return match ? Number(match[0]) : null
}

function statEntries(item: GearItemReference, primaryKey: PrimaryStatKey | ''): readonly { key: string; value: number }[] {
  const sources = [item['stats'], item['itemStats'], item['attributes'], item['secondaryStats']]
  const entries = sources.flatMap((source) => {
    if (Array.isArray(source)) {
      return source.flatMap((row) => {
        if (!row || typeof row !== 'object' || Array.isArray(row)) return []
        const record = row as Readonly<Record<string, unknown>>
        const key = canonicalStatKey(record['label'] ?? record['name'] ?? record['stat'] ?? record['key'] ?? record['type'], primaryKey)
        const value = numericValue(record['value'] ?? record['amount'] ?? record['rating'] ?? record['rawValue'])
        return key && value !== null ? [{ key, value }] : []
      })
    }
    if (!source || typeof source !== 'object') return []
    return Object.entries(source as Readonly<Record<string, unknown>>).flatMap(([label, raw]) => {
      const key = canonicalStatKey(label, primaryKey)
      const value = numericValue(raw)
      return key && value !== null ? [{ key, value }] : []
    })
  })
  const summary = text(item.statSummary)
  if (!entries.length && summary) {
    for (const part of summary.split(/[；;,，\n]+/u)) {
      const value = numericValue(part)
      const key = canonicalStatKey(part, primaryKey)
      if (key && value !== null) entries.push({ key, value })
    }
  }
  const seen = new Set<string>()
  return entries.filter((entry) => {
    if (['strength', 'agility', 'intellect'].includes(entry.key) && entry.key !== primaryKey) return false
    const identity = `${entry.key}:${entry.value}`
    if (seen.has(identity)) return false
    seen.add(identity)
    return true
  })
}

function localizedStatSummary(item: GearItemReference): string {
  const primaryKey = itemPrimaryStatKey(item)
  const entries = statEntries(item, primaryKey)
  if (!entries.length) return text(item.statSummary) || '属性待核验'
  return entries.map((entry) => `${statLabels[entry.key] ?? entry.key} ${entry.value}`).join('；')
}

export function gearItemSecondaryStatLabels(item: GearItemReference | undefined): readonly string[] {
  if (!item) return []
  const primaryKey = itemPrimaryStatKey(item)
  const labels = statEntries(item, primaryKey)
    .map((entry) => entry.key)
    .filter((key) => secondaryStatKeys.has(key))
    .map((key) => statLabels[key] ?? key)
  const unique = [...new Set(labels)]
  return unique.length ? unique : ['属性待核验']
}

function staticSecondaryStatLabels(stats: Readonly<Record<string, number>>): readonly string[] {
  return [...new Set(
    Object.keys(stats)
      .map((key) => canonicalStatKey(key, ''))
      .filter((key) => secondaryStatKeys.has(key))
      .map((key) => statLabels[key] ?? key),
  )]
}

function gearSlotSecondaryStatPresentation(
  item: GearItemReference | undefined,
  slot: string,
  itemStaticStats: GearItemStaticStatsBySlot | undefined,
): Pick<GearSlotView, 'secondaryStatLabels' | 'secondaryStatState'> {
  if (!item) return { secondaryStatLabels: [], secondaryStatState: 'unavailable' }
  const stats = itemStaticStats?.[slot]
  if (!stats && text(item.statDisplayStatus) === 'verified_variant') {
    const itemEntries = statEntries(item, itemPrimaryStatKey(item))
    if (itemEntries.length) {
      const labels = [...new Set(
        itemEntries
          .map((entry) => entry.key)
          .filter((key) => secondaryStatKeys.has(key))
          .map((key) => statLabels[key] ?? key),
      )]
      return labels.length
        ? { secondaryStatLabels: labels, secondaryStatState: 'verified' }
        : { secondaryStatLabels: ['无固定副属性'], secondaryStatState: 'none' }
    }
  }
  if (!stats) return { secondaryStatLabels: ['属性待核验'], secondaryStatState: 'unavailable' }
  const labels = staticSecondaryStatLabels(stats)
  return labels.length
    ? { secondaryStatLabels: labels, secondaryStatState: 'verified' }
    : { secondaryStatLabels: ['无固定副属性'], secondaryStatState: 'none' }
}

function gearSlotEnhancementStates(
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  slot: string,
): readonly GearSlotEnhancementState[] {
  const confirmed = enhancements[slot]
  const selection = confirmed ? packedEnhancementSelection(confirmed) : null
  const states: readonly GearSlotEnhancementState[] = [
    { id: 'socket', label: '宝石', selected: Boolean(selection?.gemOptionIds.length), count: selection?.gemOptionIds.length ?? 0 },
    { id: 'enchant', label: '附魔', selected: Boolean(selection?.enchantOptionId), count: selection?.enchantOptionId ? 1 : 0 },
    { id: 'embellishment', label: '美化', selected: Boolean(selection?.embellishmentOptionId), count: selection?.embellishmentOptionId ? 1 : 0 },
  ]
  return states.filter((state) => state.selected)
}

function candidateBadgeLabels(item: GearItemReference): readonly string[] {
  const labels: string[] = []
  const add = (value: unknown) => {
    const label = text(value)
    if (label && label !== '远程' && !labels.includes(label)) labels.push(label)
  }
  const backend = item['equipmentBadges']
  if (Array.isArray(backend)) backend.forEach((badge) => {
    if (typeof badge === 'string') add(badge)
    else if (badge && typeof badge === 'object') {
      const record = badge as Readonly<Record<string, unknown>>
      add(record['label'] ?? record['name'] ?? record['displayLabel'])
    }
  })
  return labels
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
  return item ? gearCandidateEligibilityState(item) : 'blocked'
}

export function gearCandidates(items: readonly GearItemReference[]): readonly GearCandidateView[] {
  return items.map((item, index) => {
    const level = gearItemLevel(item)
    const iconUrl = gearItemIconUrl(item)
    return {
      id: `${gearItemId(item) || 'candidate'}-${index}`,
      itemId: gearItemId(item),
      label: gearItemName(item),
      levelLabel: level ? `装等 ${Math.round(level)}` : '装等待核验',
      sourceLabel: text(item.source) || '来源待补充',
      statSummary: localizedStatSummary(item),
      badgeLabels: candidateBadgeLabels(item),
      ...(iconUrl ? { iconUrl } : {}),
      state: gearItemState(item),
    }
  })
}

export function gearSlots(
  payload: WebsimGearPayload | undefined,
  equipped: Readonly<Record<string, GearItemReference>>,
  selectedSlot: string,
  enhancements: Readonly<Record<string, GearEnhancementSelection>> = {},
  itemStaticStats: GearItemStaticStatsBySlot | undefined = undefined,
): readonly GearSlotView[] {
  const payloadSlots = new Map((payload?.slots ?? []).map((slot) => [slot.slot, slot]))
  return canonicalSlotDefinitions.map((fallback) => {
    const slot = payloadSlots.get(fallback.slot) ?? fallback
    const item = equipped[slot.slot]
    const candidateGroup = payload?.replacementCandidates.find((group) => group.slot === slot.slot)
    const level = gearItemLevel(item)
    const iconUrl = gearItemIconUrl(item)
    const weaponType = text(item?.['weaponType']).toLowerCase()
    const weaponLabel = weaponTypeLabels[weaponType]
    const secondaryStats = gearSlotSecondaryStatPresentation(item, slot.slot, itemStaticStats)
    return {
      slot: slot.slot,
      label: (slot.slot === 'main_hand' || slot.slot === 'off_hand') && item
        ? weaponLabel || (text(item['sourceType']) === 'weapon_rule' ? '双手武器' : '武器')
        : slot.label,
      selected: selectedSlot === slot.slot,
      candidateCount: candidateGroup?.items.length ?? 0,
      itemId: gearItemId(item),
      itemLabel: item ? gearItemName(item) : '槽位',
      ...secondaryStats,
      enhancementStates: gearSlotEnhancementStates(enhancements, slot.slot),
      levelLabel: level ? `${Math.round(level)}` : '',
      ...(iconUrl ? { iconUrl } : {}),
      state: item ? (gearItemState(item) === 'ready' ? 'ready' : 'partial') : 'empty',
    }
  })
}

type GearDisplayStats = GearStatsPayload | GearStatSnapshotPayload

function verifiedMetrics(stats: GearDisplayStats | undefined): readonly GearMetricView[] {
  const primaryKey = primaryStatKey(stats?.primary?.key || stats?.primary?.label)
  const fallbacks = metricFallbacks.map((item) => item.id === 'primary'
    ? { ...item, label: statLabels[primaryKey] ?? (text(stats?.primary?.label) || item.label) }
    : item)
  if (!stats || stats.statStatus === 'blocked') {
    return fallbacks.map((item) => ({ ...item, value: '待校验', verified: false }))
  }
  const values = [stats.primary, stats.stamina, ...stats.secondary].filter((item): item is NonNullable<typeof item> => Boolean(item))
  return fallbacks.map((fallback) => {
    const expectedKey = fallback.id === 'primary' ? primaryKey : fallback.id
    const match = fallback.id === 'primary'
      ? stats.primary
      : values.find((item) => canonicalStatKey(item.key || item.label, primaryKey) === expectedKey)
    return {
      ...fallback,
      value: match ? String(match.value) : '未提供',
      verified: Boolean(match),
    }
  })
}

export function gearReadiness(
  equipped: Readonly<Record<string, GearItemReference>>,
  stats: GearDisplayStats | undefined,
  routeState: ReadinessState,
  authority: GearProfileReadiness | GearReadiness | undefined,
): GearReadinessView {
  const selectedItems = Object.entries(equipped).filter(([, item]) => Boolean(gearItemId(item)))
  const levels = selectedItems.map(([, item]) => gearItemLevel(item)).filter((value): value is number => value !== null)
  const averageLevel = levels.length ? Math.round(levels.reduce((sum, value) => sum + value, 0) / levels.length) : null
  const selectedCount = selectedItems.length
  const activeAuthority = authority && ('readySlots' in authority || authority.selectedCount === selectedCount)
    ? authority
    : undefined
  const requiredCount = Math.max(0, Math.trunc(activeAuthority
    ? 'requiredSlots' in activeAuthority
      ? activeAuthority.requiredSlots.length
      : activeAuthority.requiredReadyCount
    : 0))
  const readyCount = Math.min(requiredCount, Math.max(0, Math.trunc(activeAuthority
    ? 'readySlots' in activeAuthority
      ? activeAuthority.readySlots.length
      : activeAuthority.simcReadyCount
    : 0)))
  const fullReady = Boolean(activeAuthority && ('simcReady' in activeAuthority ? activeAuthority.simcReady : activeAuthority.fullReady))
  const authorityBlocked = Boolean(activeAuthority && 'status' in activeAuthority && activeAuthority.status === 'blocked')
  const state: GearViewState = routeState === 'loading'
    ? 'loading'
    : routeState === 'error' || routeState === 'blocked' || routeState === 'stale'
      ? routeState
      : selectedCount === 0
        ? 'empty'
        : !activeAuthority
          ? 'blocked'
          : fullReady && stats?.statStatus !== 'blocked'
          ? 'ready'
          : authorityBlocked
            ? 'blocked'
            : 'partial'
  return {
    selectedCount,
    readyCount,
    requiredCount,
    percent: requiredCount ? Math.round((readyCount / requiredCount) * 100) : 0,
    itemLevel: averageLevel === null ? '--' : String(averageLevel),
    itemLevelDetail: averageLevel === null ? '待配置' : `${levels.length} 件有装等证据`,
    state,
    metrics: verifiedMetrics(stats),
  }
}

const enhancementDefinitions = [
  { id: 'socket', label: '宝石', key: 'socketOptions' },
  { id: 'enchant', label: '附魔', key: 'enchantOptions' },
  { id: 'embellishment', label: '美化', key: 'embellishmentOptions' },
] as const

function optionLabel(option: GearEnhancementOption): string {
  return text(option.displayLabel) || text(option.label) || text(option.displayName) || text(option.name) || '未命名增强项'
}

export function gearEnhancementOptions(
  item: GearItemReference | undefined,
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  slot: string,
): readonly GearEnhancementOptionView[] {
  return enhancementDefinitions.flatMap((definition) => {
    const options = item?.[definition.key] ?? []
    return options.flatMap((option) => {
      if (!item || !enhancementOptionAppliesToItem(option, item, slot, definition.key)) return []
      const id = optionIdentity(option)
      const iconUrl = text(option.iconUrl)
      return [{
        id,
        kind: definition.id,
        label: optionLabel(option),
        ...(iconUrl ? { iconUrl } : {}),
        selected: definition.id === 'socket'
          ? selectedGearEnhancementIds(enhancements, slot, definition.id).includes(id)
          : selectedGearEnhancementId(enhancements, slot, definition.id) === id,
      }]
    })
  })
}

export function gearEnhancementGroups(
  item: GearItemReference | undefined,
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  slot: string,
): readonly GearEnhancementGroupView[] {
  return enhancementDefinitions.map((definition) => {
    const options = item
      ? (item[definition.key] ?? []).filter((option) => (
          enhancementOptionAppliesToItem(option, item, slot, definition.key)
        ))
      : []
    const selectedIds = selectedGearEnhancementIds(enhancements, slot, definition.id)
    const selectedOptions = options.filter((option) => selectedIds.includes(optionIdentity(option)))
    return {
      id: definition.id,
      label: definition.label,
      optionCount: options.length,
      selectedCount: selectedOptions.length,
      value: selectedOptions.length ? selectedOptions.map(optionLabel).join('；') : options.length ? `${options.length} 项可选` : '待配置',
      state: selectedOptions.length ? 'ready' : options.length ? 'empty' : 'blocked',
      availabilityLabel: options.length ? '可用' : '待核验',
      disabled: false,
    }
  })
}

type GearEnhancementAvailability = GearEnhancementGroupView['availabilityLabel']

function itemEnhancementAvailability(
  item: GearItemReference,
  kind: GearEnhancementGroupView['id'],
  slot: string,
): GearEnhancementAvailability {
  const optionKey: GearEnhancementOptionKey = kind === 'socket'
    ? 'socketOptions'
    : kind === 'enchant'
      ? 'enchantOptions'
      : 'embellishmentOptions'
  const options = (item[optionKey] ?? []).filter((option) => (
    enhancementOptionAppliesToItem(option, item, slot, optionKey)
  ))

  const capabilities = item.modCapabilities
  if (!capabilities || typeof capabilities !== 'object' || Array.isArray(capabilities)) {
    return '待核验'
  }
  if (kind === 'socket') {
    if (capabilities['hasSocket'] === false || capabilities['socketCount'] === 0) return '不可用'
    if (Number.isInteger(capabilities['socketCount']) && Number(capabilities['socketCount']) > 0) {
      return '可用'
    }
    return '待核验'
  }
  if (options.length) return '可用'
  const field = kind === 'enchant' ? 'canEnchant' : 'canEmbellish'
  if (capabilities[field] === true) return '可用'
  if (capabilities[field] === false) return '不可用'
  return '待核验'
}

function enhancementSelectionCount(
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  kind: GearEnhancementGroupView['id'],
): number {
  return Object.values(enhancements).filter((selection) => (
    kind === 'socket'
      ? selection.gemOptionIds.some(Boolean)
      : kind === 'enchant'
        ? Boolean(selection.enchantOptionId)
        : Boolean(selection.embellishmentOptionId)
  )).length
}

export function gearEnhancementBarItems(
  equipped: Readonly<Record<string, GearItemReference>>,
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  embellishmentMax: unknown = undefined,
): readonly GearEnhancementGroupView[] {
  const items = Object.entries(equipped)
  const resolverEmbellishmentMax = Number.isInteger(embellishmentMax) && Number(embellishmentMax) >= 0
    ? Number(embellishmentMax)
    : null
  return enhancementDefinitions.map((definition) => {
    const selectedCount = enhancementSelectionCount(enhancements, definition.id)
    const availability = items.map(([slot, item]) => (
      itemEnhancementAvailability(item, definition.id, slot)
    ))
    const availabilityLabel: GearEnhancementAvailability = selectedCount > 0 || availability.includes('可用')
      ? '可用'
      : items.length === 0 || availability.includes('待核验')
        ? '待核验'
        : '不可用'
    const optionCount = availability.filter((state) => state === '可用').length
    const disabled = availabilityLabel === '不可用'
    return {
      id: definition.id,
      label: definition.label,
      optionCount,
      selectedCount,
      value: selectedCount
        ? definition.id === 'embellishment' && resolverEmbellishmentMax !== null
          ? `已配置 ${selectedCount} / ${resolverEmbellishmentMax} 件 · ${availabilityLabel}`
          : `已配置 ${selectedCount} 件 · ${availabilityLabel}`
        : availabilityLabel,
      state: selectedCount ? 'ready' : disabled ? 'blocked' : 'empty',
      availabilityLabel,
      disabled,
    }
  })
}

export function selectedGearEnhancementId(
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  slot: string,
  kind: GearEnhancementGroupView['id'],
): string {
  const selected = enhancements[slot]
  if (!selected) return ''
  if (kind === 'socket') return selected.gemOptionIds[0] ?? ''
  if (kind === 'enchant') return selected.enchantOptionId
  return selected.embellishmentOptionId
}

export function selectedGearEnhancementIds(
  enhancements: Readonly<Record<string, GearEnhancementSelection>>,
  slot: string,
  kind: GearEnhancementGroupView['id'],
): readonly string[] {
  const selected = enhancements[slot]
  if (!selected) return []
  if (kind === 'socket') return selected.gemOptionIds.filter(Boolean)
  const optionId = kind === 'enchant' ? selected.enchantOptionId : selected.embellishmentOptionId
  return optionId ? [optionId] : []
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
