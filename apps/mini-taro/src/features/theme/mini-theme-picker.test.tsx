// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
const device = vi.hoisted(() => new Map<string, unknown>())
vi.mock('@tarojs/taro', () => ({ default: {
  getStorageSync: (key: string) => device.get(key),
  setStorageSync: (key: string, value: unknown) => { device.set(key, value) },
} }))
vi.mock('@tarojs/components', async () => {
  const { createElement: h } = await import('react')
  return { View: (p: Record<string, unknown>) => h('div', p), Text: (p: Record<string, unknown>) => h('span', p), Button: (p: Record<string, unknown>) => h('button', p) }
})
import { MiniThemePicker } from './MiniThemePicker'
import { useMiniTheme } from './use-mini-theme'
function CachedPage() {
  const { theme, themeStyle } = useMiniTheme()
  return <div data-cached-page={theme.id} style={themeStyle} />
}
it('changes cached page visuals immediately and remembers the picker selection', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true })
  const host = document.createElement('div'); const root = createRoot(host)
  try {
    await act(async () => root.render(createElement('div', {}, createElement(MiniThemePicker), createElement(CachedPage))))
    expect(host.querySelectorAll('[data-theme-choice]')).toHaveLength(7)
    await act(async () => (host.querySelector('[data-theme-choice="alliance"]') as HTMLButtonElement).click())
    expect(host.querySelector('[data-cached-page="alliance"]')?.getAttribute('style')).toContain('--mini-theme-accent: #466b94')
    expect(device.get('chickenbro.mini.theme.v1')).toBe('alliance')
    expect(host.querySelector('[data-theme-choice="alliance"]')?.getAttribute('aria-label')).toContain('已选择')
  } finally { await act(async () => root.unmount()) }
})
