import { expect, it, vi } from 'vitest'
import { createAvatarClient } from './avatar'
it('reads the current owner avatar using Web Cookie authentication', async () => {
  const request = vi.fn().mockResolvedValue({ payload: { avatarDataUrl: null }, fromFallback: false, error: '' })
  const client = createAvatarClient({ request })
  const auth = { kind: 'web' as const, csrfToken: 'csrf' }
  await client.get(auth)
  expect(request).toHaveBeenCalledWith('/api/v2/me/avatar', expect.objectContaining({ method: 'GET', credentials: 'include', baseUrl: 'web-auth', auth }))
})
