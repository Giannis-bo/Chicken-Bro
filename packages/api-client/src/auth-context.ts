import type { RequestBase, RequestCredentials } from './transport'


export type ClientAuthContext =
  | { kind: 'mini'; accessToken: string }
  | { kind: 'web'; csrfToken: string }

export interface ClientAuthRequest {
  header: Readonly<Record<string, string>>
  credentials: RequestCredentials
  baseUrl: RequestBase
}


function boundedCredential(value: string, label: string): string {
  if (!value || value.length > 512 || /\s/u.test(value)) {
    throw new TypeError(`${label} is invalid`)
  }
  return value
}

export function clientAuthRequest(
  auth: ClientAuthContext,
  options: { mutating: boolean },
): ClientAuthRequest {
  if (auth.kind === 'mini') {
    const accessToken = boundedCredential(auth.accessToken, 'Mini access token')
    return {
      header: { Authorization: `Bearer ${accessToken}` },
      credentials: 'omit',
      baseUrl: 'default',
    }
  }
  const csrfToken = boundedCredential(auth.csrfToken, 'Web CSRF token')
  return {
    header: options.mutating ? { 'X-CSRF-Token': csrfToken } : {},
    credentials: 'include',
    baseUrl: 'web-auth',
  }
}
