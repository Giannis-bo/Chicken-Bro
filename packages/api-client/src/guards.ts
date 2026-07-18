export type UnknownRecord = Record<string, unknown>

export function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isString(value: unknown): value is string {
  return typeof value === 'string'
}

export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function hasArray(value: unknown, key: string): value is UnknownRecord {
  return isRecord(value) && Array.isArray(value[key])
}

export function cleanString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

export function stringArray(value: unknown): readonly string[] {
  return Array.isArray(value) ? value.filter(isNonEmptyString) : []
}

export function encodeQuery(
  values: Readonly<Record<string, string | number | boolean | undefined>>,
): string {
  return Object.entries(values)
    .filter((entry): entry is [string, string | number | boolean] => entry[1] !== undefined)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}
