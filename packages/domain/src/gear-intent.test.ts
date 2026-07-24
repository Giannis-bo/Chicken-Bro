import { describe, expect, it } from 'vitest'

import * as gearIntentExports from './gear-intent'

import {
  gearEnhancementsFromResolvedSnapshot,
  serializeGearSelectionIntent,
} from './gear-intent'

describe('canonical gear selection intent', () => {
  it('accepts only structurally canonical selection-intent-v1 storage for the current identity', () => {
    const guard = (gearIntentExports as Readonly<Record<string, unknown>>)['canonicalGearSelectionIntent'] as
      | ((value: unknown, classKey: string, specKey: string) => unknown)
      | undefined
    const valid = {
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {
        head: {
          itemId: '250060', variantKey: 'variant-head', gemOptionIds: ['gem-haste'],
          enchantOptionId: '', embellishmentOptionId: '', craftedOptionId: '', catalystOptionId: '',
        },
      },
    }

    expect(guard).toBeTypeOf('function')
    if (!guard) return
    expect(guard(valid, 'mage', 'frost')).toEqual(valid)
    expect([
      { ...valid, schemaRevision: 'selection-intent-v0' },
      { ...valid, authoredAgainst: { manifestRevision: 'manifest-r1' } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, classKey: 'warrior' } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, level: 0 } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, level: 90.5 } },
      { ...valid, slots: { helm: valid.slots.head } },
      { ...valid, slots: { head: { ...valid.slots.head, itemId: '' } } },
      { ...valid, slots: { head: { ...valid.slots.head, gemOptionIds: ['x'.repeat(257)] } } },
      { ...valid, slots: { head: { ...valid.slots.head, legality: 'verified' } } },
    ].every((value) => guard(value, 'mage', 'frost') === null)).toBe(true)
  })

  it('serializes only client-owned identifiers from the server resolver context', () => {
    const intent = serializeGearSelectionIntent({
      resolverContext: {
        contractRevision: 'gear-resolver-context-v1',
        selectionSchemaRevision: 'selection-intent-v1',
        authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      },
      selection: { classKey: 'mage', specKey: 'frost' },
      level: 90,
      gearBySlot: {
        head: {
          itemId: '250060',
          variantKey: 'variant-head',
          displayName: '不可信展示名',
          statSummary: '智力 999999',
          simcReady: true,
        },
      },
      enhancementBySlot: {
        head: {
          gemOptionIds: ['gem-haste', '', 'gem-crit'],
          enchantOptionId: 'enchant-head',
        },
      },
    })

    expect(intent).toEqual({
      schemaRevision: 'selection-intent-v1',
      authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      eligibilityContext: { classKey: 'mage', specKey: 'frost', level: 90 },
      slots: {
        head: {
          itemId: '250060',
          variantKey: 'variant-head',
          gemOptionIds: ['gem-haste', 'gem-crit'],
          enchantOptionId: 'enchant-head',
          embellishmentOptionId: '',
          craftedOptionId: '',
          catalystOptionId: '',
        },
      },
    })
  })

  it('fails closed when the backend resolver context is incomplete', () => {
    expect(serializeGearSelectionIntent({
      resolverContext: { selectionSchemaRevision: 'selection-intent-v1' },
      selection: { classKey: 'mage', specKey: 'frost' },
      gearBySlot: {},
    })).toBeNull()
  })

  it('recovers every enhancement identifier from a bound verified snapshot', () => {
    const gearBySlot = {
      head: { itemId: '250060', variantKey: 'variant-head' },
    }
    const enhancements = gearEnhancementsFromResolvedSnapshot({
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'verified',
      resolvedGearSignature: 'sha256:resolved',
      resolvedSlots: {
        head: {
          itemId: '250060',
          variantKey: 'variant-head',
          selectedOptions: {
            gemOptionIds: ['gem-haste', 'gem-haste'],
            enchantOptionId: 'enchant-head',
            embellishmentOptionId: 'embellishment-head',
            craftedOptionId: 'crafted-head',
            catalystOptionId: 'catalyst-head',
          },
        },
      },
    }, gearBySlot)

    expect(enhancements).toEqual({
      head: {
        gemOptionIds: ['gem-haste', 'gem-haste'],
        enchantOptionId: 'enchant-head',
        embellishmentOptionId: 'embellishment-head',
        craftedOptionId: 'crafted-head',
        catalystOptionId: 'catalyst-head',
      },
    })
    expect(serializeGearSelectionIntent({
      resolverContext: {
        contractRevision: 'gear-resolver-context-v1',
        selectionSchemaRevision: 'selection-intent-v1',
        authoredAgainst: { seasonRevision: 'season-17', gearCatalogRevision: 'gear-r17' },
      },
      selection: { classKey: 'mage', specKey: 'frost' },
      gearBySlot,
      enhancementBySlot: enhancements ?? {},
    })?.slots['head']?.gemOptionIds).toEqual(['gem-haste', 'gem-haste'])
  })

  it('rejects a partial or identity-mismatched verified snapshot', () => {
    const base = {
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'verified',
      resolvedGearSignature: 'sha256:resolved',
      resolvedSlots: {
        head: {
          itemId: 'different-item',
          variantKey: 'variant-head',
          selectedOptions: {
            gemOptionIds: [],
            enchantOptionId: '',
            embellishmentOptionId: '',
            craftedOptionId: '',
            catalystOptionId: '',
          },
        },
      },
    }
    expect(gearEnhancementsFromResolvedSnapshot(base, {
      head: { itemId: '250060', variantKey: 'variant-head' },
    })).toBeNull()
    expect(gearEnhancementsFromResolvedSnapshot({
      ...base,
      resolvedSlots: {
        head: {
          ...base.resolvedSlots.head,
          itemId: '250060',
          selectedOptions: { gemOptionIds: [] },
        },
      },
    }, {
      head: { itemId: '250060', variantKey: 'variant-head' },
    })).toBeNull()
  })
})
