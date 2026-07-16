type SelectorMarkerValue = boolean | number | string

function normalizeSelectorMarker(value: SelectorMarkerValue): string {
  const normalized = String(value)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')

  return normalized || 'empty'
}

export function styleSelectorClass(name: string): string {
  return `wx-style-${normalizeSelectorMarker(name)}`
}

export function dataSelectorClass(attribute: string, value: SelectorMarkerValue): string {
  const normalizedAttribute = attribute.replace(/^data-/, '')
  return `wx-data-${normalizeSelectorMarker(normalizedAttribute)}-${normalizeSelectorMarker(value)}`
}

export function selectorClass(
  ...values: readonly (string | false | null | undefined)[]
): string {
  return values.filter((value): value is string => typeof value === 'string' && value.length > 0).join(' ')
}
