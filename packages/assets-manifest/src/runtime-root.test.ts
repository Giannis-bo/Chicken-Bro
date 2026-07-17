import { describe, expect, it } from 'vitest'

import { isImmutableRemoteAssetRoot, normalizeAssetRuntimeRoot } from './runtime-root.cjs'

describe('asset runtime root', () => {
  it('accepts one versioned HTTPS release shape for config and runtime use', () => {
    const root = 'https://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2/'
    expect(isImmutableRemoteAssetRoot(root)).toBe(true)
    expect(normalizeAssetRuntimeRoot(root)).toBe(
      'https://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2',
    )
  })

  it.each([
    'http://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2',
    'https://cdn.example.com/wow-assets',
    'https://cdn.example.com/wow-assets/releases/latest',
    'https://cdn.example.com/wow-assets/releases/short',
    'https://cdn.example.com/wow-assets/releases/2026-07-18-ui-v2?mutable=1',
  ])('rejects mutable or non-HTTPS remote root %s', (root) => {
    expect(isImmutableRemoteAssetRoot(root)).toBe(false)
    expect(() => normalizeAssetRuntimeRoot(root)).toThrow()
  })

  it('keeps supported local roots available for local builds', () => {
    expect(normalizeAssetRuntimeRoot('/assets/ui-v2/')).toBe('/assets/ui-v2')
    expect(normalizeAssetRuntimeRoot('.')).toBe('.')
  })
})
