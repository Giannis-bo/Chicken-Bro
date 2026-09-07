import { isAvatarResponse, type AvatarResponse } from '@wow-mini/domain'
import type { ClientAuthContext } from './auth-context'
import { apiV2Path } from './api-v2-prefix'
import type { ApiResult, ApiTransport } from './transport'

export interface AvatarClient {
  get(auth: ClientAuthContext): Promise<ApiResult<AvatarResponse>>
  set(dataUrl: string, auth: Extract<ClientAuthContext, { kind: 'mini' }>): Promise<ApiResult<AvatarResponse>>
}

export function createAvatarClient(transport: ApiTransport): AvatarClient {
  const request = (auth: ClientAuthContext, dataUrl?: string) => transport.request<AvatarResponse>(apiV2Path('/me/avatar'), {
    method: dataUrl === undefined ? 'GET' : 'PUT',
    ...(dataUrl === undefined ? {} : { data: { avatarDataUrl: dataUrl } }),
    auth, credentials: auth.kind === 'web' ? 'include' : 'omit',
    baseUrl: auth.kind === 'web' ? 'web-auth' : 'default',
    responseMode: 'structured-problem',
    fallback: () => ({ avatarDataUrl: null }), validate: isAvatarResponse,
  })
  return { get: auth => request(auth), set: (dataUrl, auth) => request(auth, dataUrl) }
}
