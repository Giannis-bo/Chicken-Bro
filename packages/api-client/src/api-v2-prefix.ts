declare const __WOW_API_V2_PREFIX__: string
declare const __WOW_WEB_AUTH_API_PREFIX__: string

const DEFAULT_API_V2_PREFIX = '/api/v2'
const SAFE_PREFIX = /^\/[A-Za-z0-9][A-Za-z0-9/_-]*$/u

function normalized(value: unknown): string {
  if (typeof value !== 'string') return ''
  const candidate = value.trim().replace(/\/+$/u, '')
  return SAFE_PREFIX.test(candidate) ? candidate : ''
}

export function apiV2Prefix(): string {
  const primary = normalized(
    typeof __WOW_API_V2_PREFIX__ === 'string' ? __WOW_API_V2_PREFIX__ : '',
  )
  if (primary) return primary
  const legacyWebPrefix = normalized(
    typeof __WOW_WEB_AUTH_API_PREFIX__ === 'string' ? __WOW_WEB_AUTH_API_PREFIX__ : '',
  )
  return legacyWebPrefix || DEFAULT_API_V2_PREFIX
}

export function apiV2Path(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new TypeError('API v2 path must be slash-prefixed')
  }
  return `${apiV2Prefix()}${path}`
}
