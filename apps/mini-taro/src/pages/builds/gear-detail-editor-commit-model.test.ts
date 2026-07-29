import { describe, expect, it } from 'vitest'

import type {
  GearEnhancementSelection,
  GearItemReference,
  GearResolvedSnapshot,
} from '@wow-mini/domain'

import { createCandidateDraft } from './gear-detail-editor-model'
import * as gearCommitModel from './gear-detail-editor-commit-model'
import {
  resolvedSlotIdentity,
  resolvedSlotIdentityForWorkbench,
  transitionGearEditorCommit,
  type GearEditorCommitState,
  type GearEnhancementDraft,
} from './gear-detail-editor-commit-model'

const oldMainHand: GearItemReference = { itemId: 'old-main-hand', variantKey: 'old-track' }
const oldHead: GearItemReference = { itemId: 'old-head', variantKey: 'head-track' }
const candidate: GearItemReference = { itemId: 'new-main-hand', variantKey: 'new-track' }
const emptySelection: GearEnhancementSelection = {
  gemOptionIds: [],
  enchantOptionId: '',
  embellishmentOptionId: '',
  craftedOptionId: '',
  catalystOptionId: '',
}
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

function resolvedSnapshot(
  mainHand: GearItemReference,
  mainSelection: GearEnhancementSelection,
): GearResolvedSnapshot {
  return {
    contractRevision: 'gear-resolved-snapshot-v1',
    status: 'verified',
    resolvedGearSignature: 'sha256:resolved-editor',
    resolvedSlots: {
      main_hand: {
        itemId: mainHand.itemId,
        variantKey: mainHand.variantKey,
        selectedOptions: mainSelection,
      },
      head: {
        itemId: oldHead.itemId,
        variantKey: oldHead.variantKey,
        selectedOptions: headEnhancement,
      },
    },
  }
}

