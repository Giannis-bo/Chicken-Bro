import { describe, expect, it } from 'vitest'

import {
  resolveActiveTabRoute,
} from './tab-bar-items'

describe('resolveActiveTabRoute', () => {
  it('prefers the actual page stack route over a stale component router', () => {
    expect(resolveActiveTabRoute([
      'pages/builds/builds',
      'pages/news/news',
    ])).toBe('pages/builds/builds')
  })

  it('normalizes route decorations', () => {
    expect(resolveActiveTabRoute(['/pages/news/news?from=tab'])).toBe('pages/news/news')
  })

  it('falls back to the news tab when no candidate is a tab route', () => {
    expect(resolveActiveTabRoute(['pages/news/list'])).toBe('pages/news/news')
  })
})
