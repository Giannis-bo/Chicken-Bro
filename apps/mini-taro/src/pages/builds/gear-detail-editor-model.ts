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
  readonly state: 'ready' | 'partial' | 'blocked'
  readonly requiresVariantSelection: boolean
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

function displayStrings(value: unknown): readonly string[] {
  if (Array.isArray(value)) {
    return value.flatMap((item) => {
      if (typeof item === 'string') return text(item) ? [text(item)] : []
      if (typeof item === 'number' && Number.isFinite(item)) return [String(item)]
      if (typeof item === 'boolean') return [String(item)]
      return []
    })
  }
  const values = record(value)
  if (!values) return []
  return Object.entries(values)
    .sort(([left], [right]) => left.localeCompare(right))
    .flatMap(([key, item]) => {
      if (typeof item === 'string') return text(item) ? [`${key}=${text(item)}`] : []
      if (typeof item === 'number' && Number.isFinite(item)) return [`${key}=${String(item)}`]
      if (typeof item === 'boolean') return [`${key}=${String(item)}`]
      return []
    })
}

function identifier(value: unknown): string {
  if (typeof value !== 'string' && typeof value !== 'number') return ''
  return String(value).trim()
}

export function gearCandidateEligibilityState(candidate: GearItemReference): GearCandidateDraft['state'] {
  const compatibility = typeof candidate.compatibility === 'string'
    ? text(candidate.compatibility)
    : text(record(candidate.compatibility)?.['status'])
  const statuses = [candidate.status, candidate['state']]
    .map((value) => text(value).toLowerCase())
    .filter(Boolean)
  const blockers = strings(candidate['blockers'])
  if (
    !identifier(candidate.itemId ?? candidate.id)
    || compatibility.toLowerCase() === 'incompatible'
    || statuses.includes('blocked')
    || text(candidate.metadataStatus).toLowerCase() === 'blocked'
    || blockers.length
  ) return 'blocked'
  if (candidate.simcReady === true || statuses.some((status) => status === 'ready' || status === 'verified')) return 'ready'
  return 'partial'
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

function craftedStatViews(candidate: RecordValue): readonly GearCraftedStatView[] {
  const options = Array.isArray(candidate['craftedStatOptions']) ? candidate['craftedStatOptions'] : []
  return options.flatMap((value) => {
    const option = record(value)
    if (!option) return []
    const key = text(option['key'])
    const label = text(option['displayLabel'] ?? option['label'] ?? option['name'])
    if (!key && !label) return []
    return [{ key, label: label || key, simcOptions: displayStrings(option['simcOptions']) }]
  })
}

function selectedRawCandidateVariant(
  candidate: GearItemReference,
  variantKey: string,
): RecordValue | null {
  const variants = Array.isArray(candidate['variants']) ? candidate['variants'] : []
  return variants
    .map(record)
    .find((variant): variant is RecordValue => Boolean(
      variant && firstText(variant['key'], variant['variantKey']) === variantKey,
    )) ?? null
}

function selectedVariantCraftedStatViews(
  candidate: GearItemReference,
  variantKey: string,
): readonly GearCraftedStatView[] {
  const variants = Array.isArray(candidate['variants']) ? candidate['variants'] : []
  const variantRecords = variants.map(record).filter((variant): variant is RecordValue => Boolean(variant))
  const selected = selectedRawCandidateVariant(candidate, variantKey)
  if (selected && Array.isArray(selected['craftedStatOptions'])) return craftedStatViews(selected)
  if (variantRecords.some((variant) => Array.isArray(variant['craftedStatOptions']))) return []
  return craftedStatViews(candidate)
}

export function createCandidateDraft(slot: string, candidate: GearItemReference): GearCandidateDraft {
  const rawVariants = Array.isArray(candidate['variants']) ? candidate['variants'] : []
  return {
    slot: text(slot),
    candidate,
    state: gearCandidateEligibilityState(candidate),
    requiresVariantSelection: rawVariants.length > 0,
    selectedVariantKey: '',
    variants: candidateVariants(candidate),
    craftedStatOptions: craftedStatViews(candidate),
  }
}

export function selectCandidateVariant(draft: GearCandidateDraft, variantKey: string): GearCandidateDraft {
  const selectedVariantKey = text(variantKey)
  return {
    ...draft,
    selectedVariantKey,
    craftedStatOptions: selectedVariantCraftedStatViews(draft.candidate, selectedVariantKey),
  }
}

export function candidateDraftCanApply(draft: GearCandidateDraft): boolean {
  if (draft.state === 'blocked') return false
  if (!draft.requiresVariantSelection) return true
  return Boolean(draft.selectedVariantKey && draft.variants.some((item) => item.key === draft.selectedVariantKey && item.state !== 'blocked'))
}

export function materializeCandidateDraft(draft: GearCandidateDraft): GearItemReference | null {
  if (draft.state === 'blocked') return null
  const variant = draft.requiresVariantSelection
    ? draft.variants.find((item) => item.key === draft.selectedVariantKey && item.state !== 'blocked')
    : undefined
  if (draft.requiresVariantSelection && !variant) return null
  const candidate = draft.candidate
  const selectedRawVariant = variant
    ? selectedRawCandidateVariant(candidate, variant.key)
    : null
  const baseVariantKey = text(candidate.variantKey)
  const level = variant?.ilevel ?? finiteLevel(candidate.itemLevel, candidate.ilevel)
  const difficultyLabel = variant?.difficultyLabel ?? firstText(
    candidate['difficultyLabel'],
    candidate['trackLabel'],
  )
  const selectedItemStats = selectedRawVariant && Array.isArray(selectedRawVariant['itemStats'])
    ? selectedRawVariant['itemStats']
    : selectedRawVariant && Array.isArray(selectedRawVariant['stats'])
      ? selectedRawVariant['stats']
      : undefined
  const selectedStats = selectedRawVariant && Array.isArray(selectedRawVariant['stats'])
    ? selectedRawVariant['stats']
    : selectedItemStats
  const statSummary = firstText(selectedRawVariant?.['statSummary'], candidate['statSummary'])
  const primaryStatKey = firstText(selectedRawVariant?.['primaryStatKey'], candidate['primaryStatKey'])
  const statDisplayStatus = firstText(selectedRawVariant?.['statDisplayStatus'], candidate['statDisplayStatus'])
  const statSource = firstText(selectedRawVariant?.['statSource'], candidate['statSource'])
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
    ...(statSummary ? { statSummary } : {}),
    ...(primaryStatKey ? { primaryStatKey } : {}),
    ...(selectedItemStats ? { itemStats: selectedItemStats } : {}),
    ...(selectedStats ? { stats: selectedStats } : {}),
    ...(statDisplayStatus ? { statDisplayStatus } : {}),
    ...(statSource ? { statSource } : {}),
    ...(candidate.simcReady === true ? { simcReady: true } : {}),
    ...(text(candidate.metadataStatus) ? { metadataStatus: text(candidate.metadataStatus) } : {}),
    ...(text(candidate.compatibility) ? { compatibility: text(candidate.compatibility) } : {}),
    ...(variant ? { variantKey: variant.key } : baseVariantKey ? { variantKey: baseVariantKey } : {}),
    ...(difficultyLabel ? { difficultyLabel } : {}),
    ...(level !== null ? { ilevel: level, itemLevel: level } : {}),
    ...(Array.isArray(candidate.socketOptions) ? { socketOptions: candidate.socketOptions } : {}),
    ...(Array.isArray(candidate.enchantOptions) ? { enchantOptions: candidate.enchantOptions } : {}),
    ...(Array.isArray(candidate.embellishmentOptions) ? { embellishmentOptions: candidate.embellishmentOptions } : {}),
    ...(record(candidate.modCapabilities) ? { modCapabilities: candidate.modCapabilities } : {}),
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

export function packedEnhancementSelection(
  selection: GearEnhancementSelection,
): GearEnhancementSelection {
  return {
    gemOptionIds: selection.gemOptionIds.map(text).filter(Boolean),
    enchantOptionId: text(selection.enchantOptionId),
    embellishmentOptionId: text(selection.embellishmentOptionId),
    craftedOptionId: text(selection.craftedOptionId),
    catalystOptionId: text(selection.catalystOptionId),
  }
}

export function isEnhancementKindConfigured(
  selection: GearEnhancementSelection,
  kind: 'socket' | 'enchant' | 'embellishment',
): boolean {
  if (kind === 'socket') return selection.gemOptionIds.some((id) => Boolean(text(id)))
  if (kind === 'enchant') return Boolean(text(selection.enchantOptionId))
  return Boolean(text(selection.embellishmentOptionId))
}

export function setGemAtSocket(selection: GearEnhancementSelection, socketIndex: number, gemOptionId: string): GearEnhancementSelection {
  const packed = packedEnhancementSelection(selection)
  if (!Number.isInteger(socketIndex) || socketIndex < 0) return packed
  const gems = [...packed.gemOptionIds]
  const nextGemId = text(gemOptionId)
  if (!nextGemId) {
    if (socketIndex < gems.length) gems.splice(socketIndex, 1)
  } else if (socketIndex <= gems.length) {
    gems[socketIndex] = nextGemId
  }
  return { ...packed, gemOptionIds: gems }
}

export function setSingleEnhancement(
  selection: GearEnhancementSelection,
  kind: 'enchant' | 'embellishment',
  optionId: string,
): GearEnhancementSelection {
  const packed = packedEnhancementSelection(selection)
  return kind === 'enchant'
    ? { ...packed, enchantOptionId: text(optionId) }
    : { ...packed, embellishmentOptionId: text(optionId) }
}
