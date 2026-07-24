import { describe, expect, it } from 'vitest'

import type { BuildTemplate, CommunityTemplateReference } from '@wow-mini/domain'

import {
  communityGearTemplateOptions,
  formatGearTemplateUpdatedAt,
  parseGearTemplateDraft,
  savedGearTemplateOptions,
  serializeGearTemplateDraft,
} from './gear-template-import-model'

const savedTemplate = (overrides: Partial<BuildTemplate> = {}): BuildTemplate => ({
  id: 'saved-1',
  clientId: 'saved-1',
  type: 'gear',
  title: '冰霜 · 装备',
  classKey: 'mage',
  className: '法师',
  specKey: 'frost',
  specName: '冰霜',
  heroKey: '',
  heroLabel: '',
  scenarioKey: '',
  scenarioTitle: '',
  rawString: '',
  simcLines: [],
  status: 'complete',
  statusLabel: '完整',
  source: '装备工作台',
  metadata: {},
  createdAt: '2026-07-22T00:00:00Z',
  updatedAt: '2026-07-22T00:00:00Z',
  remote: false,
  schemaVersion: 1,
  trust: { level: 'local_only', sourceLabel: '本地保存' },
  ...overrides,
})

describe('gear template import model', () => {
  it('normalizes PostgreSQL timestamps before formatting them for iOS', () => {
    expect(formatGearTemplateUpdatedAt('2026-07-16 06:42:12+08:00')).toBe('2026-07-16 06:42')
  })

  it('round-trips a versioned saved draft including enhancements', () => {
    const rawString = serializeGearTemplateDraft({
      gearBySlot: { head: { itemId: 123, name: '头盔' } },
      enhancementBySlot: {
        head: {
          gemOptionIds: ['gem-1'],
          enchantOptionId: 'enchant-1',
          embellishmentOptionId: '',
          craftedOptionId: 'crafted-1',
          catalystOptionId: '',
        },
      },
    })

    expect(parseGearTemplateDraft(savedTemplate({ rawString }))).toEqual({
      schemaRevision: 'gear-template-draft-v2',
      gearBySlot: { head: { itemId: 123, name: '头盔' } },
      enhancementBySlot: {
        head: {
          gemOptionIds: ['gem-1'],
          enchantOptionId: 'enchant-1',
          embellishmentOptionId: '',
          craftedOptionId: 'crafted-1',
          catalystOptionId: '',
        },
      },
    })
  })

  it('keeps legacy saved gear usable and recovers its stored enhancements', () => {
    const template = savedTemplate({
      rawString: JSON.stringify({ head: { itemId: 456 } }),
      metadata: {
        enhancementBySlot: {
          head: {
            gemOptionIds: [],
            enchantOptionId: 'enchant-legacy',
            embellishmentOptionId: '',
            craftedOptionId: '',
            catalystOptionId: '',
          },
        },
      },
    })

    expect(parseGearTemplateDraft(template)).toMatchObject({
      gearBySlot: { head: { itemId: 456 } },
      enhancementBySlot: { head: { enchantOptionId: 'enchant-legacy' } },
    })
  })

  it('only exposes saved templates for the current profession and specialization', () => {
    const options = savedGearTemplateOptions([
      savedTemplate({ id: 'matching', rawString: JSON.stringify({ head: { itemId: 1 } }) }),
      savedTemplate({ id: 'other-spec', specKey: 'fire', rawString: JSON.stringify({ head: { itemId: 2 } }) }),
      savedTemplate({ id: 'broken', rawString: '{' }),
    ], 'mage', 'frost')

    expect(options.map((option) => option.template.id)).toEqual(['matching'])
  })

  it('keeps only importable community templates and labels their hero source', () => {
    const templates: CommunityTemplateReference[] = [
      {
        id: 'frostfire-winner', heroLabel: '霜火', playerName: '玩家甲', serverName: '伊森利恩',
        gearItems: [{ slot: 'head', itemId: 1 }],
      },
      { id: 'not-applicable', canApplyGear: false, gearItems: [{ slot: 'head', itemId: 2 }] },
      { id: 'empty', gearItems: [] },
    ]

    expect(communityGearTemplateOptions(templates)).toEqual([
      expect.objectContaining({
        template: templates[0],
        label: '霜火 · 玩家甲（伊森利恩）',
      }),
    ])
  })

  it('keeps both distinct observed Hero players as import options', () => {
    const templates: CommunityTemplateReference[] = [
      {
        id: 'projection-frostfire',
        heroKey: 'frostfire',
        heroLabel: '霜火',
        playerName: '玩家甲',
        sourceIdentity: 'raiderio:cn|realm-a|player-a',
        canApplyGear: true,
        gearItems: [{ slot: 'head', itemId: 1 }],
      },
      {
        id: 'projection-spellslinger',
        heroKey: 'spellslinger',
        heroLabel: '法术投射者',
        playerName: '玩家乙',
        sourceIdentity: 'raiderio:cn|realm-b|player-b',
        canApplyGear: true,
        gearItems: [{ slot: 'head', itemId: 2 }],
      },
    ]

    const options = communityGearTemplateOptions(templates)

    expect(options.map((option) => option.template.id)).toEqual([
      'projection-frostfire',
      'projection-spellslinger',
    ])
    expect(new Set(
      options.map((option) => option.template.sourceIdentity),
    ).size).toBe(2)
  })
})
