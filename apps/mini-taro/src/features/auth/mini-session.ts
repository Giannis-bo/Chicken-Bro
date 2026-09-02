import Taro from '@tarojs/taro'

import {
  taroStorage,
  type ClientAuthContext,
  type StorageAdapter,
  type WebAuthClient,
} from '@wow-mini/api-client'
import { isMiniExchangeResponse } from '@wow-mini/domain'


export const MINI_SESSION_KEY = 'chickenbro.mini.session.v1'

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
    private readonly auth: Pick<WebAuthClient, 'exchangeMiniCode' | 'logout'>,
    private readonly storage: StorageAdapter = taroStorage,
    dependencies: MiniSessionDependencies = {},
  ) {
    this.now = dependencies.now ?? (() => Date.now())
    this.loginProvider = dependencies.login ?? (() => Taro.login())
  }

  getValid(): StoredMiniSession | null {
    const stored = this.storage.get<unknown>(MINI_SESSION_KEY)
    if (validSession(stored, this.now())) return stored
    if (stored !== undefined) this.storage.remove(MINI_SESSION_KEY)
    return null
  }

  async login(): Promise<StoredMiniSession> {
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
    this.storage.set(MINI_SESSION_KEY, session)
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
      this.storage.remove(MINI_SESSION_KEY)
    }
  }
}
