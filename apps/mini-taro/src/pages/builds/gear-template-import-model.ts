import type {
  BuildTemplate,
  CommunityTemplateReference,
  GearEnhancementSelection,
  GearItemReference,
} from '@wow-mini/domain'

export interface GearTemplateDraft {
  schemaRevision: 'gear-template-draft-v2'
  gearBySlot: Readonly<Record<string, GearItemReference>>
  enhancementBySlot: Readonly<Record<string, GearEnhancementSelection>>
}

export interface SavedGearTemplateOption {
  template: BuildTemplate
  draft: GearTemplateDraft
  label: string
}

export interface CommunityGearTemplateOption {
  template: CommunityTemplateReference
  label: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function hasGearItemIdentity(value: Record<string, unknown>): boolean {
  const itemId = value['itemId'] ?? value['id']
  return typeof itemId === 'number'
    ? Number.isFinite(itemId) && itemId > 0
    : text(itemId).length > 0
}

function gearBySlot(value: unknown): Readonly<Record<string, GearItemReference>> | null {
  if (!isRecord(value)) return null
  const result: Record<string, GearItemReference> = {}
  for (const [slot, item] of Object.entries(value)) {
    if (text(slot) && isRecord(item) && hasGearItemIdentity(item)) result[slot] = item as GearItemReference
  }
  return Object.keys(result).length ? result : null
}

function enhancementBySlot(value: unknown): Readonly<Record<string, GearEnhancementSelection>> {
  if (!isRecord(value)) return {}
  const result: Record<string, GearEnhancementSelection> = {}
  for (const [slot, selection] of Object.entries(value)) {
    if (!text(slot) || !isRecord(selection)) continue
    const gemOptionIds = Array.isArray(selection['gemOptionIds'])
      ? selection['gemOptionIds'].map(text).filter(Boolean)
      : []
    const normalized: GearEnhancementSelection = {
      gemOptionIds,
      enchantOptionId: text(selection['enchantOptionId']),
      embellishmentOptionId: text(selection['embellishmentOptionId']),
      craftedOptionId: text(selection['craftedOptionId']),
      catalystOptionId: text(selection['catalystOptionId']),
    }
    if (gemOptionIds.length
      || normalized.enchantOptionId
      || normalized.embellishmentOptionId
      || normalized.craftedOptionId
      || normalized.catalystOptionId) {
      result[slot] = normalized
    }
  }
  return result
}

function parseRaw(rawString: string): unknown {
  try {
    return JSON.parse(rawString) as unknown
  } catch {
    return null
  }
}

function stableRecord<T>(value: Readonly<Record<string, T>>): Record<string, T> {
  return Object.fromEntries(Object.entries(value).sort(([left], [right]) => left.localeCompare(right)))
}

export function serializeGearTemplateDraft(
  draft: Omit<GearTemplateDraft, 'schemaRevision'>,
): string {
  return JSON.stringify({
    schemaRevision: 'gear-template-draft-v2',
    gearBySlot: stableRecord(draft.gearBySlot),
    enhancementBySlot: stableRecord(draft.enhancementBySlot),
  })
}

export function parseGearTemplateDraft(template: Pick<BuildTemplate, 'rawString' | 'metadata'> | undefined): GearTemplateDraft | null {
  if (!template) return null
  const raw = parseRaw(template.rawString)
  const versioned = isRecord(raw) && raw['schemaRevision'] === 'gear-template-draft-v2'
  const gear = versioned
    ? gearBySlot(raw['gearBySlot'])
    : gearBySlot(raw) ?? gearBySlot(template.metadata['gearBySlot'])
  if (!gear) return null
  const enhancements = versioned
    ? enhancementBySlot(raw['enhancementBySlot'])
    : enhancementBySlot(template.metadata['enhancementBySlot'])
  return {
    schemaRevision: 'gear-template-draft-v2',
    gearBySlot: gear,
    enhancementBySlot: enhancements,
  }
}

export function savedGearTemplateOptions(
  templates: readonly BuildTemplate[],
  classKey: string,
  specKey: string,
): readonly SavedGearTemplateOption[] {
  return templates.flatMap((template) => {
    if (template.type !== 'gear' || template.classKey !== classKey || template.specKey !== specKey) return []
    const draft = parseGearTemplateDraft(template)
    return draft ? [{ template, draft, label: template.title || '已保存装备模板' }] : []
  })
}

function communityTemplateHasGear(template: CommunityTemplateReference): boolean {
  return Boolean(gearBySlot(Object.fromEntries((template.gearItems ?? []).map((item) => [text(item['slot']), item]))))
}

export function communityGearTemplateOptions(
  templates: readonly CommunityTemplateReference[],
): readonly CommunityGearTemplateOption[] {
  return templates.flatMap((template) => {
    if (!text(template.id) || template.canApplyGear === false || !communityTemplateHasGear(template)) return []
    const hero = text(template.heroLabel) || text(template.heroKey) || '社区玩家'
    const player = text(template.playerName) || text(template.name) || text(template.title)
    const realm = text(template.serverName)
    const detail = player ? `${player}${realm ? `（${realm}）` : ''}` : text(template.sourceName)
    return [{ template, label: detail ? `${hero} · ${detail}` : hero }]
  })
}
