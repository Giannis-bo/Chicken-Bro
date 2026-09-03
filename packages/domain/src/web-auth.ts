export type WebLoginSessionStatus =
  | 'pending'
  | 'confirmed'
  | 'expired'
  | 'cancelled'
  | 'consumed'

export interface WebLoginCreated {
  sessionId: string
  expiresAt: string
  qrDataUrl: string
  requestId?: string
}

export interface WebLoginStatusResponse {
  status: WebLoginSessionStatus
  expiresAt: string
  requestId?: string
}

export interface WebLoginExchangeResponse {
  authenticated: true
  requestId?: string
}

export interface MiniExchangeResponse {
  accessToken: string
  expiresAt: string
  requestId?: string
}

export interface ConfirmResponse {
  confirmed: true
  requestId?: string
}

export interface MeResponse {
  connected: true
  displayName: string
  requestId?: string
}

export interface LogoutResponse {
  loggedOut: true
  requestId?: string
}

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iu
const QR_DATA_URL_PATTERN = /^data:image\/(?:png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/u

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isIsoDate(value: unknown): value is string {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

function isRequestId(value: unknown): value is string | undefined {
  return value === undefined || (typeof value === 'string' && value.length > 0 && value.length <= 128)
}

export function isValidBrowserVerifier(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{43,128}$/u.test(value)
}

export function isValidIdempotencyKey(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9._~-]{8,128}$/u.test(value)
}

export function isWebLoginCreated(value: unknown): value is WebLoginCreated {
  if (!isRecord(value)) return false
  if ('sceneTicket' in value) return false
  const qrDataUrl = value['qrDataUrl']
  return UUID_PATTERN.test(String(value['sessionId'] ?? ''))
    && isIsoDate(value['expiresAt'])
    && typeof qrDataUrl === 'string'
    && QR_DATA_URL_PATTERN.test(qrDataUrl)
    && !qrDataUrl.toLowerCase().includes('placeholder')
    && isRequestId(value['requestId'])
}

export function isWebLoginStatusResponse(value: unknown): value is WebLoginStatusResponse {
  if (!isRecord(value)) return false
  return ['pending', 'confirmed', 'expired', 'cancelled', 'consumed'].includes(String(value['status']))
    && isIsoDate(value['expiresAt'])
    && isRequestId(value['requestId'])
}

export function isWebLoginExchangeResponse(value: unknown): value is WebLoginExchangeResponse {
  if (!isRecord(value)) return false
  return value['authenticated'] === true && isRequestId(value['requestId'])
}

export function isMiniExchangeResponse(value: unknown): value is MiniExchangeResponse {
  if (!isRecord(value)) return false
  const accessToken = value['accessToken']
  return typeof accessToken === 'string'
    && accessToken.length >= 16
    && isIsoDate(value['expiresAt'])
    && isRequestId(value['requestId'])
}

export function isConfirmResponse(value: unknown): value is ConfirmResponse {
  if (!isRecord(value)) return false
  return value['confirmed'] === true && isRequestId(value['requestId'])
}

export function isMeResponse(value: unknown): value is MeResponse {
  if (!isRecord(value)) return false
  const displayName = value['displayName']
  return value['connected'] === true
    && typeof displayName === 'string'
    && displayName.length <= 128
    && isRequestId(value['requestId'])
}

export function isLogoutResponse(value: unknown): value is LogoutResponse {
  if (!isRecord(value)) return false
  return value['loggedOut'] === true && isRequestId(value['requestId'])
}
