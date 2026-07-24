import type {
  GearEnhancementSelection,
  GearItemReference,
  GearSelectionIntent,
} from '@wow-mini/domain'

import {
  packedEnhancementSelection,
  type GearCandidateDraft,
} from './gear-detail-editor-model'

export type GearEnhancementKind = 'socket' | 'enchant' | 'embellishment'

export interface GearEnhancementDraft {
  readonly slot: string
  readonly requestedKind: GearEnhancementKind
  readonly selection: GearEnhancementSelection
  readonly item?: GearItemReference
  readonly blockers: readonly string[]
}

export interface GearEditorCommitState {
  readonly equipped: Readonly<Record<string, GearItemReference>>
  readonly enhancements: Readonly<Record<string, GearEnhancementSelection>>
  readonly candidateDraft: GearCandidateDraft | null
  readonly enhancementDraft: GearEnhancementDraft | null
}

type IncompleteCommitStatus = 'pending' | 'failed' | 'stale'

export type GearEditorCommitEvent =
  | {
      readonly status: IncompleteCommitStatus | 'resolved'
      readonly kind: 'candidate'
      readonly slot: string
      readonly item: GearItemReference
    }
  | {
      readonly status: IncompleteCommitStatus
      readonly kind: 'enhancement'
      readonly slot: string
    }
  | {
      readonly status: 'resolved'
      readonly kind: 'enhancement'
      readonly slot: string
      readonly resolvedIntent: GearSelectionIntent
    }
  | { readonly status: 'conflict' }

export interface GearEditorCommitTransition {
  readonly state: GearEditorCommitState
  readonly committed: boolean
  readonly reload: boolean
}

function withoutSlot<T>(
  values: Readonly<Record<string, T>>,
  slot: string,
): Readonly<Record<string, T>> {
  return Object.fromEntries(Object.entries(values).filter(([key]) => key !== slot))
}

export function resolvedEnhancementSelection(
  intent: GearSelectionIntent,
  slot: string,
): GearEnhancementSelection | null {
  const resolvedSlot = intent.slots[slot]
  if (!resolvedSlot) return null
  return packedEnhancementSelection({
    gemOptionIds: resolvedSlot.gemOptionIds,
    enchantOptionId: resolvedSlot.enchantOptionId,
    embellishmentOptionId: resolvedSlot.embellishmentOptionId,
    craftedOptionId: resolvedSlot.craftedOptionId,
    catalystOptionId: resolvedSlot.catalystOptionId,
  })
}

export function transitionGearEditorCommit(
  state: GearEditorCommitState,
  event: GearEditorCommitEvent,
): GearEditorCommitTransition {
  if (event.status === 'conflict') {
    return {
      state: {
        ...state,
        candidateDraft: null,
        enhancementDraft: null,
      },
      committed: false,
      reload: true,
    }
  }
  if (event.status !== 'resolved') {
    return { state, committed: false, reload: false }
  }
  if (event.kind === 'candidate') {
    return {
      state: {
        ...state,
        equipped: { ...state.equipped, [event.slot]: event.item },
        enhancements: withoutSlot(state.enhancements, event.slot),
        candidateDraft: null,
      },
      committed: true,
      reload: false,
    }
  }
  const selection = resolvedEnhancementSelection(event.resolvedIntent, event.slot)
  if (!selection) return { state, committed: false, reload: false }
  return {
    state: {
      ...state,
      enhancements: { ...state.enhancements, [event.slot]: selection },
      enhancementDraft: null,
    },
    committed: true,
    reload: false,
  }
}
