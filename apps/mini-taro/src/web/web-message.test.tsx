// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { renderToStaticMarkup } from 'react-dom/server'
import { expect, it, vi } from 'vitest'
import WebMessage from './WebMessage'

it('renders tables, emphasis, lists, code and safe links as semantic content', () => {
  const html = renderToStaticMarkup(createElement(WebMessage, { markdown: true, content:
    '**重点**\n\n| 技能 | 次数 |\n| --- | ---: |\n| 地震术 | 64 |\n\n- 检查 `爆发`\n\n[日志](https://cn.warcraftlogs.com/reports/abc)\n\n```simc\nactions+=/lava_burst\n```' }))
  const doc = new DOMParser().parseFromString(html, 'text/html')
  expect(doc.querySelector('strong')?.textContent).toBe('重点')
  expect(doc.querySelector('tbody td')?.textContent).toBe('地震术')
  expect(doc.querySelector('li code')?.textContent).toBe('爆发')
  expect(doc.querySelector('pre code')?.textContent).toContain('actions+=/lava_burst')
  expect(doc.querySelector('a')?.getAttribute('href')).toContain('https://cn.warcraftlogs.com/')
})

it('keeps HTML and unsafe URLs inert, and handles unfinished streaming syntax', () => {
  const html = renderToStaticMarkup(createElement(WebMessage, { markdown: true,
    content: '<img src=x onerror=alert(1)>\n\n[x](javascript:alert(1))\n\n**未完成' }))
  const doc = new DOMParser().parseFromString(html, 'text/html')
  expect(doc.querySelector('img, script, a')).toBeNull()
  expect(doc.body.textContent).toContain('**未完成')
})

it('preserves parentheses in wiki reference URLs', () => {
  const html = renderToStaticMarkup(createElement(WebMessage, { markdown: true,
    content: '[Haste](https://warcraft.wiki.gg/wiki/Haste_(rating))' }))
  const doc = new DOMParser().parseFromString(html, 'text/html')
  expect(doc.querySelector('a')?.getAttribute('href')).toBe('https://warcraft.wiki.gg/wiki/Haste_(rating)')
  expect(doc.querySelector('a')?.nextSibling?.textContent ?? '').toBe('')
})

it('copies original message and reports clipboard failures honestly', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  const host = document.createElement('div')
  const root = createRoot(host)
  try {
    await act(async () => root.render(createElement(WebMessage, { content: '**原文**', markdown: true })))
    await act(async () => host.querySelector('button')!.click())
    expect(writeText).toHaveBeenCalledWith('**原文**')
    expect(host.textContent).toContain('已复制')
    writeText.mockRejectedValue(new Error('denied'))
    await act(async () => host.querySelector('button')!.click())
    expect(host.textContent).toContain('请选择文字复制')
  } finally {
    await act(async () => root.unmount())
    vi.unstubAllGlobals()
  }
})
