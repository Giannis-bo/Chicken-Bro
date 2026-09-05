import Taro from '@tarojs/taro'

import {
  taroStorage,
  type ClientAuthContext,
  type StorageAdapter,
  type WebAuthClient,
} from '@wow-mini/api-client'
import { isMiniExchangeResponse } from '@wow-mini/domain'
import { isTestLoginEnabled } from './test-login-mode'


export const MINI_SESSION_KEY = 'chickenbro.mini.session.v1'
const sessionListeners = new Set<() => void>()

function notifySessionChanged(): void {
  for (const listener of sessionListeners) listener()
}

export interface StoredMiniSession {
  accessToken: string
  expiresAt: string
}

export interface MiniSessionDependencies {
  now?: () => number
  login?: () => Promise<{ code?: string }>
}


function validSession(value: unknown, now: number): value is StoredMiniSession {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const record = value as Record<string, unknown>
  if (
    Object.keys(record).length !== 2
    || !Object.prototype.hasOwnProperty.call(record, 'accessToken')
    || !Object.prototype.hasOwnProperty.call(record, 'expiresAt')
  ) return false
  const accessToken = record['accessToken']
  const expiresAt = record['expiresAt']
  if (
    typeof accessToken !== 'string'
    || accessToken.length < 16
    || accessToken.length > 512
    || /\s/u.test(accessToken)
    || typeof expiresAt !== 'string'
    || expiresAt.length === 0
    || expiresAt.length > 64
  ) return false
  const expiry = Date.parse(expiresAt)
  return Number.isFinite(expiry) && expiry > now
}

export class MiniSessionStore {
  private readonly now: () => number
  private readonly loginProvider: () => Promise<{ code?: string }>

  constructor(
    private readonly auth: Pick<WebAuthClient, 'exchangeMiniCode' | 'logout'> & Partial<Pick<WebAuthClient, 'loginTestMini'>>,
    private readonly storage: StorageAdapter = taroStorage,
    dependencies: MiniSessionDependencies = {},
  ) {
    this.now = dependencies.now ?? (() => Date.now())
    this.loginProvider = dependencies.login ?? (() => Taro.login())
  }

  private get storageKey(): string {
    return isTestLoginEnabled() ? 'chickenbro.mini.test-session.v1' : MINI_SESSION_KEY
  }

  subscribe(listener: () => void): () => void {
    sessionListeners.add(listener)
    return () => { sessionListeners.delete(listener) }
  }

  invalidate(): void {
    this.storage.remove(this.storageKey)
    notifySessionChanged()
  }

  getValid(): StoredMiniSession | null {
    const stored = this.storage.get<unknown>(this.storageKey)
    if (validSession(stored, this.now())) return stored
    if (stored !== undefined) this.invalidate()
    return null
  }

  async login(): Promise<StoredMiniSession> {
    if (isTestLoginEnabled()) {
      notifySessionChanged()
      throw new Error('TEST_LOGIN_REQUIRED')
    }
    const login = await this.loginProvider()
    const code = typeof login.code === 'string' ? login.code.trim() : ''
    if (!code || code.length > 512) throw new Error('MINI_LOGIN_CODE_MISSING')
    const result = await this.auth.exchangeMiniCode(code)
    if (result.fromFallback || !isMiniExchangeResponse(result.payload)) {
      throw new Error(result.problemCode || 'MINI_LOGIN_FAILED')
    }
    const session: StoredMiniSession = {
      accessToken: result.payload.accessToken,
      expiresAt: result.payload.expiresAt,
    }
    if (!validSession(session, this.now())) throw new Error('MINI_LOGIN_SESSION_INVALID')
    this.storage.set(this.storageKey, session)
    notifySessionChanged()
    return session
  }

  async loginTestAccount(account: 'A' | 'B', credential: string): Promise<StoredMiniSession> {
    if (!isTestLoginEnabled() || !this.auth.loginTestMini) throw new Error('TEST_LOGIN_DISABLED')
    const result = await this.auth.loginTestMini(account, credential)
    if (result.fromFallback || !isMiniExchangeResponse(result.payload)) {
      throw new Error(result.problemCode || 'TEST_LOGIN_FAILED')
    }
    const session = { accessToken: result.payload.accessToken, expiresAt: result.payload.expiresAt }
    if (!validSession(session, this.now())) throw new Error('MINI_LOGIN_SESSION_INVALID')
    this.storage.set(this.storageKey, session)
    notifySessionChanged()
    return session
  }

  createAuthContext(): ClientAuthContext {
    const session = this.getValid()
    if (session === null) throw new Error('MINI_SESSION_REQUIRED')
    return { kind: 'mini', accessToken: session.accessToken }
  }

  async logout(): Promise<void> {
    const session = this.getValid()
    try {
      if (session !== null) {
        const result = await this.auth.logout({
          kind: 'mini',
          accessToken: session.accessToken,
        })
        if (result.fromFallback) {
          throw new Error(result.problemCode || 'MINI_LOGOUT_FAILED')
        }
      }
    } finally {
      this.invalidate()
    }
  }
}
