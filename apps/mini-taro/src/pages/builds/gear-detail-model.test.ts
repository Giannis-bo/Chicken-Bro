import { describe, expect, it } from 'vitest'

import {
  serializeGearSelectionIntent,
  type GearItemReference,
  type WebsimGearPayload,
} from '@wow-mini/domain'
import * as gearDetailModel from './gear-detail-model'

import {
  gearCandidates,
  hydrateCompactSlotGroup,
  prepareHydratedEnhancementDraft,
  gearEnhancementGroups,
  gearEnhancementOptions,
  gearItemSecondaryStatLabels,
  gearReadiness,
  gearSlots,
  templateGearItems,
} from './gear-detail-model'
import { candidateDraftCanApply, createCandidateDraft } from './gear-detail-editor-model'

const readyItem: GearItemReference = {
  itemId: '250060',
  name: '虚空粉碎者的面纱',
  ilevel: '289',
  iconUrl: 'https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg',
  simcReady: true,
  metadataStatus: 'verified',
  source: '后端装备目录',
  statSummary: '智力 124；耐力 1768',
}

const partialItem: GearItemReference = {
  itemId: 'candidate-2',
  name: '待补字段候选',
  ilevel: 281,
  simcReady: false,
}

function payload(): WebsimGearPayload {
  return {
    classKey: 'mage', specKey: 'frost', dataStatus: 'verified', catalogStatus: 'verified',
    slots: [
      { slot: 'head', label: '头部' },
      { slot: 'neck', label: '颈部' },
    ],
    slotGroups: [], equippedSet: {}, slotReadiness: {},
    replacementCandidates: [
      { slot: 'head', label: '头部', items: [readyItem, partialItem] },
      { slot: 'neck', label: '颈部', items: [] },
    ],
    communityTemplates: [],
    readiness: {
      fullReady: false, simcReadyCount: 14, selectedCount: 361, candidateCount: 257,
      missingRequiredSlots: ['finger2'], missingCoreSlots: ['finger2'], requiredReadyCount: 15,
      warnings: ['catalog aggregate'],
    },
    statSnapshot: {
      classKey: 'mage', specKey: 'frost', statStatus: 'blocked', blockers: ['incomplete'],
      primary: null, stamina: null, secondary: [], armor: null, weaponDps: null,
      itemLevel: { key: 'itemLevel', label: '装备等级', value: '205' },
    },
    catalogBlockers: [], checkedAt: '2026-07-15T00:00:00Z',
  }
}

