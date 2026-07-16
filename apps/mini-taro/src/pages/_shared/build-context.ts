import type {
  BuildsHomePayload,
  ClassOption,
  ReadinessState,
  SpecializationOption,
  TrustLevel,
  VerifiedWowObjectReference,
} from '@wow-mini/domain'

export const defaultSpecId = '法师-冰霜'

export const scenarioOptions = [
  { key: 'single', title: '单体' },
  { key: 'aoe_5', title: '5目标' },
  { key: 'mythic_plus', title: '大秘境' },
] as const

export interface SpecSelection {
  classItem: ClassOption
  spec: SpecializationOption
  classIndex: number
  specIndex: number
  classKey: string
  specKey: string
  heroKey: string
  specId: string
  label: string
}

export function flattenSpecs(classOptions: readonly ClassOption[]): readonly Omit<SpecSelection, 'classKey' | 'specKey' | 'heroKey' | 'specId' | 'label'>[] {
  return classOptions.flatMap((classItem, classIndex) => classItem.specializations.map((spec, specIndex) => ({
    classItem,
    spec,
    classIndex,
    specIndex,
  })))
}

export function findSpecSelection(home: BuildsHomePayload, wantedId?: string): SpecSelection | null {
  const entries = flattenSpecs(home.classOptions)
  const selected = wantedId
    ? entries.find((entry) => entry.spec.id === wantedId || entry.spec.specId === wantedId)
    : entries.find((entry) => entry.spec.id === defaultSpecId) ?? entries[0]
  if (!selected) return null
  const classKey = selected.spec.websimClassKey || selected.spec.classKey || selected.classItem.websimClassKey || ''
  const specKey = selected.spec.websimSpecKey || selected.spec.specKey || ''
  const heroKey = selected.spec.heroKey || ''
  const specId = selected.spec.id || selected.spec.specId || `${selected.classItem.name}-${selected.spec.specName || selected.spec.title || selected.spec.name}`
  const label = selected.spec.title || `${selected.spec.specName || selected.spec.name}${selected.classItem.name}`
  return { ...selected, classKey, specKey, heroKey, specId, label }
}

export function specObject(
  selection: SpecSelection | null,
  trust: boolean | TrustLevel,
): VerifiedWowObjectReference | null {
  if (!selection) return null
  const iconUrl = selection.spec.specIconUrl || selection.spec.iconUrl
  const level = typeof trust === 'boolean' ? (trust ? 'source_referenced' : 'unknown') : trust
  const sourceReferenced = level === 'source_referenced' && Boolean(iconUrl && selection.spec.sourceUrl)
  const backendVerified = level === 'backend_verified' && Boolean(iconUrl)
  return {
    objectType: 'spec',
    objectId: selection.specId,
    name: selection.label,
    ...(iconUrl ? { iconUrl } : {}),
    ...(selection.spec.sourceUrl ? { sourceUrl: selection.spec.sourceUrl } : {}),
    verified: sourceReferenced || backendVerified,
    trust: sourceReferenced
      ? { level: 'source_referenced', sourceLabel: selection.spec.sourceName, sourceUrl: selection.spec.sourceUrl }
      : backendVerified
        ? { level: 'backend_verified' }
      : { level: 'unknown', reason: 'fallback 专精视觉不作为已验证物件' },
  }
}

export function readinessFromBoolean(ready: boolean, partial: boolean): ReadinessState {
  if (ready) return 'ready'
  if (partial) return 'partial'
  return 'blocked'
}
