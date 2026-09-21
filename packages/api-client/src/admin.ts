import { isAdminAccess, isAdminOverview, type AdminGame, type AdminAccess, type AdminOverview } from '@wow-mini/domain'
import type { ClientAuthContext } from './auth-context'
import { apiV2Path } from './api-v2-prefix'
import type { ApiResult, ApiTransport } from './transport'
type Auth = Extract<ClientAuthContext, { kind: 'web' }>
export interface AdminClient {
  access(auth: Auth): Promise<ApiResult<AdminAccess | null>>
  overview(auth: Auth, start: string, end: string, game?: AdminGame): Promise<ApiResult<AdminOverview | null>>
}
export function createAdminClient(transport: ApiTransport): AdminClient {
  const options = (auth: Auth) => ({ method: 'GET' as const, auth, credentials: 'include' as const, baseUrl: 'web-auth' as const, responseMode: 'structured-problem' as const, fallback: () => null })
  return {
    access: auth => transport.request<AdminAccess | null>(apiV2Path('/admin/access'), { ...options(auth), validate: isAdminAccess }),
    overview: (auth,start,end,game='wow') => transport.request<AdminOverview | null>(apiV2Path(`/admin/overview?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}&game=${game}`), { ...options(auth), validate: isAdminOverview }),
  }
}
