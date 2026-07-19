import { afterEach, describe, expect, it } from 'vitest'

import {
  configureTrustedMediaHosts,
  configureRuntimeMediaRoot,
  currentRuntimeMediaRoot,
  isTrustedRuntimeMediaUrl,
  resolveRuntimeMediaUrl,
  resetRuntimeMediaRoot,
  resetTrustedMediaHosts,
} from './runtime-media'

describe('trusted runtime media guard', () => {
  afterEach(() => {
    resetTrustedMediaHosts()
    resetRuntimeMediaRoot()
  })

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

  it('maps trusted source media to one immutable first-party CDN release', () => {
    configureRuntimeMediaRoot('https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1/')
    expect(currentRuntimeMediaRoot()).toBe(
      'https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1',
    )
    expect(resolveRuntimeMediaUrl(
      'https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
    )).toBe(
      'https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1/sources/wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
    )
    expect(resolveRuntimeMediaUrl(
      'https://render.worldofwarcraft.com/us/icons/56/inv_helm.jpg',
    )).toBe(
      'https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1/sources/render.worldofwarcraft.com/us/icons/56/inv_helm.jpg',
    )
  })

  it('does not depend on the Node URL module or a WHATWG URL global at app launch', () => {
    const previousUrl = globalThis.URL
    // WeChat JSCore does not guarantee the WHATWG URL constructor. App
    // bootstrap must still be able to configure and resolve runtime media.
    Reflect.deleteProperty(globalThis, 'URL')
    try {
      configureRuntimeMediaRoot('https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1')
      expect(resolveRuntimeMediaUrl(
        'https://wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg',
      )).toContain('/sources/wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg')
    } finally {
      Object.defineProperty(globalThis, 'URL', {
        configurable: true,
        writable: true,
        value: previousUrl,
      })
    }
  })

  it('accepts an already resolved URL only under the configured release root', () => {
    const root = 'https://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1'
    configureRuntimeMediaRoot(root)
    const resolved = `${root}/sources/wow.zamimg.com/images/wow/icons/large/classicon_mage.jpg`
    expect(isTrustedRuntimeMediaUrl(resolved)).toBe(true)
    expect(resolveRuntimeMediaUrl(resolved)).toBe(resolved)
    expect(resolveRuntimeMediaUrl(
      'https://static.chickenbro.cloud/wow-media/releases/other-release/sources/wow.zamimg.com/a.jpg',
    )).toBe('')
  })

  it.each([
    'https://static.chickenbro.cloud/wow-media/latest',
    'http://static.chickenbro.cloud/wow-media/releases/2026-07-19-wow-icons-v1',
    'https://static.chickenbro.cloud/wow-media/releases/short',
  ])('rejects a mutable or unsafe runtime media root %s', (root) => {
    expect(() => configureRuntimeMediaRoot(root)).toThrow()
  })

  it('rejects source queries, fragments, encoded separators, and non-image objects', () => {
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com/icon.jpg?mutable=1')).toBe('')
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com/icon.jpg#fragment')).toBe('')
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com/a%2Fb.jpg')).toBe('')
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com/icon.json')).toBe('')
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com/a/%2e%2e/icon.jpg')).toBe('')
    expect(resolveRuntimeMediaUrl('https://wow.zamimg.com:443/icon.jpg')).toBe('')
  })
})
