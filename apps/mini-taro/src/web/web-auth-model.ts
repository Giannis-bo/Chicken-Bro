import {
  isValidBrowserVerifier,
  isWebLoginCreated,
  type WebLoginCreated,
  type WebLoginStatusResponse,
} from '@wow-mini/domain'

export const BROWSER_VERIFIER_STORAGE_KEY = 'chickenbro.web.login.verifier'

export type WebAuthPhase =
  | 'idle'
  | 'pending'
  | 'confirmed'
  | 'authenticated'
  | 'blocked'
  | 'expired'
  | 'cancelled'

export interface WebAuthState {
  phase: WebAuthPhase
  sessionId: string
  qrDataUrl: string
  expiresAt: string
  polling: boolean
  errorCode: string
  errorMessage: string
}

export type WebAuthStateEvent =
  | { type: 'created'; payload: WebLoginCreated }
  | { type: 'status'; payload: WebLoginStatusResponse }
  | { type: 'authenticated' }
  | { type: 'blocked'; code?: string; message?: string }
  | { type: 'logout' }

export const initialWebAuthState: WebAuthState = {
  phase: 'idle',
  sessionId: '',
  qrDataUrl: '',
  expiresAt: '',
  polling: false,
  errorCode: '',
  errorMessage: '',
}

const statusPhase = (status: WebLoginStatusResponse['status']): WebAuthPhase => {
  if (status === 'confirmed') return 'confirmed'
  if (status === 'expired') return 'expired'
  if (status === 'cancelled') return 'cancelled'
  if (status === 'exchanged') return 'authenticated'
  return 'pending'
}

function terminalState(
  state: WebAuthState,
  phase: Extract<WebAuthPhase, 'authenticated' | 'expired' | 'cancelled'>,
  expiresAt = state.expiresAt,
): WebAuthState {
  return {
    ...state,
    phase,
    expiresAt,
    polling: false,
    errorCode: '',
    errorMessage: '',
  }
}

export function reduceWebAuthState(state: WebAuthState, event: WebAuthStateEvent): WebAuthState {
  if (event.type === 'logout') return initialWebAuthState

  if (event.type === 'created') {
    if (!isWebLoginCreated(event.payload)) {
      return {
        ...initialWebAuthState,
        phase: 'blocked',
        errorCode: 'INVALID_QR_RESPONSE',
        errorMessage: '登录二维码无效，请重新生成',
      }
    }
    return {
      ...initialWebAuthState,
      phase: 'pending',
      sessionId: event.payload.sessionId,
      qrDataUrl: event.payload.qrDataUrl,
      expiresAt: event.payload.expiresAt,
      polling: true,
    }
  }

  if (event.type === 'status') {
    const phase = statusPhase(event.payload.status)
    if (phase === 'authenticated') return terminalState(state, phase, event.payload.expiresAt)
    if (phase === 'expired' || phase === 'cancelled') return terminalState(state, phase, event.payload.expiresAt)
    return {
      ...state,
      phase,
      expiresAt: event.payload.expiresAt,
      polling: true,
      errorCode: '',
      errorMessage: '',
    }
  }

  if (event.type === 'authenticated') return terminalState(state, 'authenticated')

  return {
    ...state,
    phase: 'blocked',
    polling: false,
    errorCode: event.code ?? 'AUTH_REQUEST_FAILED',
    errorMessage: event.message ?? '登录服务暂不可用，请稍后重试',
  }
}

function encodeBase64Url(bytes: Uint8Array): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let output = ''
  for (let index = 0; index < bytes.length; index += 3) {
    const first = bytes[index] ?? 0
    const second = bytes[index + 1]
    const third = bytes[index + 2]
    output += alphabet[first >> 2]
    output += alphabet[((first & 3) << 4) | ((second ?? 0) >> 4)]
    output += second === undefined ? '=' : alphabet[((second & 15) << 2) | ((third ?? 0) >> 6)]
    output += third === undefined ? '=' : alphabet[third & 63]
  }
  return output.replace(/\+/gu, '-').replace(/\//gu, '_').replace(/=+$/u, '')
}

function randomBase64Url(byteLength: number): string {
  const bytes = new Uint8Array(byteLength)
  if (!globalThis.crypto?.getRandomValues) throw new Error('WEB_CRYPTO_UNAVAILABLE')
  globalThis.crypto.getRandomValues(bytes)
  return encodeBase64Url(bytes)
}

export function getOrCreateBrowserVerifier(storage: Storage | undefined = (
  typeof window === 'undefined' ? undefined : window.sessionStorage
)): string {
  if (!storage) throw new Error('WEB_BROWSER_STORAGE_UNAVAILABLE')
  try {
    const existing = storage.getItem(BROWSER_VERIFIER_STORAGE_KEY)
    if (isValidBrowserVerifier(existing)) return existing
    const verifier = randomBase64Url(32)
    storage.setItem(BROWSER_VERIFIER_STORAGE_KEY, verifier)
    return verifier
  } catch {
    throw new Error('WEB_BROWSER_STORAGE_UNAVAILABLE')
  }
}

export function createWebLoginIdempotencyKey(): string {
  return randomBase64Url(16)
}
