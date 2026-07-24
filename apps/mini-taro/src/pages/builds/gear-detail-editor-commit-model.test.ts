import { describe, expect, it } from 'vitest'

import type { GearEnhancementSelection, GearItemReference } from '@wow-mini/domain'

import { createCandidateDraft } from './gear-detail-editor-model'
import {
  transitionGearEditorCommit,
  type GearEditorCommitState,
  type GearEnhancementDraft,
} from './gear-detail-editor-commit-model'

const oldMainHand: GearItemReference = { itemId: 'old-main-hand', variantKey: 'old-track' }
const oldHead: GearItemReference = { itemId: 'old-head', variantKey: 'head-track' }
const candidate: GearItemReference = { itemId: 'new-main-hand', variantKey: 'new-track' }
const mainHandEnhancement: GearEnhancementSelection = {
  gemOptionIds: ['main-gem'],
  enchantOptionId: 'main-enchant',
  embellishmentOptionId: '',
  craftedOptionId: '',
  catalystOptionId: '',
}
const headEnhancement: GearEnhancementSelection = {
  gemOptionIds: ['head-gem'],
  enchantOptionId: 'head-enchant',
  embellishmentOptionId: '',
  craftedOptionId: '',
  catalystOptionId: '',
}
const nextMainHandEnhancement: GearEnhancementSelection = {
  ...mainHandEnhancement,
  gemOptionIds: ['next-main-gem'],
}

function enhancementDraft(selection = nextMainHandEnhancement): GearEnhancementDraft {
  return {
    slot: 'main_hand',
    requestedKind: 'socket',
    selection,
    item: oldMainHand,
    blockers: [],
  }
}

function state(): GearEditorCommitState {
  return {
    equipped: { main_hand: oldMainHand, head: oldHead },
    enhancements: { main_hand: mainHandEnhancement, head: headEnhancement },
    candidateDraft: createCandidateDraft('main_hand', candidate),
    enhancementDraft: enhancementDraft(),
  }
}

describe('gear detail editor commit model', () => {
  it.each(['pending', 'stale'] as const)(
    'keeps candidate and committed state unchanged for a %s completion',
    (status) => {
      const before = state()
      const transition = transitionGearEditorCommit(before, {
        status,
        kind: 'candidate',
        slot: 'main_hand',
        item: candidate,
      })

      expect(transition.committed).toBe(false)
      expect(transition.reload).toBe(false)
      expect(transition.state).toBe(before)
    },
  )

  it('keeps both drafts and committed state unchanged for network or 503 failure', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'failed',
      kind: 'candidate',
      slot: 'main_hand',
      item: candidate,
    })

    expect(transition).toEqual({
      state: before,
      committed: false,
      reload: false,
    })
  })

  it('commits a verified candidate only to its target slot and clears only target enhancements', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'candidate',
      slot: 'main_hand',
      item: candidate,
    })

    expect(transition.committed).toBe(true)
    expect(transition.reload).toBe(false)
    expect(transition.state.equipped).toEqual({ main_hand: candidate, head: oldHead })
    expect(transition.state.enhancements).toEqual({ head: headEnhancement })
    expect(transition.state.candidateDraft).toBeNull()
    expect(transition.state.enhancementDraft).toBe(before.enhancementDraft)
  })

  it('commits a verified enhancement only to its target slot and preserves other slots', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'enhancement',
      slot: 'main_hand',
      selection: nextMainHandEnhancement,
    })

    expect(transition.committed).toBe(true)
    expect(transition.reload).toBe(false)
    expect(transition.state.equipped).toBe(before.equipped)
    expect(transition.state.enhancements).toEqual({
      main_hand: nextMainHandEnhancement,
      head: headEnhancement,
    })
    expect(transition.state.candidateDraft).toBe(before.candidateDraft)
    expect(transition.state.enhancementDraft).toBeNull()
  })

  it('clears both drafts and requests reload on a 409 without changing committed state', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, { status: 'conflict' })

    expect(transition.committed).toBe(false)
    expect(transition.reload).toBe(true)
    expect(transition.state.equipped).toBe(before.equipped)
    expect(transition.state.enhancements).toBe(before.enhancements)
    expect(transition.state.candidateDraft).toBeNull()
    expect(transition.state.enhancementDraft).toBeNull()
  })
})
