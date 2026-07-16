const canonicalGearSlots = [
  'head', 'neck', 'shoulder', 'back', 'chest', 'wrist', 'hands', 'waist',
  'legs', 'feet', 'finger1', 'finger2', 'trinket1', 'trinket2', 'main_hand', 'off_hand'
]

function cleanIdentifier(value) {
  if (value === undefined || value === null || typeof value === 'boolean') return ''
  const text = String(value).trim()
  return text.length <= 256 ? text : ''
}

function completeResolverContext(value) {
  const context = value && typeof value === 'object' ? value : {}
  const authored = context.authoredAgainst && typeof context.authoredAgainst === 'object'
    ? context.authoredAgainst
    : {}
  return !!(
    context.contractRevision === 'gear-resolver-context-v1' &&
    cleanIdentifier(context.selectionSchemaRevision) &&
    cleanIdentifier(authored.seasonRevision) &&
    cleanIdentifier(authored.gearCatalogRevision)
  )
}

function normalizedEligibilityContext(value) {
  const context = value && typeof value === 'object' ? value : {}
  const classKey = cleanIdentifier(context.classKey)
  const specKey = cleanIdentifier(context.specKey)
  const level = Number(context.level)
  if (!classKey || !specKey || !Number.isInteger(level) || level <= 0) return null
  return { classKey, specKey, level }
}

function itemAtSlot(selectedGearBySlot, slot) {
  const selected = selectedGearBySlot && typeof selectedGearBySlot === 'object'
    ? selectedGearBySlot
    : {}
  if (selected[slot] && typeof selected[slot] === 'object') return selected[slot]
  return Object.keys(selected).map((key) => selected[key]).find((item) => (
    item && (item.slot === slot || item.simcSlot === slot)
  )) || null
}

function selectedGemOptionIds(enhancement) {
  if (Array.isArray(enhancement.gemOptionIds)) {
    return enhancement.gemOptionIds.map(cleanIdentifier).filter(Boolean)
  }
  const one = cleanIdentifier(enhancement.socketOptionId || enhancement.gemOptionId)
  return one ? [one] : []
}

function slotSelection(item, enhancement) {
  const itemId = cleanIdentifier(item && (item.itemId || item.id))
  if (!itemId) return null
  const selected = enhancement && typeof enhancement === 'object' ? enhancement : {}
  return {
    itemId,
    variantKey: cleanIdentifier(item && item.variantKey),
    gemOptionIds: selectedGemOptionIds(selected),
    enchantOptionId: cleanIdentifier(selected.enchantOptionId || (item && item.enchantOptionId)),
    embellishmentOptionId: cleanIdentifier(selected.embellishmentOptionId || (item && item.embellishmentOptionId)),
    craftedOptionId: cleanIdentifier(selected.craftedOptionId || (item && item.craftedOptionId)),
    catalystOptionId: cleanIdentifier(selected.catalystOptionId || (item && item.catalystOptionId))
  }
}

function serializeGearSelectionIntent(options) {
  const source = options && typeof options === 'object' ? options : {}
  const resolverContext = source.resolverContext
  const eligibilityContext = normalizedEligibilityContext(source.eligibilityContext)
  if (!completeResolverContext(resolverContext) || !eligibilityContext) return null
  const enhancements = source.enhancementBySlot && typeof source.enhancementBySlot === 'object'
    ? source.enhancementBySlot
    : {}
  const slots = {}
  canonicalGearSlots.forEach((slot) => {
    const item = itemAtSlot(source.selectedGearBySlot, slot)
    const selection = slotSelection(item, enhancements[slot])
    if (selection) slots[slot] = selection
  })
  return {
    schemaRevision: cleanIdentifier(resolverContext.selectionSchemaRevision),
    authoredAgainst: {
      seasonRevision: cleanIdentifier(resolverContext.authoredAgainst.seasonRevision),
      gearCatalogRevision: cleanIdentifier(resolverContext.authoredAgainst.gearCatalogRevision)
    },
    eligibilityContext,
    slots
  }
}

module.exports = {
  completeResolverContext,
  serializeGearSelectionIntent
}
