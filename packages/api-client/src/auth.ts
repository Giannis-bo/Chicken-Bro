import Taro from '@tarojs/taro'

import { storageKey, type AuthSession, type AuthUser } from '@wow-mini/domain'

import { cleanString, isRecord } from './guards'
import { taroStorage, type StorageAdapter } from './storage'
import type { ApiResult, ApiTransport } from './transport'

const defaultAuthTtlMs = 7 * 24 * 60 * 60 * 1000

function parseUser(value: unknown): AuthUser | null {
  if (isRecord(value)) return value as AuthUser
  if (typeof value !== 'string' || !value) return null
  try {
    const parsed: unknown = JSON.parse(value)
    return isRecord(parsed) ? parsed as AuthUser : null
  } catch {
    return null
  }
}

export class AuthClient {
  constructor(
    private readonly transport: ApiTransport,
    private readonly storage: StorageAdapter = taroStorage,
  ) {}

  current(): AuthSession {
    const accessToken = this.storage.get<string>(storageKey('auth.token')) ?? ''
    if (!accessToken) return { accessToken: '', user: null, expiresAt: 0 }
    let expiresAt = Number(this.storage.get<string | number>(storageKey('auth.expiresAt')) ?? 0)
    if (accessToken && !expiresAt) {
      expiresAt = Date.now() + defaultAuthTtlMs
      this.storage.set(storageKey('auth.expiresAt'), String(expiresAt))
    }
    if (accessToken && expiresAt <= Date.now()) {
      this.clear()
      return { accessToken: '', user: null, expiresAt: 0 }
    }
    return {
      accessToken,
      user: parseUser(this.storage.get(storageKey('auth.user'))),
      expiresAt,
    }
  }

  profile(): AuthUser {
    const local = parseUser(this.storage.get(storageKey('profile.local'))) ?? {}
    return { ...(this.current().user ?? {}), ...local }
  }

  saveLocalProfile(profile: AuthUser): AuthUser {
    const current = parseUser(this.storage.get(storageKey('profile.local'))) ?? {}
    const nickname = cleanString(profile.nickname) || cleanString(current.nickname)
    const avatarUrl = cleanString(profile.avatarUrl) || cleanString(current.avatarUrl)
    const next: AuthUser = {
      ...(nickname ? { nickname } : {}),
      ...(avatarUrl ? { avatarUrl } : {}),
    }
    this.storage.set(storageKey('profile.local'), JSON.stringify(next))
    return next
  }

  persist(payload: unknown): AuthSession {
    if (!isRecord(payload)) return this.current()
    const accessToken = cleanString(payload['accessToken'])
    if (!accessToken) return this.current()
    const user = parseUser(payload['user'])
    const expiresAt = Number(payload['expiresAt'] ?? payload['expires_at'] ?? 0) || Date.now() + defaultAuthTtlMs
    this.storage.set(storageKey('auth.token'), accessToken)
    this.storage.set(storageKey('auth.user'), JSON.stringify(user))
    this.storage.set(storageKey('auth.expiresAt'), String(expiresAt))
    if (user) this.saveLocalProfile(user)
    return { accessToken, user, expiresAt }
  }

  clear(): void {
    this.storage.remove(storageKey('auth.token'))
    this.storage.remove(storageKey('auth.user'))
    this.storage.remove(storageKey('auth.expiresAt'))
  }

  async loginWithWechat(): Promise<AuthSession> {
    const current = this.current()
    if (current.accessToken && current.user) return current
    const login = await Taro.login()
    if (!login.code) throw new Error('wx.login did not return code')
    const result = await this.transport.requestEndpoint<Readonly<Record<string, unknown>>>('auth.wechatLogin', '/api/auth/wechat-login', {
      data: { code: login.code },
      timeoutMs: 10000,
      fallback: () => ({ accessToken: '', user: null }),
      validate: (value) => isRecord(value) && typeof value['accessToken'] === 'string' && isRecord(value['user']),
    })
    if (result.fromFallback || !cleanString(result.payload['accessToken'])) {
      throw new Error(result.error || 'wechat login failed')
    }
    return this.persist(result.payload)
  }

  async saveProfile(profile: AuthUser): Promise<ApiResult<AuthUser>> {
    const auth = await this.loginWithWechat()
    const result = await this.transport.requestEndpoint<AuthUser>('profile.upsert', '/api/me/profile', {
      data: profile,
      fallback: () => auth.user ?? this.profile(),
      validate: (value) => isRecord(value) && typeof value['openid'] === 'string',
    })
    if (!result.fromFallback) this.persist({ accessToken: auth.accessToken, user: result.payload })
    return result
  }

  async saveProfileDraft(profile: AuthUser): Promise<ApiResult<AuthUser>> {
    const local = this.saveLocalProfile(profile)
    try {
      const result = await this.saveProfile(local)
      return result.fromFallback ? { ...result, payload: local } : result
    } catch (error) {
      return {
        payload: local,
        fromFallback: true,
        error: error instanceof Error ? error.message : 'profile saved locally',
      }
    }
  }
}
