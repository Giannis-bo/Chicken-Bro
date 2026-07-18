import { afterEach, describe, expect, it } from 'vitest'

import {
  configureTrustedMediaHosts,
  isTrustedRuntimeMediaUrl,
  resetTrustedMediaHosts,
} from './runtime-media'

describe('trusted runtime media guard', () => {
  afterEach(() => resetTrustedMediaHosts())

  it('allows only HTTPS URLs on an exact host or its subdomain', () => {
    configureTrustedMediaHosts(['media.example.test'])
    expect(isTrustedRuntimeMediaUrl('https://media.example.test/a.png')).toBe(true)
    expect(isTrustedRuntimeMediaUrl('https://cdn.media.example.test/a.png')).toBe(true)
    expect(isTrustedRuntimeMediaUrl('https://notmedia.example.test/a.png')).toBe(false)
  })

  it('rejects unsafe schemes, credentials, malformed URLs, and empty values', () => {
    configureTrustedMediaHosts(['media.example.test'])
    expect(isTrustedRuntimeMediaUrl('http://media.example.test/a.png')).toBe(false)
    expect(isTrustedRuntimeMediaUrl('https://user:secret@media.example.test/a.png')).toBe(false)
    expect(isTrustedRuntimeMediaUrl('data:image/png;base64,AA==')).toBe(false)
    expect(isTrustedRuntimeMediaUrl('/local.png')).toBe(false)
    expect(isTrustedRuntimeMediaUrl(undefined)).toBe(false)
  })

  it('allows the backend official World of Warcraft render host by default', () => {
    expect(isTrustedRuntimeMediaUrl('https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg')).toBe(true)
    expect(isTrustedRuntimeMediaUrl('https://render.worldofwarcraft.example/us/icons/56/inv_helm.jpg')).toBe(false)
  })
})