describe('gear detail editor commit model', () => {
  it('exposes resolved-slot identity as a snapshot-only proof boundary', () => {
    expect(gearCommitModel).toHaveProperty('resolvedSlotIdentity')
  })

  it('keeps unconfirmed enhancements from multiple slots in one workbench draft', () => {
    expect(gearCommitModel).toHaveProperty('updateEnhancementDraftSelection')
    expect(gearCommitModel).toHaveProperty('selectEnhancementDraftSlot')

    const updateSelection = gearCommitModel.updateEnhancementDraftSelection as unknown as (
      draft: GearEnhancementDraft,
      selection: GearEnhancementSelection,
    ) => GearEnhancementDraft
    const selectSlot = gearCommitModel.selectEnhancementDraftSlot as unknown as (
      draft: GearEnhancementDraft,
      slot: string,
      selection: GearEnhancementSelection,
    ) => GearEnhancementDraft
    const initial: GearEnhancementDraft = {
      ...enhancementDraft(mainHandEnhancement),
      selectionBySlot: { main_hand: mainHandEnhancement },
    }

    const afterHead = updateSelection(selectSlot(initial, 'head', headEnhancement), {
      ...headEnhancement,
      embellishmentOptionId: 'head-embellishment',
    })

    expect(afterHead).toMatchObject({
      slot: 'head',
      selection: { embellishmentOptionId: 'head-embellishment' },
      selectionBySlot: {
        main_hand: mainHandEnhancement,
        head: { ...headEnhancement, embellishmentOptionId: 'head-embellishment' },
      },
    })
  })

  it('reads item and variant identity only from a complete verified resolved slot', () => {
    const snapshot = resolvedSnapshot(candidate, emptySelection)

    expect(resolvedSlotIdentity(snapshot, 'main_hand')).toEqual({
      itemId: 'new-main-hand',
      variantKey: 'new-track',
    })
    expect(resolvedSlotIdentity({ ...snapshot, status: 'partial' }, 'main_hand')).toBeNull()
    expect(resolvedSlotIdentity({
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'verified',
      resolvedGearSignature: 'sha256:missing-slots',
    }, 'main_hand')).toBeNull()
    expect(resolvedSlotIdentity({
      ...snapshot,
      resolvedSlots: {
        ...snapshot.resolvedSlots,
        main_hand: { variantKey: 'new-track', selectedOptions: emptySelection },
      },
    }, 'main_hand')).toBeNull()
  })

  it('publishes a verified slot identity when only the remaining profile is incomplete', () => {
    const snapshot: GearResolvedSnapshot = {
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'blocked',
      resolvedGearSignature: 'sha256:main-hand-only',
      aggregateLegality: { status: 'verified', problemCodes: [] },
      profileReadiness: {
        status: 'blocked',
        simcReady: false,
        requiredSlots: ['main_hand', 'head'],
        readySlots: ['main_hand'],
        problems: [{ code: 'GEAR_REQUIRED_SLOTS_INCOMPLETE' }],
      },
      problems: [{ code: 'GEAR_REQUIRED_SLOTS_INCOMPLETE' }],
      resolvedSlots: {
        main_hand: {
          itemId: candidate.itemId,
          variantKey: candidate.variantKey,
          legality: { status: 'verified' },
          selectedOptions: emptySelection,
        },
      },
    }

    expect(resolvedSlotIdentityForWorkbench(snapshot, 'main_hand')).toEqual({
      itemId: candidate.itemId,
      variantKey: candidate.variantKey,
    })
  })

  it('does not commit a candidate from a resolved status without resolved-slot proof', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'candidate',
      slot: 'main_hand',
      item: candidate,
    })

    expect(transition.committed).toBe(false)
    expect(transition.state).toBe(before)
  })

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
      snapshot: resolvedSnapshot(candidate, emptySelection),
    })

    expect(transition.committed).toBe(true)
    expect(transition.reload).toBe(false)
    expect(transition.state.equipped).toEqual({ main_hand: candidate, head: oldHead })
    expect(transition.state.enhancements).toEqual({
      main_hand: emptySelection,
      head: headEnhancement,
    })
    expect(transition.state.candidateDraft).toBeNull()
    expect(transition.state.enhancementDraft).toBe(before.enhancementDraft)
  })

  it('keeps a per-slot verified candidate when only the rest of the profile is incomplete', () => {
    const before = state()
    const partialSnapshot: GearResolvedSnapshot = {
      contractRevision: 'gear-resolved-snapshot-v1',
      status: 'blocked',
      resolvedGearSignature: 'sha256:head-only',
      aggregateLegality: { status: 'verified', problemCodes: [] },
      profileReadiness: {
        status: 'blocked',
        simcReady: false,
        requiredSlots: ['head', 'main_hand', 'neck'],
        readySlots: ['head', 'main_hand'],
        problems: [{ code: 'GEAR_REQUIRED_SLOTS_INCOMPLETE' }],
      },
      problems: [{ code: 'GEAR_REQUIRED_SLOTS_INCOMPLETE' }],
      resolvedSlots: {
        main_hand: {
          itemId: candidate.itemId,
          variantKey: candidate.variantKey,
          legality: { status: 'verified' },
          selectedOptions: emptySelection,
        },
        head: {
          itemId: oldHead.itemId,
          variantKey: oldHead.variantKey,
          legality: { status: 'verified' },
          selectedOptions: headEnhancement,
        },
      },
    }

    const transition = transitionGearEditorCommit(before, {
      status: 'slot_resolved',
      kind: 'candidate',
      slot: 'main_hand',
      item: candidate,
      snapshot: partialSnapshot,
    })

    expect(transition.committed).toBe(true)
    expect(transition.state.equipped).toEqual({ main_hand: candidate, head: oldHead })
    expect(transition.state.enhancements).toEqual({ head: headEnhancement })
    expect(transition.state.candidateDraft).toBeNull()
  })

  it.each([
    {
      name: 'mismatched resolved variant',
      snapshot: {
        ...resolvedSnapshot(candidate, emptySelection),
        resolvedSlots: {
          ...resolvedSnapshot(candidate, emptySelection).resolvedSlots,
          main_hand: {
            itemId: candidate.itemId,
            variantKey: 'different-track',
            selectedOptions: emptySelection,
          },
        },
      },
    },
    {
      name: 'partial resolved options',
      snapshot: {
        ...resolvedSnapshot(candidate, emptySelection),
        resolvedSlots: {
          ...resolvedSnapshot(candidate, emptySelection).resolvedSlots,
          main_hand: {
            itemId: candidate.itemId,
            variantKey: candidate.variantKey,
            selectedOptions: { gemOptionIds: [] },
          },
        },
      },
    },
  ])('keeps the candidate draft for $name', ({ snapshot }) => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'candidate',
      slot: 'main_hand',
      item: candidate,
      snapshot,
    })

    expect(transition.committed).toBe(false)
    expect(transition.state).toBe(before)
  })

  it('commits the verified resolved enhancement rather than the unverified draft', () => {
    const before = state()
    const verifiedSelection = {
      ...nextMainHandEnhancement,
      gemOptionIds: ['verified-gem'],
      enchantOptionId: 'verified-enchant',
    }
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'enhancement',
      slot: 'main_hand',
      snapshot: resolvedSnapshot(oldMainHand, verifiedSelection),
    })

    expect(transition.committed).toBe(true)
    expect(transition.reload).toBe(false)
    expect(transition.state.equipped).toBe(before.equipped)
    expect(transition.state.enhancements).toEqual({
      main_hand: {
        ...verifiedSelection,
      },
      head: headEnhancement,
    })
    expect(transition.state.candidateDraft).toBe(before.candidateDraft)
    expect(transition.state.enhancementDraft).toBeNull()
  })

  it('does not commit an enhancement without resolved-slot proof', () => {
    const before = state()
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'enhancement',
      slot: 'main_hand',
    })

    expect(transition.committed).toBe(false)
    expect(transition.state).toBe(before)
  })

  it('fails closed and preserves the draft when the verified snapshot lacks the target slot', () => {
    const before = state()
    const snapshot = resolvedSnapshot(oldMainHand, nextMainHandEnhancement)
    const transition = transitionGearEditorCommit(before, {
      status: 'resolved',
      kind: 'enhancement',
      slot: 'main_hand',
      snapshot: {
        ...snapshot,
        resolvedSlots: { head: snapshot.resolvedSlots?.['head'] ?? {} },
      },
    })

    expect(transition.committed).toBe(false)
    expect(transition.state).toBe(before)
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
