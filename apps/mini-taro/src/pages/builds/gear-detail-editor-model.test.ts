import { describe, expect, it } from 'vitest'

import type { GearItemReference } from '@wow-mini/domain'

import {
  candidateDraftCanApply,
  createCandidateDraft,
  emptyEnhancementSelection,
  isEnhancementKindConfigured,
  materializeCandidateDraft,
  selectCandidateVariant,
  setGemAtSocket,
  setSingleEnhancement,
} from './gear-detail-editor-model'

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
    { key: 'haste_mastery', label: '急速 / 精通', simcOptions: ['haste', 'mastery'] },
    { key: 'crit_vers', label: '暴击 / 全能', simcOptions: ['crit', 'vers'] },
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

  it('does not turn display-only craftedStatOptions into a resolver selection', () => {
    const draft = selectCandidateVariant(createCandidateDraft('main_hand', craftedWeapon), 'crafted-myth-285')

    expect(draft.craftedStatOptions).toHaveLength(2)
    expect(materializeCandidateDraft(draft)).not.toHaveProperty('craftedOptionId')
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
