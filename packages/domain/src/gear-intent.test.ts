import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import * as gearIntentExports from './gear-intent'

import {
  canonicalExactLoadoutIntent,
  gearEnhancementsFromResolvedSnapshot,
  gearItemStaticStatsFromResolvedSnapshot,
  serializeGearSelectionIntent,
} from './gear-intent'

const mutationPath = fileURLToPath(new URL('../../../tests/fixtures/gear_canonical_mutations.json', import.meta.url))
const mutations = JSON.parse(readFileSync(mutationPath, 'utf8')) as {
  invalidIdentityStrings: string[]
}

const exactCoreSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand',
]

function exactSlot(itemId: string) {
  return {
    itemId, declaredItemLevel: null, bonusIds: [], context: '', gemIds: [],
    gemBonusIds: [], gemItemLevels: [], enchantId: '', craftedStats: [],
    embellishmentIds: [], redirectedBaseStats: [],
  }
}

function validExactIntent() {
  return {
    schemaRevision: 'exact-loadout-intent-v2',
    authoredAgainst: { seasonRevision: 'season-r1', gameBuild: 'build-r1' },
    eligibilityContext: { classKey: 'warrior', specKey: 'fury', level: 80 },
    slots: Object.fromEntries(exactCoreSlots.map((name, index) => [name, exactSlot(String(225574 + index))])),
  }
}

describe('canonical gear selection intent', () => {
  it('accepts exactly the complete catalog-independent exact v2 identity', () => {
    const coreSlots = [
      'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
      'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand',
    ]
    const slot = (itemId: string) => ({
      itemId, declaredItemLevel: null, bonusIds: [], context: '', gemIds: [],
      gemBonusIds: [], gemItemLevels: [], enchantId: '', craftedStats: [],
      embellishmentIds: [], redirectedBaseStats: [],
    })
    const valid = {
      schemaRevision: 'exact-loadout-intent-v2',
      authoredAgainst: { seasonRevision: 'season-r1', gameBuild: 'build-r1' },
      eligibilityContext: { classKey: 'warrior', specKey: 'fury', level: 80 },
      slots: Object.fromEntries(coreSlots.map((name, index) => [name, slot(String(225574 + index))])),
    }

    expect(canonicalExactLoadoutIntent(valid, 'warrior', 'fury')).toEqual(valid)
    expect([
      { ...valid, authoredAgainst: { ...valid.authoredAgainst, gearCatalogRevision: 'catalog-r1' } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, variantKey: 'variant-head' } } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, level: 80.5 } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, classKey: 'mage' } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, itemId: '' } } },
      { ...valid, slots: Object.fromEntries([...coreSlots].reverse().map((name, index) => [name, slot(String(225574 + index))])) },
      { ...valid, slots: Object.fromEntries(coreSlots.slice(1).map((name, index) => [name, slot(String(225574 + index))])) },
    ].every((value) => canonicalExactLoadoutIntent(value, 'warrior', 'fury') === null)).toBe(true)
  })

  it('rejects newline-bearing identifiers in every exact v2 identity field', () => {
    const coreSlots = [
      'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
      'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand',
    ]
    const slot = (itemId: string) => ({
      itemId, declaredItemLevel: null, bonusIds: [], context: '', gemIds: [],
      gemBonusIds: [], gemItemLevels: [], enchantId: '', craftedStats: [],
      embellishmentIds: [], redirectedBaseStats: [],
    })
    const valid = {
      schemaRevision: 'exact-loadout-intent-v2',
      authoredAgainst: { seasonRevision: 'season-r1', gameBuild: 'build-r1' },
      eligibilityContext: { classKey: 'warrior', specKey: 'fury', level: 80 },
      slots: Object.fromEntries(coreSlots.map((name, index) => [name, slot(String(225574 + index))])),
    }
    const newline = 'unsafe\nvalue'
    const cases = [
      { ...valid, authoredAgainst: { ...valid.authoredAgainst, seasonRevision: newline } },
      { ...valid, authoredAgainst: { ...valid.authoredAgainst, gameBuild: newline } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, classKey: newline } },
      { ...valid, eligibilityContext: { ...valid.eligibilityContext, specKey: newline } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, itemId: newline } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, context: newline } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, enchantId: newline } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, bonusIds: [newline] } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, gemIds: [newline] } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, gemBonusIds: [newline] } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, craftedStats: [newline] } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, embellishmentIds: [newline] } } },
      { ...valid, slots: { ...valid.slots, head: { ...valid.slots.head, redirectedBaseStats: [newline] } } },
    ]
    expect(cases.every((value) => canonicalExactLoadoutIntent(value, 'warrior', 'fury') === null)).toBe(true)
  })

  it('rejects the shared raw control mutation corpus in every exact v2 string field', () => {
    const cases = (value: string) => {
      const values: unknown[] = []
      for (const [section, key] of [
        ['authoredAgainst', 'seasonRevision'],
        ['authoredAgainst', 'gameBuild'],
        ['eligibilityContext', 'classKey'],
        ['eligibilityContext', 'specKey'],
      ] as const) {
        const candidate = validExactIntent()
        candidate[section][key] = value
        values.push(candidate)
      }
      for (const key of ['itemId', 'context', 'enchantId'] as const) {
        const candidate = validExactIntent()
        candidate.slots.head[key] = value
        values.push(candidate)
      }
      for (const key of [
        'bonusIds', 'gemIds', 'gemBonusIds', 'craftedStats',
        'embellishmentIds', 'redirectedBaseStats',
      ] as const) {
        const candidate = validExactIntent()
        candidate.slots.head[key] = [value]
        values.push(candidate)
      }
      return values
    }

    for (const mutation of mutations.invalidIdentityStrings) {
      expect(
        cases(mutation).every((value) => canonicalExactLoadoutIntent(value, 'warrior', 'fury') === null),
        JSON.stringify(mutation),
      ).toBe(true)
    }
  })

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

  it('recovers only intrinsic pre-enhancement stats from a bound verified snapshot', () => {
    const snapshot = {
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'verified',
      resolvedGearSignature: 'sha256:resolved',
      resolvedSlots: {
        head: {
          itemId: '250060',
          variantKey: 'variant-head',
          itemStaticStats: { critical_strike: 301, mastery: 227 },
          resolvedStats: { critical_strike: 301, mastery: 227, haste: 147 },
        },
      },
    }
    const gearBySlot = { head: { itemId: '250060', variantKey: 'variant-head' } }

    expect(gearItemStaticStatsFromResolvedSnapshot(snapshot, gearBySlot)).toEqual({
      head: { critical_strike: 301, mastery: 227 },
    })
    expect(gearItemStaticStatsFromResolvedSnapshot({
      ...snapshot,
      resolvedSlots: {
        head: { ...snapshot.resolvedSlots.head, itemStaticStats: { haste: -1 } },
      },
    }, gearBySlot)).toBeNull()
    expect(gearItemStaticStatsFromResolvedSnapshot(snapshot, {
      head: { itemId: 'different-item', variantKey: 'variant-head' },
    })).toBeNull()
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
