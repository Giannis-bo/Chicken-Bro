import { describe, expect, it } from 'vitest'

import type { GearItemReference, WebsimGearPayload } from '@wow-mini/domain'

import {
  gearCandidates,
  gearEnhancementGroups,
  gearReadiness,
  gearSlots,
  gearStatusDeck,
  templateGearItems,
} from './gear-detail-model'

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
  it('ignores catalog-wide compact readiness when the editable equipped set is empty', () => {
    const readiness = gearReadiness({}, undefined, 'ready')
    expect(readiness.selectedCount).toBe(0)
    expect(readiness.readyCount).toBe(0)
    expect(readiness.requiredCount).toBe(15)
    expect(readiness.itemLevel).toBe('--')
    expect(readiness.state).toBe('empty')
  })

  it('derives slots and readiness only from the current equipped record', () => {
    const equipped = { head: readyItem, neck: partialItem }
    const slots = gearSlots(payload(), equipped, 'head')
    const readiness = gearReadiness(equipped, undefined, 'ready')
    expect(slots).toHaveLength(16)
    expect(slots[0]).toMatchObject({ selected: true, candidateCount: 2, state: 'ready', itemId: '250060' })
    expect(slots.map((slot) => slot.slot)).toContain('off_hand')
    expect(readiness).toMatchObject({ selectedCount: 2, readyCount: 1, itemLevel: '285', state: 'partial' })
  })

  it('preserves real candidate identity and evidence without inventing readiness', () => {
    expect(gearCandidates([readyItem, partialItem])).toEqual([
      expect.objectContaining({ id: '250060-0', label: '虚空粉碎者的面纱', levelLabel: '装等 289', state: 'ready' }),
      expect.objectContaining({ id: 'candidate-2-1', label: '待补字段候选', levelLabel: '装等 281', state: 'partial' }),
    ])
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
    const readiness = gearReadiness({ head: readyItem }, stats, 'ready')
    expect(readiness.metrics[0]).toMatchObject({ label: '智力', value: '12,345', verified: true })
    expect(readiness.metrics[2]).toMatchObject({ label: '暴击', value: '678', verified: true })
  })

  it('summarizes only returned enhancement options', () => {
    const item: GearItemReference = {
      ...readyItem,
      socketOptions: [{ id: 'gem-1', label: '+15 急速' }],
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

  it('imports only explicit returned template gear items', () => {
    expect(templateGearItems({ title: '无装备体' })).toBeNull()
    expect(templateGearItems({ title: '来源模板', gearItems: [{ ...readyItem, slot: 'head' }] })).toEqual({ head: expect.objectContaining({ itemId: '250060' }) })
  })

  it('keeps four stable status cards', () => {
    const readiness = gearReadiness({}, undefined, 'ready')
    const statuses = gearStatusDeck(payload(), readiness, payload().statSnapshot, 'ready', '')
    expect(statuses.map((item) => item.id)).toEqual(['catalog', 'selection', 'validation', 'evidence'])
    expect(statuses[0]).toMatchObject({ detail: '2 个候选 · 2 个槽位' })
    expect(statuses[1]).toMatchObject({ label: '暂无装备数据', state: 'empty' })
    expect(statuses[2]).toMatchObject({ detail: '装备或天赋输入尚未完整' })
    expect(statuses[3]).toMatchObject({ detail: '后端检查 7月15日 00:00' })
  })
})