describe('gear detail truth model', () => {
  it('exposes a compact slot-group hydration boundary', () => {
    expect(gearDetailModel).toHaveProperty('hydrateCompactSlotGroup')
    expect(gearDetailModel).toHaveProperty('prepareHydratedEnhancementDraft')
  })

  it('hydrates exact compact items with group-level enhancement option sets', () => {
    const group = {
      slot: 'finger1',
      label: '戒指 1',
      items: [{
        itemId: 'compact-ring',
        variantKey: 'myth-289',
        modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: true },
      }],
      socketOptions: [{ id: 'gem-haste', status: 'verified', label: '+147 急速' }],
      enchantOptions: [{ optionKey: 'ring-enchant', status: 'verified', label: '+90 急速' }],
    } as WebsimGearPayload['replacementCandidates'][number] & {
      socketOptions: NonNullable<GearItemReference['socketOptions']>
      enchantOptions: NonNullable<GearItemReference['enchantOptions']>
    }

    const [item] = hydrateCompactSlotGroup(group)

    expect(item).toMatchObject({
      itemId: 'compact-ring',
      variantKey: 'myth-289',
      modCapabilities: { hasSocket: true, socketCount: 1, canEnchant: true },
      socketOptions: [{ id: 'gem-haste' }],
      enchantOptions: [{ optionKey: 'ring-enchant' }],
      embellishmentOptions: [],
    })
    expect(gearEnhancementOptions(item, {}, 'finger1').map((option) => option.id)).toEqual([
      'gem-haste',
      'ring-enchant',
    ])
    expect(prepareHydratedEnhancementDraft(
      hydrateCompactSlotGroup(group),
      { itemId: 'compact-ring', variantKey: 'myth-289' },
      {
        gemOptionIds: ['gem-haste'],
        enchantOptionId: 'ring-enchant',
        embellishmentOptionId: '',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    )).toEqual({
      item,
      selection: {
        gemOptionIds: ['gem-haste'],
        enchantOptionId: 'ring-enchant',
        embellishmentOptionId: '',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    })
  })

  it('filters enhancement options without a resolver-owned identity', () => {
    const item: GearItemReference = {
      itemId: 'unsafe-ring',
      socketOptions: [
        { status: 'verified', label: '缺少 canonical id' },
        { id: 'gem-safe', status: 'verified', label: '+147 急速' },
      ],
      enchantOptions: [{ optionKey: 'enchant-safe', status: 'verified', label: '+90 急速' }],
      embellishmentOptions: [],
    }

    expect(gearEnhancementOptions(item, {}, 'finger1').map((option) => option.id)).toEqual([
      'gem-safe',
      'enchant-safe',
    ])
    expect(gearEnhancementGroups({
      ...item,
      socketOptions: [{ status: 'verified', label: '仍然缺少 canonical id' }],
      enchantOptions: [],
    }, {}, 'finger1').find((group) => group.id === 'socket')).toMatchObject({
      optionCount: 0,
      state: 'blocked',
    })
  })

  it('serializes the resolver-owned option key selected from a compact PG option', () => {
    const [option] = gearEnhancementOptions({
      itemId: 'compact-ring',
      enchantOptions: [{
        id: '301',
        optionKey: 'quick-ruby',
        status: 'verified',
        label: '迅捷红玉',
      }],
    }, {}, 'finger1')

    expect(option?.id).toBe('quick-ruby')
    expect(serializeGearSelectionIntent({
      resolverContext: {
        contractRevision: 'gear-resolver-context-v1',
        selectionSchemaRevision: 'selection-intent-v1',
        authoredAgainst: {
          seasonRevision: 'season-17',
          gearCatalogRevision: 'gear-r17',
        },
      },
      selection: { classKey: 'mage', specKey: 'frost' },
      gearBySlot: { finger1: { itemId: 'compact-ring' } },
      enhancementBySlot: {
        finger1: {
          gemOptionIds: [],
          enchantOptionId: option?.id ?? '',
        },
      },
    })?.slots['finger1']?.enchantOptionId).toBe('quick-ruby')
  })

  it('accepts the compact PG option_key alias as the resolver-owned identity', () => {
    const [option] = gearEnhancementOptions({
      itemId: 'compact-ring',
      enchantOptions: [{
        id: '301',
        option_key: 'quick-ruby-alias',
        status: 'verified',
        label: '迅捷红玉',
      }],
    }, {}, 'finger1')

    expect(option?.id).toBe('quick-ruby-alias')
  })

  it('exposes only explicitly verified enhancement options', () => {
    const item: GearItemReference = {
      itemId: 'strict-ring',
      enchantOptions: [
        { optionKey: 'verified', status: 'verified', label: '已验证附魔' },
        { optionKey: 'uppercase-is-not-canonical', status: 'VERIFIED', label: '非规范状态附魔' },
        { optionKey: 'partial', status: 'partial', label: '部分证据附魔' },
        { optionKey: 'blocked', status: 'blocked', label: '阻断附魔' },
        {
          optionKey: 'metadata-cannot-bypass-status',
          status: 'partial',
          metadataStatus: 'verified',
          label: '物品元数据不能替代增强项验证',
        },
      ],
    }

    expect(gearEnhancementOptions(item, {}, 'finger1').map((option) => option.id)).toEqual([
      'verified',
    ])
    expect(gearEnhancementGroups(item, {}, 'finger1').find((group) => group.id === 'enchant')).toMatchObject({
      optionCount: 1,
    })

    const [hydrated] = hydrateCompactSlotGroup({
      slot: 'finger1',
      label: '戒指 1',
      items: [{
        itemId: 'strict-ring',
        modCapabilities: { hasSocket: false, canEnchant: true, canEmbellish: false },
      }],
      enchantOptions: item.enchantOptions,
    } as WebsimGearPayload['replacementCandidates'][number] & {
      enchantOptions: NonNullable<GearItemReference['enchantOptions']>
    })
    expect(prepareHydratedEnhancementDraft(
      hydrated ? [hydrated] : [],
      { itemId: 'strict-ring' },
      {
        gemOptionIds: [],
        enchantOptionId: 'partial',
        embellishmentOptionId: '',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    )?.selection.enchantOptionId).toBe('')
  })

  it('hydrates off-hand compact enchants only onto the applicable item type', () => {
    const enchantOptions = [
      { optionKey: 'shield-enchant', status: 'verified', itemTypeRule: 'shield' },
      { optionKey: 'held-enchant', status: 'verified', itemTypeRule: 'held_offhand' },
      { optionKey: 'weapon-enchant', status: 'verified', itemTypeRule: 'weapon' },
      { optionKey: 'blocked-enchant', status: 'verified', configCategory: 'runeforge' },
    ]
    const group = {
      slot: 'off_hand',
      label: '副手',
      items: [
        { itemId: 'shield', weaponType: 'shield', modCapabilities: { canEnchant: true } },
        { itemId: 'held', weaponType: 'held in off-hand', modCapabilities: { canEnchant: true } },
        { itemId: 'weapon', weaponType: 'one-handed sword', modCapabilities: { canEnchant: true } },
        { itemId: 'wand', weaponType: 'wand', modCapabilities: { canEnchant: true } },
      ],
      enchantOptions,
    } as WebsimGearPayload['replacementCandidates'][number] & {
      enchantOptions: NonNullable<GearItemReference['enchantOptions']>
    }

    const [shield, held, weapon, wand] = hydrateCompactSlotGroup(group)

    expect(shield?.enchantOptions?.map((option) => option.optionKey)).toEqual(['shield-enchant'])
    expect(held?.enchantOptions?.map((option) => option.optionKey)).toEqual(['held-enchant'])
    expect(weapon?.enchantOptions?.map((option) => option.optionKey)).toEqual(['weapon-enchant'])
    expect(wand?.enchantOptions).toEqual([])
  })

  it('uses the compact group slot to separate jewelry and armor embellishments', () => {
    const embellishmentOptions = [
      { optionKey: 'jewelry-only', status: 'verified', slotGroup: 'jewelry' },
      { optionKey: 'armor-only', status: 'verified', slotGroup: 'armor' },
    ]
    const group = (slot: string, itemId: string) => ({
      slot,
      label: slot,
      items: [{ itemId, armorType: 'cloth', modCapabilities: { canEmbellish: true } }],
      embellishmentOptions,
    }) as WebsimGearPayload['replacementCandidates'][number] & {
      embellishmentOptions: NonNullable<GearItemReference['embellishmentOptions']>
    }

    const [ring] = hydrateCompactSlotGroup(group('finger1', 'ring'))
    const [wrist] = hydrateCompactSlotGroup(group('wrist', 'wrist'))

    expect(ring).not.toHaveProperty('slot')
    expect(ring?.embellishmentOptions?.map((option) => option.optionKey)).toEqual(['jewelry-only'])
    expect(wrist?.embellishmentOptions?.map((option) => option.optionKey)).toEqual(['armor-only'])
  })

  it('blocks embellishment choices for items with a built-in embellishment', () => {
    const embellishmentOptions = [
      { optionKey: 'armor-only', status: 'verified', slotGroup: 'armor' },
    ]
    const builtInItems: GearItemReference[] = [
      { itemId: 'flag', hasBuiltInEmbellishment: true },
      { itemId: 'built-in-value', builtInEmbellishment: '自带美化' },
      { itemId: 'intrinsic-value', intrinsicEmbellishment: '自带美化' },
      { itemId: 'inherent-value', inherentEmbellishment: '自带美化' },
      { itemId: 'source-built-in', embellishmentSource: 'built_in' },
      { itemId: 'source-builtin', embellishmentSource: 'builtin' },
      { itemId: 'source-intrinsic', embellishmentSource: 'intrinsic' },
      { itemId: 'source-item', embellishmentSource: 'item' },
    ].map((item) => ({
      ...item,
      armorType: 'cloth',
      modCapabilities: { canEmbellish: true },
    }))
    const group = {
      slot: 'wrist',
      label: '腕部',
      items: [
        ...builtInItems,
        {
          itemId: 'ordinary-armor',
          armorType: 'cloth',
          modCapabilities: { canEmbellish: true },
        },
      ],
      embellishmentOptions,
    } as WebsimGearPayload['replacementCandidates'][number] & {
      embellishmentOptions: NonNullable<GearItemReference['embellishmentOptions']>
    }

    const hydrated = hydrateCompactSlotGroup(group)

    expect(hydrated.slice(0, builtInItems.length).every((item) => (
      item.embellishmentOptions?.length === 0
    ))).toBe(true)
    expect(hydrated.at(-1)?.embellishmentOptions?.map((option) => option.optionKey)).toEqual([
      'armor-only',
    ])
  })

  it('ignores catalog-wide compact readiness when the editable equipped set is empty', () => {
    const readiness = gearReadiness({}, undefined, 'ready', payload().readiness)
    expect(readiness.selectedCount).toBe(0)
    expect(readiness.readyCount).toBe(0)
    expect(readiness.requiredCount).toBe(0)
    expect(readiness.itemLevel).toBe('--')
    expect(readiness.state).toBe('empty')
  })

  it('labels an unvalidated editable draft as unknown instead of zero required slots', () => {
    const readiness = gearReadiness({ head: readyItem }, undefined, 'ready', payload().readiness)

    expect(readiness).toMatchObject({ selectedCount: 1, readyCount: 0, requiredCount: 0, state: 'blocked' })
  })

  it('derives slot presentation from the draft while readiness stays backend-owned', () => {
    const equipped = { head: readyItem, neck: partialItem }
    const slots = gearSlots(payload(), equipped, 'head')
    const readiness = gearReadiness(equipped, undefined, 'ready', {
      ...payload().readiness,
      simcReadyCount: 1,
      selectedCount: 2,
    })
    expect(slots).toHaveLength(16)
    expect(slots[0]).toMatchObject({ selected: true, candidateCount: 2, state: 'ready', itemId: '250060' })
    expect(slots.map((slot) => slot.slot)).toContain('off_hand')
    expect(readiness).toMatchObject({ selectedCount: 2, readyCount: 1, itemLevel: '285', state: 'partial' })
  })

  it('projects only backend-derived secondary labels and confirmed enhancement state into a slot row', () => {
    const item: GearItemReference = {
      ...readyItem,
      itemStats: [
        { key: 'intellect', value: 124 },
        { key: 'stamina', value: 1768 },
        { key: 'haste_rating', value: 411 },
        { key: 'mastery_rating', value: 287 },
      ],
    }
    const enhancements = {
      head: {
        gemOptionIds: ['gem-haste'],
        enchantOptionId: '',
        embellishmentOptionId: 'embellishment-thread',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    }

    expect(gearItemSecondaryStatLabels(item)).toEqual(['急速', '精通'])
    expect(gearItemSecondaryStatLabels({ ...readyItem, statSummary: '智力 124；耐力 1768' })).toEqual(['属性待核验'])
    expect(gearSlots(payload(), { head: item }, '', enhancements, {
      head: { haste: 235, mastery: 191 },
    })[0]).toMatchObject({
      secondaryStatLabels: ['急速', '精通'],
      secondaryStatState: 'verified',
      enhancementStates: [
        { id: 'socket', selected: true, count: 1 },
        { id: 'enchant', selected: false, count: 0 },
        { id: 'embellishment', selected: true, count: 1 },
      ],
    })
    expect(gearSlots(payload(), { head: item }, '', enhancements, { head: {} })[0]).toMatchObject({
      secondaryStatLabels: ['无固定副属性'],
      secondaryStatState: 'none',
    })
    expect(gearSlots(payload(), { head: item }, '', enhancements)[0]).toMatchObject({
      secondaryStatLabels: ['属性待核验'],
      secondaryStatState: 'unavailable',
    })
  })

  it('uses backend resolver readiness instead of a fixed local slot rule', () => {
    const readiness = gearReadiness({ head: readyItem }, undefined, 'ready', {
      status: 'blocked',
      simcReady: false,
      readySlots: ['head'],
      requiredSlots: [
        'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
        'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand',
      ],
    })

    expect(readiness).toMatchObject({
      selectedCount: 1,
      readyCount: 1,
      requiredCount: 16,
      percent: 6,
      state: 'blocked',
    })
  })

  it('orders the summary metrics into primary, left secondary and right tertiary slots', () => {
    const stats = {
      ...payload().statSnapshot,
      statStatus: 'verified' as const,
      primary: { key: 'intellect', label: '智力', value: '2345' },
      stamina: { key: 'stamina', label: '耐力', value: '5678' },
      secondary: [
        { key: 'haste', label: '急速', value: '100' },
        { key: 'critical_strike', label: '暴击', value: '200' },
        { key: 'mastery', label: '精通', value: '300' },
        { key: 'versatility', label: '全能', value: '400' },
        { key: 'leech', label: '吸血', value: '50' },
        { key: 'avoidance', label: '闪避', value: '60' },
        { key: 'speed', label: '加速', value: '70' },
      ],
    }
    const readiness = gearReadiness({ head: readyItem }, stats, 'ready', {
      status: 'verified', simcReady: true, readySlots: ['head'], requiredSlots: ['head'],
    })

    expect(readiness.metrics.map((metric) => metric.id)).toEqual([
      'primary', 'stamina', 'haste', 'critical_strike', 'mastery', 'versatility', 'leech', 'avoidance', 'speed',
    ])
    expect(readiness.metrics.map((metric) => metric.value)).toContain('70')
  })

  it('preserves real candidate identity and evidence without inventing readiness', () => {
    expect(gearCandidates([readyItem, partialItem])).toEqual([
      expect.objectContaining({ id: '250060-0', label: '虚空粉碎者的面纱', levelLabel: '装等 289', state: 'ready' }),
      expect.objectContaining({ id: 'candidate-2-1', label: '待补字段候选', levelLabel: '装等 281', state: 'partial' }),
    ])
  })

  it('gives each candidate a distinct selection identity when backend variant keys repeat', () => {
    const views = gearCandidates([
      { itemId: 'head-a', variantKey: 'mythic', name: '头部候选 A' },
      { itemId: 'head-b', variantKey: 'mythic', name: '头部候选 B' },
      { itemId: 'head-c', variantKey: 'mythic', name: '头部候选 C' },
      { itemId: 'head-d', variantKey: 'mythic', name: '头部候选 D' },
    ])

    expect(views.map((candidate) => candidate.id)).toEqual([
      'head-a-0',
      'head-b-1',
      'head-c-2',
      'head-d-3',
    ])
  })

  it('uses the same backend eligibility projection for candidate rows and editor drafts', () => {
    const blockedCandidates: GearItemReference[] = [
      { itemId: 'status-blocked', status: 'blocked', compatibility: 'compatible' },
      { itemId: 'state-blocked', status: 'partial', state: 'blocked', compatibility: 'compatible' },
      { itemId: 'metadata-blocked', metadataStatus: 'blocked', compatibility: 'compatible' },
      { itemId: 'blocker-blocked', blockers: ['规则拒绝'], compatibility: 'compatible' },
      { name: 'missing identity', compatibility: 'compatible' },
    ]

    expect(gearCandidates(blockedCandidates).map((candidate) => candidate.state)).toEqual([
      'blocked',
      'blocked',
      'blocked',
      'blocked',
      'blocked',
    ])
    expect(blockedCandidates.map((candidate) => (
      candidateDraftCanApply(createCandidateDraft('main_hand', candidate))
    ))).toEqual([false, false, false, false, false])
  })

  it('localizes backend-owned primary stats and equipment badges', () => {
    const candidate: GearItemReference = {
      ...readyItem,
      weaponType: 'staff',
      primaryStatKey: 'intellect',
      equipmentBadges: [{ key: 'weapon_handedness', label: '双手' }],
      itemStats: [
        { key: 'agi_int', value: 124 },
        { key: 'haste_rating', value: 77 },
      ],
    }
    expect(gearCandidates([candidate])[0]).toMatchObject({
      statSummary: '智力 124；急速 77',
      badgeLabels: ['双手'],
    })
  })

  it('does not recreate missing equipment badges from raw weapon fields', () => {
    expect(gearCandidates([{ ...readyItem, weaponType: 'staff', uniqueEquipped: true }])[0]?.badgeLabels).toEqual([])
  })

  it('labels weapon slots by the selected item type', () => {
    const slots = gearSlots(payload(), {
      main_hand: { ...readyItem, weaponType: 'staff' },
      off_hand: { ...readyItem, weaponType: 'shield' },
    }, '')
    expect(slots.find((slot) => slot.slot === 'main_hand')?.label).toBe('法杖')
    expect(slots.find((slot) => slot.slot === 'off_hand')?.label).toBe('盾牌')
  })

  it('matches rating aliases in verified stat snapshots', () => {
    const stats = {
      ...payload().statSnapshot,
      statStatus: 'verified',
      primary: { key: 'intellect', label: 'Intellect', value: '12,345' },
      secondary: [{ key: 'critical_strike_rating', label: 'Critical Strike Rating', value: 678 }],
    }
    const readiness = gearReadiness({ head: readyItem }, stats, 'ready', undefined)
    expect(readiness.metrics[0]).toMatchObject({ label: '智力', value: '12,345', verified: true })
    expect(readiness.metrics.find((metric) => metric.id === 'critical_strike')).toMatchObject({
      label: '暴击',
      value: '678',
      verified: true,
    })
  })

  it('summarizes only returned enhancement options', () => {
    const item: GearItemReference = {
      ...readyItem,
      socketOptions: [{ id: 'gem-1', status: 'verified', label: '+15 急速' }],
      enchantOptions: [],
      embellishmentOptions: [],
    }
    expect(gearEnhancementGroups(item, {
      head: {
        gemOptionIds: ['gem-1'],
        enchantOptionId: '',
        embellishmentOptionId: '',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    }, 'head')).toEqual([
      expect.objectContaining({ id: 'socket', optionCount: 1, value: '+15 急速', state: 'ready' }),
      expect.objectContaining({ id: 'enchant', optionCount: 0, value: '待配置', state: 'blocked' }),
      expect.objectContaining({ id: 'embellishment', optionCount: 0, value: '待配置', state: 'blocked' }),
    ])
  })

  it('shows every selected socket gem and uses the player-facing 美化 label', () => {
    const item: GearItemReference = {
      ...readyItem,
      socketOptions: [
        { id: 'gem-1', status: 'verified', label: '+15 急速' },
        { id: 'gem-2', status: 'verified', label: '+15 暴击' },
      ],
      enchantOptions: [],
      embellishmentOptions: [{ id: 'embellishment-1', status: 'verified', label: '加固护腕' }],
    }

    expect(gearEnhancementGroups(item, {
      head: {
        gemOptionIds: ['gem-1', 'gem-2'],
        enchantOptionId: '',
        embellishmentOptionId: 'embellishment-1',
        craftedOptionId: '',
        catalystOptionId: '',
      },
    }, 'head')).toEqual([
      expect.objectContaining({ id: 'socket', selectedCount: 2, value: '+15 急速；+15 暴击', state: 'ready' }),
      expect.objectContaining({ id: 'enchant', value: '待配置', state: 'blocked' }),
      expect.objectContaining({ id: 'embellishment', label: '美化', value: '加固护腕', state: 'ready' }),
    ])
  })

  it('imports only explicit returned template gear items', () => {
    expect(templateGearItems({ title: '无装备体' })).toBeNull()
    expect(templateGearItems({ title: '来源模板', gearItems: [{ ...readyItem, slot: 'head' }] })).toEqual({ head: expect.objectContaining({ itemId: '250060' }) })
  })

})
