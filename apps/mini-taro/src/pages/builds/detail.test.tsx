import { describe, expect, it, vi } from 'vitest'

import {
  gearEnhancementBarItems,
  hydrateCompactSlotGroup,
  prepareHydratedEnhancementDraft,
  selectGearEnhancementBarItem,
} from './gear-detail-model'

describe('gear detail enhancement capability presentation', () => {
  it('presents canonical labels and makes unavailable controls semantically disabled', () => {
    const items = gearEnhancementBarItems({
      wrist: {
        itemId: 'capability-states',
        capabilityFacts: {
          socket: { status: 'unavailable', value: 0, options: [] },
          enchant: { status: 'pending', value: null, options: [] },
          embellishment: { status: 'verified', value: true, options: ['emb-safe'] },
        },
        embellishmentOptions: [{ id: 'emb-safe', status: 'verified', label: '安全美化' }],
      },
    }, {})
    const onSelect = vi.fn()
    const [socket, , embellishment] = items
    if (!socket || !embellishment) throw new Error('expected all enhancement categories')

    expect(items.map((item) => item.value)).toEqual(['不可用', '待核验', '可用'])
    expect(items.map((item) => item.disabled)).toEqual([true, true, false])
    expect(selectGearEnhancementBarItem(socket, onSelect)).toBe(false)
    expect(selectGearEnhancementBarItem(embellishment, onSelect)).toBe(true)
    expect(onSelect).toHaveBeenCalledWith(embellishment)
  })

  it('opens one released gem slot for item 250033 variant void_upgrade-298', () => {
    const group = {
      slot: 'finger1',
      label: '戒指 1',
      items: [{
        itemId: '250033',
        variantKey: 'void_upgrade-298',
        modCapabilities: { hasSocket: false, socketCount: 0 },
        capabilityFacts: {
          socket: { status: 'verified', value: 1, options: ['gem-void'] },
          enchant: { status: 'unavailable', value: false, options: [] },
          embellishment: { status: 'unavailable', value: false, options: [] },
        },
      }],
      socketOptions: [{ id: 'gem-void', status: 'verified', label: '+147 急速' }],
    } as Parameters<typeof hydrateCompactSlotGroup>[0]
    const [item] = hydrateCompactSlotGroup(group)

    expect(item).toBeDefined()
    if (!item) throw new Error('expected released compact item')
    expect(prepareHydratedEnhancementDraft(
      [item],
      { itemId: '250033', variantKey: 'void_upgrade-298' },
      { gemOptionIds: ['gem-void'], enchantOptionId: '', embellishmentOptionId: '', craftedOptionId: '', catalystOptionId: '' },
    )?.selection.gemOptionIds).toEqual(['gem-void'])
  })
})
