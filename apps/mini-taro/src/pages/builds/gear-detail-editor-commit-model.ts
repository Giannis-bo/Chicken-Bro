import type {
  GearEnhancementSelection,
  GearItemReference,
  GearResolvedSnapshot,
} from '@wow-mini/domain'
import { gearEnhancementsFromResolvedSnapshot } from '@wow-mini/domain'

import {
  packedEnhancementSelection,
  type GearCandidateDraft,
} from './gear-detail-editor-model'

export type GearEnhancementKind = 'socket' | 'enchant' | 'embellishment'

export interface GearEnhancementDraft {
  readonly slot: string
  readonly requestedKind: GearEnhancementKind
  readonly selection: GearEnhancementSelection
  readonly selectionBySlot?: Readonly<Record<string, GearEnhancementSelection>>
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
      readonly status: IncompleteCommitStatus | 'resolved' | 'slot_resolved'
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

export function enhancementDraftSelections(
  draft: GearEnhancementDraft,
): Readonly<Record<string, GearEnhancementSelection>> {
  return {
    ...(draft.selectionBySlot ?? {}),
    [draft.slot]: packedEnhancementSelection(draft.selection),
  }
}

export function selectEnhancementDraftSlot(
  draft: GearEnhancementDraft,
  slot: string,
  selection: GearEnhancementSelection,
): GearEnhancementDraft {
  const selectionBySlot = enhancementDraftSelections(draft)
  const activeSelection = packedEnhancementSelection(selection)
  return {
    ...draft,
    slot,
    selection: activeSelection,
    selectionBySlot: {
      ...selectionBySlot,
      [slot]: activeSelection,
    },
  }
}

export function updateEnhancementDraftSelection(
  draft: GearEnhancementDraft,
  selection: GearEnhancementSelection,
): GearEnhancementDraft {
  const activeSelection = packedEnhancementSelection(selection)
  return {
    ...draft,
    selection: activeSelection,
    selectionBySlot: {
      ...enhancementDraftSelections(draft),
      [draft.slot]: activeSelection,
    },
  }
}

function record(value: unknown): value is Readonly<Record<string, unknown>> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function identifier(value: unknown): string {
  return typeof value === 'string' || typeof value === 'number'
    ? String(value).trim()
    : ''
}

function onlyProblemCode(value: unknown, code: string): boolean {
  return Array.isArray(value)
    && value.length === 1
    && record(value[0])
    && value[0]['code'] === code
}

function resolvedSlotIdentityFrom(
  snapshot: GearResolvedSnapshot | undefined,
  slot: string,
): ResolvedSlotIdentity | null {
  if (
    snapshot?.contractRevision !== 'gear-resolved-snapshot-v1'
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

/**
 * A blocked Resolve can still prove that every selected slot is legal.  This
 * narrower state is accepted only when the sole blocker is that the profile
 * lacks its remaining required slots; it never makes the profile executable.
 */
export function isProfileIncompleteOnlySnapshot(
  snapshot: GearResolvedSnapshot | undefined,
): boolean {
  const aggregateLegality = snapshot?.aggregateLegality
  const readiness = snapshot?.profileReadiness
  return Boolean(
    snapshot?.contractRevision === 'gear-resolved-snapshot-v1'
    && snapshot.status === 'blocked'
    && record(aggregateLegality)
    && aggregateLegality['status'] === 'verified'
    && record(readiness)
    && readiness['status'] === 'blocked'
    && readiness['simcReady'] === false
    && onlyProblemCode(snapshot['problems'], 'GEAR_REQUIRED_SLOTS_INCOMPLETE')
    && onlyProblemCode(readiness['problems'], 'GEAR_REQUIRED_SLOTS_INCOMPLETE'),
  )
}

export function resolvedSlotIdentityForIncompleteProfile(
  snapshot: GearResolvedSnapshot | undefined,
  slot: string,
): ResolvedSlotIdentity | null {
  if (!isProfileIncompleteOnlySnapshot(snapshot)) return null
  const resolved = snapshot?.resolvedSlots?.[slot]
  if (!record(resolved) || !record(resolved['legality']) || resolved['legality']['status'] !== 'verified') return null
  return resolvedSlotIdentityFrom(snapshot, slot)
}

export function resolvedSlotIdentity(
  snapshot: GearResolvedSnapshot | undefined,
  slot: string,
): ResolvedSlotIdentity | null {
  if (snapshot?.status !== 'verified') return null
  return resolvedSlotIdentityFrom(snapshot, slot)
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
  if (event.status !== 'resolved' && event.status !== 'slot_resolved') {
    return { state, committed: false, reload: false }
  }
  if (event.kind === 'candidate') {
    const nextEquipped = { ...state.equipped, [event.slot]: event.item }
    const resolvedCandidate = event.status === 'slot_resolved'
      ? resolvedSlotIdentityForIncompleteProfile(event.snapshot, event.slot)
      : resolvedSlotIdentity(event.snapshot, event.slot)
    if (
      !resolvedCandidate
      || resolvedCandidate.itemId !== identifier(event.item.itemId)
      || resolvedCandidate.variantKey !== identifier(event.item.variantKey)
    ) return { state, committed: false, reload: false }
    const resolvedEnhancements = event.status === 'slot_resolved'
      ? Object.fromEntries(Object.entries(state.enhancements).filter(([slot]) => slot !== event.slot))
      : gearEnhancementsFromResolvedSnapshot(event.snapshot, nextEquipped)
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
