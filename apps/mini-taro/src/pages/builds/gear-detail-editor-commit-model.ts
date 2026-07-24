import type {
  GearEnhancementSelection,
  GearItemReference,
  GearResolvedSnapshot,
} from '@wow-mini/domain'
import { gearEnhancementsFromResolvedSnapshot } from '@wow-mini/domain'

import {
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
      readonly snapshot?: GearResolvedSnapshot
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
      readonly snapshot?: GearResolvedSnapshot
    }
  | { readonly status: 'conflict' }

export interface GearEditorCommitTransition {
  readonly state: GearEditorCommitState
  readonly committed: boolean
  readonly reload: boolean
}

export interface ResolvedSlotIdentity {
  readonly itemId: string
  readonly variantKey: string
}

function record(value: unknown): value is Readonly<Record<string, unknown>> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function identifier(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value).trim()
    : ''
}

export function resolvedSlotIdentity(
  snapshot: GearResolvedSnapshot | undefined,
  slot: string,
): ResolvedSlotIdentity | null {
  if (
    snapshot?.contractRevision !== 'gear-resolved-snapshot-v1'
    || snapshot.status !== 'verified'
    || !identifier(snapshot.resolvedGearSignature)
    || !record(snapshot.resolvedSlots)
  ) return null
  const resolved = snapshot.resolvedSlots[slot]
  if (!record(resolved)) return null
  const itemId = identifier(resolved['itemId'])
  if (!itemId) return null
  const selectedOptions = resolved['selectedOptions']
  const fields = [
    'gemOptionIds',
    'enchantOptionId',
    'embellishmentOptionId',
    'craftedOptionId',
    'catalystOptionId',
  ] as const
  if (
    !record(selectedOptions)
    || fields.some((field) => !Object.prototype.hasOwnProperty.call(selectedOptions, field))
    || !Array.isArray(selectedOptions['gemOptionIds'])
  ) return null
  if (
    selectedOptions['gemOptionIds'].some((value) => !identifier(value))
    || fields.slice(1).some((field) => {
      const value = selectedOptions[field]
      return typeof value !== 'string' || identifier(value) !== value.trim()
    })
  ) return null
  return {
    itemId,
    variantKey: identifier(resolved['variantKey']),
  }
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
    const nextEquipped = { ...state.equipped, [event.slot]: event.item }
    const resolvedEnhancements = gearEnhancementsFromResolvedSnapshot(
      event.snapshot,
      nextEquipped,
    )
    if (!resolvedEnhancements) return { state, committed: false, reload: false }
    return {
      state: {
        ...state,
        equipped: nextEquipped,
        enhancements: resolvedEnhancements,
        candidateDraft: null,
      },
      committed: true,
      reload: false,
    }
  }
  const resolvedEnhancements = gearEnhancementsFromResolvedSnapshot(
    event.snapshot,
    state.equipped,
  )
  if (!resolvedEnhancements?.[event.slot]) return { state, committed: false, reload: false }
  return {
    state: {
      ...state,
      enhancements: resolvedEnhancements,
      enhancementDraft: null,
    },
    committed: true,
    reload: false,
  }
}
