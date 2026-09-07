import { describe, expect, it } from 'vitest'

import { resolveActiveTabRoute, tabBarItems } from './tab-bar-items'

describe('resolveActiveTabRoute', () => {
  it('prefers the actual page stack route over a stale component router', () => {
    expect(resolveActiveTabRoute([
      'pages/simc/index',
      'pages/chickenbro/index',
    ])).toBe('pages/simc/index')
  })

  it('normalizes route decorations', () => {
    expect(resolveActiveTabRoute(['/pages/chickenbro/index?from=tab'])).toBe('pages/chickenbro/index')
  })

  it('falls back to the Captain tab when no candidate is a tab route', () => {
    expect(resolveActiveTabRoute(['pages/simc/tasks'])).toBe('pages/chickenbro/index')
  })

  it('contains exactly the two approved product tabs', () => {
    expect(tabBarItems.map(({ pagePath, label }) => ({ pagePath, label }))).toEqual([
      { pagePath: 'pages/chickenbro/index', label: '聊天' },
      { pagePath: 'pages/simc/index', label: 'Simc模拟' },
    ])
  })
})
