export interface WebLoginExchangeResponse {
  authenticated: true
  requestId?: string
}

export interface MeResponse {
  connected: true
  displayName: string
  avatarUrl?: string
  requestId?: string
}

export interface LogoutResponse {
  loggedOut: true
  requestId?: string
}

export interface QqLoginCreated {
  authorizationUrl: string
  requestId?: string
}

const AVATAR_DATA_URL_PATTERN = /^data:image\/(?:png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/u

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasExactResponseKeys(
  value: Record<string, unknown>,
  required: readonly string[],
): boolean {
  const allowed = new Set([...required, 'requestId'])
  const actual = Object.keys(value)
  return required.every((key) => Object.prototype.hasOwnProperty.call(value, key))
    && actual.every((key) => allowed.has(key))
    && actual.length <= required.length + 1
}


function isRequestId(value: unknown): value is string | undefined {
  return value === undefined || (typeof value === 'string' && value.length > 0 && value.length <= 128)
}

export function isOfficialQqAuthorizationUrl(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 4096) return false
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && url.hostname === 'graph.qq.com' && url.port === ''
      && url.username === '' && url.password === '' && url.pathname === '/oauth2.0/authorize' && url.hash === ''
  } catch { return false }
}

export function isQqLoginCreated(value: unknown): value is QqLoginCreated {
  return isRecord(value) && hasExactResponseKeys(value, ['authorizationUrl'])
    && isOfficialQqAuthorizationUrl(value['authorizationUrl']) && isRequestId(value['requestId'])
}


export function isValidIdempotencyKey(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._~-]{8,128}$/u.test(value)
}



export function isWebLoginExchangeResponse(value: unknown): value is WebLoginExchangeResponse {
  if (!isRecord(value)) return false
  return hasExactResponseKeys(value, ['authenticated'])
    && value['authenticated'] === true
    && isRequestId(value['requestId'])
}



export function isMeResponse(value: unknown): value is MeResponse {
  if (!isRecord(value)) return false
  const displayName = value['displayName']
  const avatarUrl = value['avatarUrl']
  let validAvatar = avatarUrl === undefined
  if (typeof avatarUrl === 'string' && avatarUrl.length <= 4096) {
    try {
      const url = new URL(avatarUrl)
      validAvatar = url.protocol === 'https:' && url.port === '' && url.username === '' && url.password === ''
        && (url.hostname === 'q.qlogo.cn' || url.hostname === 'thirdqq.qlogo.cn') && url.hash === ''
    } catch { validAvatar = false }
  }
  return Object.keys(value).every(key => ['connected', 'displayName', 'avatarUrl', 'requestId'].includes(key))
    && value['connected'] === true
    && typeof displayName === 'string'
    && displayName.length <= 256
    && validAvatar
    && isRequestId(value['requestId'])
}

export function isLogoutResponse(value: unknown): value is LogoutResponse {
  if (!isRecord(value)) return false
  return hasExactResponseKeys(value, ['loggedOut'])
    && value['loggedOut'] === true
    && isRequestId(value['requestId'])
}


export interface AvatarResponse {
  avatarDataUrl: string | null
  requestId?: string
}

export function isAvatarResponse(value: unknown): value is AvatarResponse {
  if (!isRecord(value) || !hasExactResponseKeys(value, ['avatarDataUrl'])) return false
  const avatar = value['avatarDataUrl']
  return (avatar === null || (typeof avatar === 'string' && avatar.length <= 349551 && AVATAR_DATA_URL_PATTERN.test(avatar)))
    && isRequestId(value['requestId'])
}
