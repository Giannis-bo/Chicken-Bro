import type { GearEnhancementSelection, GearItemReference } from '@wow-mini/domain'

export interface GearCandidateVariantView {
  readonly key: string
  readonly label: string
  readonly difficultyLabel: string
  readonly ilevel: number | null
  readonly state: 'ready' | 'partial' | 'blocked'
  readonly blockers: readonly string[]
}

export interface GearCraftedStatView {
  readonly key: string
  readonly label: string
  readonly simcOptions: readonly string[]
}

export interface GearCandidateDraft {
  readonly slot: string
  readonly candidate: GearItemReference
  readonly selectedVariantKey: string
  readonly variants: readonly GearCandidateVariantView[]
  readonly craftedStatOptions: readonly GearCraftedStatView[]
}

type RecordValue = Readonly<Record<string, unknown>>

function record(value: unknown): RecordValue | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : null
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function firstText(...values: readonly unknown[]): string {
  return values.map(text).find(Boolean) ?? ''
}

function finiteLevel(...values: readonly unknown[]): number | null {
  for (const value of values) {
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value
    const raw = text(value)
    if (!/^(?:\d+|\d+\.\d+)$/u.test(raw)) continue
    const parsed = Number(raw)
    if (Number.isFinite(parsed) && parsed > 0) return parsed
  }
  return null
}

function strings(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.map(text).filter(Boolean) : []
}

function variantState(value: RecordValue, blockers: readonly string[]): GearCandidateVariantView['state'] {
  const status = firstText(value['state'], value['status']).toLowerCase()
  if (status === 'blocked' || blockers.length) return 'blocked'
  if (status === 'ready' || status === 'verified') return 'ready'
  if (status === 'partial') return 'partial'
  return 'blocked'
}

function candidateVariants(candidate: GearItemReference): readonly GearCandidateVariantView[] {
  const variants = Array.isArray(candidate['variants']) ? candidate['variants'] : []
  const seen = new Set<string>()
  return variants.flatMap((value) => {
    const item = record(value)
    if (!item) return []
    const key = firstText(item['key'], item['variantKey'])
    if (!key || key === 'needs-variant' || seen.has(key)) return []
    seen.add(key)
    const blockers = strings(item['blockers'])
    const difficultyLabel = firstText(item['difficultyLabel'], item['trackLabel'], item['displayLabel'], item['label'], item['name'])
    return [{
      key,
      label: difficultyLabel || key,
      difficultyLabel: difficultyLabel || key,
      ilevel: finiteLevel(item['itemLevel'], item['ilevel']),
      state: variantState(item, blockers),
      blockers,
    }]
  })
}

function craftedStatViews(candidate: GearItemReference): readonly GearCraftedStatView[] {
  const options = Array.isArray(candidate['craftedStatOptions']) ? candidate['craftedStatOptions'] : []
  return options.flatMap((value) => {
    const option = record(value)
    if (!option) return []
    const key = text(option['key'])
    const label = text(option['displayLabel'] ?? option['label'] ?? option['name'])
    if (!key && !label) return []
    return [{ key, label: label || key, simcOptions: strings(option['simcOptions']) }]
  })
}

export function createCandidateDraft(slot: string, candidate: GearItemReference): GearCandidateDraft {
  return {
    slot: text(slot),
    candidate,
    selectedVariantKey: '',
    variants: candidateVariants(candidate),
    craftedStatOptions: craftedStatViews(candidate),
  }
}

export function selectCandidateVariant(draft: GearCandidateDraft, variantKey: string): GearCandidateDraft {
  return { ...draft, selectedVariantKey: text(variantKey) }
}

export function candidateDraftCanApply(draft: GearCandidateDraft): boolean {
  return Boolean(draft.selectedVariantKey && draft.variants.some((item) => item.key === draft.selectedVariantKey && item.state !== 'blocked'))
}

export function materializeCandidateDraft(draft: GearCandidateDraft): GearItemReference | null {
  const variant = draft.variants.find((item) => item.key === draft.selectedVariantKey && item.state !== 'blocked')
  if (!variant) return null
  const candidate = draft.candidate
  return {
    ...(text(candidate.id) ? { id: text(candidate.id) } : {}),
    ...(candidate.itemId !== undefined ? { itemId: candidate.itemId } : {}),
    ...(text(candidate.name) ? { name: text(candidate.name) } : {}),
    ...(text(candidate.itemName) ? { itemName: text(candidate.itemName) } : {}),
    ...(text(candidate.displayName) ? { displayName: text(candidate.displayName) } : {}),
    ...(text(candidate.iconUrl) ? { iconUrl: text(candidate.iconUrl) } : {}),
    ...(text(candidate.source) ? { source: text(candidate.source) } : {}),
    ...(text(candidate.sourceUrl) ? { sourceUrl: text(candidate.sourceUrl) } : {}),
    ...(text(candidate.sourceType) ? { sourceType: text(candidate.sourceType) } : {}),
    ...(text(candidate.statSummary) ? { statSummary: text(candidate.statSummary) } : {}),
    ...(candidate.simcReady === true ? { simcReady: true } : {}),
    ...(text(candidate.metadataStatus) ? { metadataStatus: text(candidate.metadataStatus) } : {}),
    ...(text(candidate.compatibility) ? { compatibility: text(candidate.compatibility) } : {}),
    variantKey: variant.key,
    difficultyLabel: variant.difficultyLabel,
    ...(variant.ilevel !== null ? { ilevel: variant.ilevel, itemLevel: variant.ilevel } : {}),
    ...(Array.isArray(candidate.socketOptions) ? { socketOptions: candidate.socketOptions } : {}),
    ...(Array.isArray(candidate.enchantOptions) ? { enchantOptions: candidate.enchantOptions } : {}),
    ...(Array.isArray(candidate.embellishmentOptions) ? { embellishmentOptions: candidate.embellishmentOptions } : {}),
  }
}

export function emptyEnhancementSelection(): GearEnhancementSelection {
  return {
    gemOptionIds: [],
    enchantOptionId: '',
    embellishmentOptionId: '',
    craftedOptionId: '',
    catalystOptionId: '',
  }
}

export function setGemAtSocket(selection: GearEnhancementSelection, socketIndex: number, gemOptionId: string): GearEnhancementSelection {
  if (!Number.isInteger(socketIndex) || socketIndex < 0) return selection
  const gems = [...selection.gemOptionIds]
  const nextGemId = text(gemOptionId)
  if (!nextGemId) {
    if (socketIndex < gems.length) gems[socketIndex] = ''
  } else if (socketIndex <= gems.length) {
    gems[socketIndex] = nextGemId
  }
  return { ...selection, gemOptionIds: gems }
}

export function setSingleEnhancement(
  selection: GearEnhancementSelection,
  kind: 'enchant' | 'embellishment',
  optionId: string,
): GearEnhancementSelection {
  return kind === 'enchant'
    ? { ...selection, enchantOptionId: text(optionId) }
    : { ...selection, embellishmentOptionId: text(optionId) }
}
