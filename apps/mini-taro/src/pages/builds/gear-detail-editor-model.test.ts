import { describe, expect, it } from 'vitest'

import type { GearItemReference } from '@wow-mini/domain'

import {
  candidateDraftEnhancementSelection,
  candidateDraftCanApply,
  createCandidateDraft,
  emptyEnhancementSelection,
  isEnhancementKindConfigured,
  materializeCandidateDraft,
  selectCandidateCraftedStat,
  selectCandidateVariant,
  setGemAtSocket,
  setSingleEnhancement,
} from './gear-detail-editor-model'
import { gearCandidates } from './gear-detail-model'

const weaponWithHeroAndMythTracks: GearItemReference = {
  itemId: 'weapon-1',
  name: '星界短杖',
  ilevel: 272,
  variants: [
    { key: 'hero-285', difficultyLabel: '英雄', itemLevel: 285, status: 'ready' },
    { variantKey: 'myth-289', difficultyLabel: '神话', ilevel: 289, status: 'ready' },
    { key: 'needs-variant', difficultyLabel: '待选择', status: 'blocked' },
  ],
  socketOptions: [{ id: 'gem-a', label: '+15 急速' }, { id: 'gem-b', label: '+15 暴击' }],
}

const craftedWeapon: GearItemReference = {
  itemId: 'crafted-weapon-1',
  name: '制造的星界短杖',
  variants: [{ key: 'crafted-myth-285', difficultyLabel: '神话', ilevel: 285, status: 'ready' }],
  craftedStatOptions: [
    {
      key: 'haste_mastery',
      optionId: 'crafted-stats-haste-mastery',
      label: '急速 / 精通',
      simcOptions: ['haste', 'mastery'],
      status: 'verified',
    },
    {
      key: 'crit_vers',
      optionId: 'crafted-stats-crit-versatility',
      label: '暴击 / 全能',
      simcOptions: ['crit', 'vers'],
      status: 'verified',
    },
  ],
}

