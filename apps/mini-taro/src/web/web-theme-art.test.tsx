// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
import WebThemeArt from './WebThemeArt'
import { webThemes } from './web-themes'

it('switches every theme as a static illustration without animated overlays', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const host = document.createElement('div')
  const root = createRoot(host)
  try {
    for (const theme of webThemes) {
      await act(async () => root.render(createElement(WebThemeArt, { themeId: theme.id })))
      const art = host.querySelector<HTMLElement>('[data-theme-art]')!
      expect(art.style.backgroundImage).toContain(theme.image)
      expect(host.querySelector('animate, filter, [data-motion-layer]')).toBeNull()
    }
  } finally {
    await act(async () => root.unmount())
    vi.unstubAllGlobals()
  }
})
