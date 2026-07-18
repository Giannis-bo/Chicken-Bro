import type {
  GearEnhancementSelection,
  GearItemReference,
  GearResolvedSnapshot,
  GearResolverContext,
  GearSelectionIntent,
  WebsimSelection,
} from './entities'

const canonicalSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand',
] as const

function identifier(value: unknown): string {
  if (typeof value !== 'string' && typeof value !== 'number') return ''
  const text = String(value).trim()
  return text.length <= 256 ? text : ''
}

function record(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasOwn(value: Readonly<Record<string, unknown>>, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(value, key)
}

/**
 * Bind the public imported item rows to the backend-verified snapshot and
 * recover only the client-owned enhancement identifiers. Any missing slot,
 * identity mismatch, or partial selectedOptions record fails closed.
 */
export function gearEnhancementsFromResolvedSnapshot(
  snapshot: GearResolvedSnapshot | undefined,
  gearBySlot: Readonly<Record<string, GearItemReference>>,
): Readonly<Record<string, GearEnhancementSelection>> | null {
  if (
    snapshot?.contractRevision !== 'gear-resolved-snapshot-v1'
    || snapshot.status !== 'verified'
    || !identifier(snapshot.resolvedGearSignature)
    || !record(snapshot.resolvedSlots)
  ) return null

  const selectedSlots = Object.keys(gearBySlot).sort()
  const resolvedSlots = Object.keys(snapshot.resolvedSlots).sort()
  if (
    selectedSlots.length === 0
    || selectedSlots.length !== resolvedSlots.length
    || selectedSlots.some((slot, index) => slot !== resolvedSlots[index] || !canonicalSlots.includes(slot as typeof canonicalSlots[number]))
  ) return null

  const result: Record<string, GearEnhancementSelection> = {}
  for (const slot of selectedSlots) {
    const item = gearBySlot[slot]
    const resolved = snapshot.resolvedSlots[slot]
    if (!item || !record(resolved)) return null
    if (
      identifier(item.itemId ?? item.id) !== identifier(resolved['itemId'])
      || identifier(item.variantKey) !== identifier(resolved['variantKey'])
    ) return null

    const selectedOptions = resolved['selectedOptions']
    if (!record(selectedOptions)) return null
    const requiredFields = [
      'gemOptionIds',
      'enchantOptionId',
      'embellishmentOptionId',
      'craftedOptionId',
      'catalystOptionId',
    ] as const
    if (requiredFields.some((field) => !hasOwn(selectedOptions, field))) return null
    const rawGemIds = selectedOptions['gemOptionIds']
    if (!Array.isArray(rawGemIds)) return null
    const gemOptionIds = rawGemIds.map(identifier)
    if (gemOptionIds.some((value) => !value)) return null
    const scalarIds = requiredFields.slice(1).map((field) => selectedOptions[field])
    if (scalarIds.some((value) => typeof value !== 'string' || identifier(value) !== value.trim())) return null

    result[slot] = {
      gemOptionIds,
      enchantOptionId: identifier(selectedOptions['enchantOptionId']),
      embellishmentOptionId: identifier(selectedOptions['embellishmentOptionId']),
      craftedOptionId: identifier(selectedOptions['craftedOptionId']),
      catalystOptionId: identifier(selectedOptions['catalystOptionId']),
    }
  }
  return result
}

export function completeGearResolverContext(
  value: GearResolverContext | undefined,
): value is GearResolverContext & {
  contractRevision: 'gear-resolver-context-v1'
  selectionSchemaRevision: string
  authoredAgainst: Readonly<Record<string, string>>
} {
  return Boolean(
    value?.contractRevision === 'gear-resolver-context-v1'
    && identifier(value.selectionSchemaRevision)
    && identifier(value.authoredAgainst?.['seasonRevision'])
    && identifier(value.authoredAgainst?.['gearCatalogRevision']),
  )
}

export interface SerializeGearIntentOptions {
  resolverContext?: GearResolverContext
  selection: WebsimSelection
  level?: number
  gearBySlot: Readonly<Record<string, GearItemReference>>
  enhancementBySlot?: Readonly<Record<string, Partial<GearEnhancementSelection> & {
    socketOptionId?: unknown
    gemOptionId?: unknown
  }>>
}

export function serializeGearSelectionIntent(
  options: SerializeGearIntentOptions,
): GearSelectionIntent | null {
  const context = options.resolverContext
  const level = Math.trunc(options.level ?? 90)
  if (!completeGearResolverContext(context) || !options.selection.classKey || !options.selection.specKey || level <= 0) {
    return null
  }

  const slots: Record<string, GearSelectionIntent['slots'][string]> = {}
  for (const slot of canonicalSlots) {
    const item = options.gearBySlot[slot]
    const itemId = identifier(item?.itemId ?? item?.id)
    if (!item || !itemId) continue
    const enhancement = options.enhancementBySlot?.[slot] ?? {}
    const gemIds = Array.isArray(enhancement.gemOptionIds)
      ? enhancement.gemOptionIds.map(identifier).filter(Boolean)
      : [identifier(enhancement.socketOptionId ?? enhancement.gemOptionId)].filter(Boolean)
    slots[slot] = {
      itemId,
      variantKey: identifier(item.variantKey),
      gemOptionIds: gemIds,
      enchantOptionId: identifier(enhancement.enchantOptionId ?? item['enchantOptionId']),
      embellishmentOptionId: identifier(enhancement.embellishmentOptionId ?? item['embellishmentOptionId']),
      craftedOptionId: identifier(enhancement.craftedOptionId ?? item['craftedOptionId']),
      catalystOptionId: identifier(enhancement.catalystOptionId ?? item['catalystOptionId']),
    }
  }

  return {
    schemaRevision: context.selectionSchemaRevision,
    authoredAgainst: {
      seasonRevision: identifier(context.authoredAgainst['seasonRevision']),
      gearCatalogRevision: identifier(context.authoredAgainst['gearCatalogRevision']),
    },
    eligibilityContext: {
      classKey: options.selection.classKey,
      specKey: options.selection.specKey,
      level,
    },
    slots,
  }
}