describe('gear detail editor model', () => {
  it('keeps a candidate local until an explicit variant-backed apply', () => {
    const draft = createCandidateDraft('main_hand', weaponWithHeroAndMythTracks)
    expect(candidateDraftCanApply(draft)).toBe(false)

    const selected = selectCandidateVariant(draft, 'myth-289')
    expect(candidateDraftCanApply(selected)).toBe(true)
    expect(materializeCandidateDraft(selected)).toMatchObject({
      itemId: 'weapon-1', variantKey: 'myth-289', ilevel: 289, difficultyLabel: '神话',
    })
  })

  it('uses the selected compact variant display facts before canonical resolve', () => {
    const candidate: GearItemReference = {
      itemId: 'manifest-head',
      name: '溃烂之花冠冕',
      armorType: 'Cloth',
      equipmentBadges: [{ key: 'equipment_type', label: '布甲' }],
      statSummary: '力量 135；暴击 60；急速 112',
      primaryStatKey: 'strength',
      variants: [
        {
          key: 'myth-298', difficultyLabel: '神话 6/6', itemLevel: 298, status: 'verified',
          primaryStatKey: 'strength',
          itemStats: [
            { key: 'agiint', label: '敏捷 or 智力', value: 135 },
            { key: 'critical_strike', label: '暴击', value: 60 },
            { key: 'haste', label: '急速', value: 112 },
          ],
          statSummary: '力量 135；暴击 60；急速 112',
        },
        {
          key: 'hero-289', difficultyLabel: '英雄 6/6', itemLevel: 289, status: 'verified',
          primaryStatKey: 'strength',
          itemStats: [
            { key: 'agiint', label: '敏捷 or 智力', value: 124 },
            { key: 'critical_strike', label: '暴击', value: 57 },
            { key: 'haste', label: '急速', value: 108 },
          ],
          statSummary: '力量 124；暴击 57；急速 108',
        },
      ],
    }

    const selected = selectCandidateVariant(createCandidateDraft('head', candidate), 'hero-289')
    const materialized = materializeCandidateDraft(selected)

    expect(materialized).toMatchObject({
      itemId: 'manifest-head',
      variantKey: 'hero-289',
      ilevel: 289,
      primaryStatKey: 'strength',
      statSummary: '力量 124；暴击 57；急速 108',
      armorType: 'Cloth',
      equipmentBadges: [{ key: 'equipment_type', label: '布甲' }],
      itemStats: [
        { key: 'agiint', label: '敏捷 or 智力', value: 124 },
        { key: 'critical_strike', label: '暴击', value: 57 },
        { key: 'haste', label: '急速', value: 108 },
      ],
    })
    expect(gearCandidates(materialized ? [materialized] : [])).toEqual([
      expect.objectContaining({
        statSummary: '力量 124；暴击 57；急速 108',
        badgeLabels: ['布甲'],
      }),
    ])
  })

  it('uses valid fallback aliases and keeps unknown variant status blocked', () => {
    const candidate: GearItemReference = {
      itemId: 'alias-weapon',
      variants: [
        { key: '', variantKey: 'fallback-variant', state: '', status: 'ready', itemLevel: '289oops', ilevel: '288' },
        { key: 'unknown-status', status: 'unrecognized', ilevel: 289 },
      ],
    }
    const draft = createCandidateDraft('main_hand', candidate)

    expect(draft.variants).toEqual([
      expect.objectContaining({ key: 'fallback-variant', state: 'ready', ilevel: 288 }),
      expect.objectContaining({ key: 'unknown-status', state: 'blocked', ilevel: 289 }),
    ])
    expect(candidateDraftCanApply(selectCandidateVariant(draft, 'fallback-variant'))).toBe(true)
    expect(candidateDraftCanApply(selectCandidateVariant(draft, 'unknown-status'))).toBe(false)
  })

  it('keeps an explicit partial variant resolver-eligible', () => {
    const draft = createCandidateDraft('main_hand', {
      itemId: 'partial-weapon',
      variants: [{ key: 'partial-285', status: 'partial', difficultyLabel: '英雄', ilevel: 285 }],
    })
    const selected = selectCandidateVariant(draft, 'partial-285')

    expect(selected.variants).toEqual([expect.objectContaining({ key: 'partial-285', state: 'partial' })])
    expect(candidateDraftCanApply(selected)).toBe(true)
    expect(materializeCandidateDraft(selected)).toMatchObject({
      itemId: 'partial-weapon', variantKey: 'partial-285', ilevel: 285, difficultyLabel: '英雄',
    })
  })

  it('materializes a resolver-eligible backend base candidate when no variants are returned', () => {
    const candidate: GearItemReference = {
      itemId: 'base-weapon',
      name: '后端基础武器',
      variantKey: 'backend-base',
      status: 'partial',
      ilevel: 281,
      compatibility: 'compatible',
      socketOptions: [{ id: 'gem-a', label: '+15 急速' }],
    }
    const draft = createCandidateDraft('main_hand', candidate)

    expect(draft.variants).toEqual([])
    expect(candidateDraftCanApply(draft)).toBe(true)
    expect(materializeCandidateDraft(draft)).toMatchObject({
      itemId: 'base-weapon',
      name: '后端基础武器',
      variantKey: 'backend-base',
      ilevel: 281,
      compatibility: 'compatible',
    })
  })

  it('never fabricates base identity and keeps a blocked base candidate disabled', () => {
    const missingIdentity = createCandidateDraft('main_hand', {
      name: '缺少后端物品 ID',
      compatibility: 'compatible',
    })
    const incompatible = createCandidateDraft('main_hand', {
      itemId: 'blocked-weapon',
      compatibility: 'incompatible',
    })

    expect(candidateDraftCanApply(missingIdentity)).toBe(false)
    expect(materializeCandidateDraft(missingIdentity)).toBeNull()
    expect(candidateDraftCanApply(incompatible)).toBe(false)
    expect(materializeCandidateDraft(incompatible)).toBeNull()
  })

  it('requires a verified crafted stat option and materializes it as a resolver enhancement selection', () => {
    const draft = selectCandidateVariant(createCandidateDraft('main_hand', craftedWeapon), 'crafted-myth-285')

    expect(draft.craftedStatOptions).toHaveLength(2)
    expect(draft.requiresCraftedStatSelection).toBe(true)
    expect(candidateDraftCanApply(draft)).toBe(false)

    const selected = selectCandidateCraftedStat(draft, 'crafted-stats-haste-mastery')

    expect(candidateDraftCanApply(selected)).toBe(true)
    expect(candidateDraftEnhancementSelection(selected)).toEqual({
      ...emptyEnhancementSelection(),
      craftedOptionId: 'crafted-stats-haste-mastery',
    })
    expect(materializeCandidateDraft(selected)).not.toHaveProperty('craftedOptionId')
  })

  it('projects resolver-owned crafted options from the selected compact variant', () => {
    const compactCrafted: GearItemReference = {
      itemId: 'compact-crafted',
      variants: [{
        key: 'crafted-myth-289',
        difficultyLabel: '神话',
        itemLevel: 289,
        status: 'ready',
        craftedStatSelectionRequired: true,
        craftedStatOptions: [{
          key: 'haste_mastery',
          optionId: 'crafted-stats-haste-mastery',
          displayLabel: '急速 / 精通',
          simcOptions: { crafted_stats: '32/49', ilevel: 289 },
          status: 'verified',
        }],
      }],
    }

    const initial = createCandidateDraft('main_hand', compactCrafted)
    const selected = selectCandidateVariant(initial, 'crafted-myth-289')

    expect(initial.craftedStatOptions).toEqual([])
    expect(selected.craftedStatOptions).toEqual([{
      key: 'haste_mastery',
      optionId: 'crafted-stats-haste-mastery',
      label: '急速 / 精通',
      simcOptions: ['crafted_stats=32/49', 'ilevel=289'],
      state: 'ready',
      blockers: [],
    }])
    expect(candidateDraftCanApply(selected)).toBe(false)
    expect(candidateDraftCanApply(
      selectCandidateCraftedStat(selected, 'crafted-stats-haste-mastery'),
    )).toBe(true)
  })

  it('does not leak candidate-level crafted display into another compact variant', () => {
    const candidate: GearItemReference = {
      itemId: 'compact-crafted-multi',
      craftedStatOptions: [{
        key: 'legacy',
        displayLabel: '旧候选展示',
        simcOptions: ['legacy'],
      }],
      variants: [
        {
          key: 'crafted-hero',
          status: 'ready',
          craftedStatSelectionRequired: true,
          craftedStatOptions: [{
            key: 'hero-stats',
            optionId: 'crafted-stats-hero',
            displayLabel: '英雄属性',
            simcOptions: { crafted_stats: '32/49' },
            status: 'verified',
          }],
        },
        { key: 'crafted-myth', status: 'ready' },
      ],
    }

    const selected = selectCandidateVariant(
      createCandidateDraft('main_hand', candidate),
      'crafted-myth',
    )

    expect(selected.craftedStatOptions).toEqual([])
  })

  it('fails closed when a customizable crafted variant has no selectable option identity', () => {
    const selected = selectCandidateVariant(createCandidateDraft('head', {
      itemId: 'crafted-missing-option',
      variants: [{
        key: 'crafted-myth-285',
        status: 'ready',
        craftedStatSelectionRequired: true,
        craftedStatOptions: [{
          key: 'haste',
          displayLabel: '急速',
          simcOptions: { crafted_stats: '36' },
          status: 'blocked',
          blockers: ['制造属性选项身份不可用'],
        }],
      }],
    }), 'crafted-myth-285')

    expect(selected.requiresCraftedStatSelection).toBe(true)
    expect(candidateDraftCanApply(selected)).toBe(false)
    expect(selectCandidateCraftedStat(selected, 'forged-option')).toBe(selected)
  })

  it('keeps fixed-stat crafted variants free of a fabricated stat selector', () => {
    const selected = selectCandidateVariant(createCandidateDraft('wrist', {
      itemId: 'crafted-fixed',
      variants: [{
        key: 'crafted-myth-285',
        status: 'ready',
        craftedStatSelectionRequired: false,
        craftedStatOptions: [],
      }],
    }), 'crafted-myth-285')

    expect(selected.requiresCraftedStatSelection).toBe(false)
    expect(selected.craftedStatOptions).toEqual([])
    expect(candidateDraftCanApply(selected)).toBe(true)
    expect(candidateDraftEnhancementSelection(selected)).toEqual(emptyEnhancementSelection())
  })

  it('replaces a gem in place and keeps removals as a packed ordered sequence', () => {
    const selection = { ...emptyEnhancementSelection(), gemOptionIds: ['gem-a', 'gem-old'] }

    expect(setGemAtSocket(selection, 1, 'gem-b').gemOptionIds).toEqual(['gem-a', 'gem-b'])
    expect(setGemAtSocket(selection, 1, '').gemOptionIds).toEqual(['gem-a'])
  })

  it('shifts later gems forward when an earlier gem is removed', () => {
    const selection = { ...emptyEnhancementSelection(), gemOptionIds: ['gem-a', 'gem-b'] }

    expect(setGemAtSocket(selection, 0, '').gemOptionIds).toEqual(['gem-b'])
  })

  it('packs historical empty gem values before applying an edit', () => {
    const selection = { ...emptyEnhancementSelection(), gemOptionIds: ['', 'gem-b'] }

    expect(setGemAtSocket(selection, 1, 'gem-c').gemOptionIds).toEqual(['gem-b', 'gem-c'])
  })

  it('does not report an all-cleared socket sequence as configured', () => {
    expect(isEnhancementKindConfigured(
      { ...emptyEnhancementSelection(), gemOptionIds: ['', ''] },
      'socket',
    )).toBe(false)
    expect(isEnhancementKindConfigured(
      { ...emptyEnhancementSelection(), gemOptionIds: ['gem-a'] },
      'socket',
    )).toBe(true)
  })

  it('changes enchantment or 美化 without affecting socket gems', () => {
    const selection = { ...emptyEnhancementSelection(), gemOptionIds: ['gem-a', 'gem-b'] }

    expect(setSingleEnhancement(selection, 'enchant', 'enchant-a')).toMatchObject({
      gemOptionIds: ['gem-a', 'gem-b'], enchantOptionId: 'enchant-a', embellishmentOptionId: '',
    })
    expect(setSingleEnhancement(selection, 'embellishment', 'embellishment-a')).toMatchObject({
      gemOptionIds: ['gem-a', 'gem-b'], enchantOptionId: '', embellishmentOptionId: 'embellishment-a',
    })
  })

  it('keeps the gem sequence packed while editing a single-value enhancement', () => {
    const selection = { ...emptyEnhancementSelection(), gemOptionIds: ['', 'gem-b'] }

    expect(setSingleEnhancement(selection, 'enchant', 'enchant-a').gemOptionIds).toEqual(['gem-b'])
  })
})
