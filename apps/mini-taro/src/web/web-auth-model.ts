import {
  isValidBrowserVerifier,
  isValidIdempotencyKey,
  isWebLoginCreated,
  type WebLoginCreated,
  type WebLoginStatusResponse,
} from '@wow-mini/domain'

export const BROWSER_VERIFIER_STORAGE_KEY = 'chickenbro.web.login.verifier'

export type WebAuthPhase =
  | 'checking'
  | 'signed_out'
  | 'qr_pending'
  | 'qr_confirmed'
  | 'authenticated'
  | 'blocked'

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
  | { type: 'signed_out'; code?: string; message?: string }
  | { type: 'blocked'; code?: string; message?: string }
  | { type: 'logout' }

export const initialWebAuthState: WebAuthState = {
  phase: 'checking',
  sessionId: '',
  qrDataUrl: '',
  expiresAt: '',
  polling: false,
  errorCode: '',
  errorMessage: '',
}

export class WebAuthIntentFence {
  private generation = 0

  begin(): number {
    this.generation += 1
    return this.generation
  }

  capture(): number {
    return this.generation
  }

  isCurrent(generation: number): boolean {
    return generation === this.generation
  }

  invalidate(): void {
    this.generation += 1
  }
}

function signedOutState(code = '', message = ''): WebAuthState {
  return {
    ...initialWebAuthState,
    phase: 'signed_out',
    polling: false,
    errorCode: code,
    errorMessage: message,
  }
}

export function reduceWebAuthState(state: WebAuthState, event: WebAuthStateEvent): WebAuthState {
  if (event.type === 'logout') return signedOutState()
  if (event.type === 'signed_out') return signedOutState(event.code, event.message)

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
      phase: 'qr_pending',
      sessionId: event.payload.sessionId,
      qrDataUrl: event.payload.qrDataUrl,
      expiresAt: event.payload.expiresAt,
      polling: true,
    }
  }

  if (event.type === 'status') {
    if (
      !state.sessionId
      || !['qr_pending', 'qr_confirmed', 'blocked'].includes(state.phase)
    ) return state
    if (event.payload.status === 'expired') {
      return signedOutState('WEB_LOGIN_EXPIRED', '二维码已过期，请重新生成')
    }
    if (event.payload.status === 'cancelled') {
      return signedOutState('WEB_LOGIN_CANCELLED', '登录已取消，请重新生成')
    }
    if (event.payload.status === 'consumed') {
      if (state.phase === 'qr_confirmed') return state
      return {
        ...initialWebAuthState,
        phase: 'checking',
        expiresAt: event.payload.expiresAt,
      }
    }
    const phase = event.payload.status === 'confirmed' || state.phase === 'qr_confirmed'
      ? 'qr_confirmed'
      : 'qr_pending'
    return {
      ...state,
      phase,
      expiresAt: event.payload.expiresAt,
      polling: phase === 'qr_pending',
      errorCode: '',
      errorMessage: '',
    }
  }

  if (event.type === 'authenticated') {
    return {
      ...initialWebAuthState,
      phase: 'authenticated',
      polling: false,
    }
  }

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

export interface WebLoginCreateAttempt {
  browserVerifier: string
  idempotencyKey: string
}

export function shouldDiscardWebLoginCreateAttempt(problemCode: string | undefined): boolean {
  return problemCode === 'WEB_LOGIN_RESTART_REQUIRED'
}

export function selectWebLoginCreateAttempt(
  current: WebLoginCreateAttempt | null,
  browserVerifier: string,
  replaceActive: boolean,
  createKey: () => string = createWebLoginIdempotencyKey,
): WebLoginCreateAttempt {
  if (!isValidBrowserVerifier(browserVerifier)) throw new Error('WEB_LOGIN_VERIFIER_INVALID')
  if (!replaceActive && current?.browserVerifier === browserVerifier) return current
  const idempotencyKey = createKey()
  if (!isValidIdempotencyKey(idempotencyKey)) throw new Error('WEB_LOGIN_REQUEST_KEY_INVALID')
  return { browserVerifier, idempotencyKey }
}
