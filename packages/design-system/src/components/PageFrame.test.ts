import { describe, expect, it } from 'vitest'

import { resolvePageChromeMode, type PageFrameVariant } from './PageFrame.chrome'

describe('resolvePageChromeMode', () => {
  it.each<PageFrameVariant>([
    'news-home',
    'builds-home',
    'simulator-home',
    'profile',
  ])('keeps the primary tab root %s on root chrome', (variant) => {
    expect(resolvePageChromeMode(variant)).toBe('root')
    expect(resolvePageChromeMode(variant, () => undefined)).toBe('root')
  })

  it('uses pushed chrome for routes with a back affordance', () => {
    expect(resolvePageChromeMode('workbench')).toBe('pushed')
    expect(resolvePageChromeMode('news-detail', () => undefined)).toBe('pushed')
    expect(resolvePageChromeMode('build-intel', () => undefined)).toBe('pushed-action')
    expect(resolvePageChromeMode('simc-submit', () => undefined)).toBe('pushed-action')
    expect(resolvePageChromeMode('chickenbro-chat', () => undefined)).toBe('chat')
  })

  it('does not manufacture back chrome for secondary content without a back handler', () => {
    expect(resolvePageChromeMode('news-detail')).toBe('root')
  })
})
