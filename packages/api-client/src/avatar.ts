import { isAvatarResponse, type AvatarResponse } from '@wow-mini/domain'
import type { ClientAuthContext } from './auth-context'
import { apiV2Path } from './api-v2-prefix'
import type { ApiResult, ApiTransport } from './transport'

export interface AvatarClient {
  get(auth: ClientAuthContext): Promise<ApiResult<AvatarResponse>>
}

export function createAvatarClient(transport: ApiTransport): AvatarClient {
  return { get: auth => transport.request<AvatarResponse>(apiV2Path('/me/avatar'), {
    method: 'GET', auth, credentials: 'include', baseUrl: 'web-auth',
    responseMode: 'structured-problem',
    fallback: () => ({ avatarDataUrl: null }), validate: isAvatarResponse,
  }) }
}
