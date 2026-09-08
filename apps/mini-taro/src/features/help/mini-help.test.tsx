// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const menu = vi.hoisted(() => vi.fn())
vi.mock('@tarojs/taro', () => ({ default: { showActionSheet: menu } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => ({ selectable, ...props }: Record<string, unknown>) => element(tag, { ...Object.fromEntries(Object.entries(props).filter(([key]) => key !== 'scrollY')), ...(selectable ? { 'data-selectable': 'true' } : {}) })
  return { Button: host('button'), Text: host('span'), View: host('div'), ScrollView: host('div') }
})
import { MiniHelpPanel, MiniHelpActions, MiniHelpContext } from '../../components/MiniHelp'
let root: Root
let container: HTMLDivElement
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals() })
it('starts with four closed FAQ categories and expands selectable real examples and rerun guidance', async () => {
  await act(async () => root.render(createElement(MiniHelpPanel, { view: 'faq', onClose: vi.fn() })))
  const groups = Array.from(container.querySelectorAll<HTMLButtonElement>('button[aria-expanded]'))
  expect(groups).toHaveLength(4)
  expect(groups.every(button => button.getAttribute('aria-expanded') === 'false')).toBe(true)
  expect(container.textContent).not.toContain('GPT-Astra')
  for (const button of groups) await act(async () => button.click())
  expect(container.textContent).toContain('GPT-Astra')
  expect(container.querySelectorAll('[data-selectable="true"]')).not.toHaveLength(0)
  expect(container.textContent).toContain('05 · 密谋小径楼下的怪到底是谁引到的？')
  expect(container.textContent).toContain('怎样用任务 ID 换装备再跑一次？')
  expect(container.textContent).toContain('当时得到的结果')
  await act(async () => groups[1]!.click())
  expect(container.textContent).not.toContain('05 · 密谋小径楼下的怪到底是谁引到的？')
})
it('keeps the existing changelog available', async () => {
  await act(async () => root.render(createElement(MiniHelpPanel, { view: 'changelog', onClose: vi.fn() })))
  expect(container.textContent).toContain('小程序移动端交互优化')
})

it('routes the remaining FAQ and changelog menu actions independently', async () => {
  const help = vi.fn()
  await act(async () => root.render(createElement(MiniHelpContext.Provider, { value: help }, createElement(MiniHelpActions))))
  menu.mockResolvedValueOnce({ tapIndex: 0 })
  await act(async () => container.querySelector('button')!.click())
  expect(menu).toHaveBeenLastCalledWith({ itemList: ['FAQ · 常见问题', '更新日志'] })
  expect(help).toHaveBeenLastCalledWith('faq')
  menu.mockResolvedValueOnce({ tapIndex: 1 })
  await act(async () => container.querySelector('button')!.click())
  expect(help).toHaveBeenLastCalledWith('changelog')
})
