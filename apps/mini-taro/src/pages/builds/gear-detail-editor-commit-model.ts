import type { GearEnhancementSelection, GearItemReference } from '@wow-mini/domain'

import type { GearCandidateDraft } from './gear-detail-editor-model'

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
      readonly status: IncompleteCommitStatus | 'resolved'
      readonly kind: 'enhancement'
      readonly slot: string
      readonly selection: GearEnhancementSelection
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
  return {
    state: {
      ...state,
      enhancements: { ...state.enhancements, [event.slot]: event.selection },
      enhancementDraft: null,
    },
    committed: true,
    reload: false,
  }
}
