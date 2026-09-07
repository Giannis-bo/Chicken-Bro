// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) => key !== 'selectable')))
  return { Button: host('button'), Text: host('span'), View: host('div') }
})
import ChatReplyDetails from '../../components/ChatReplyDetails'

let root: Root
let container: HTMLDivElement
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})
it('shares Mini/Web progressive expansion, manual control and failed-history restoration', async () => {
  const render = async (text: string, status: 'thinking' | 'failed') => act(async () => root.render(
    createElement(ChatReplyDetails, { text, status, ...(status === 'failed'
      ? { completedAt: '2026-09-07T06:32:00Z', durationMs: 18500 } : {}) })))
  await render('核对', 'thinking')
  expect(container.querySelector('button')?.getAttribute('aria-expanded')).toBe('true')
  await render('核对日志', 'thinking')
  expect(container.textContent).toContain('核对日志')
  await act(async () => container.querySelector('button')!.click())
  await render('核对日志与技能', 'thinking')
  expect(container.textContent).not.toContain('核对日志与技能')
  await render('核对日志与技能', 'failed')
  expect(container.textContent).toContain('未完成')
  expect(container.textContent).toContain('2026-09-07')
  expect(container.textContent).toContain('用时 0 分 19 秒')
  expect(container.querySelector('button')?.getAttribute('aria-expanded')).toBe('false')
  await act(async () => container.querySelector('button')!.click())
  expect(container.textContent).toContain('核对日志与技能')
})
it('does not invent a duration for older replies or a summary when none was provided', async () => {
  await act(async () => root.render(createElement(ChatReplyDetails, {
    text: '', status: 'completed', completedAt: '2026-09-07T06:32:00Z',
  })))
  expect(container.textContent).toContain('2026-09-07')
  expect(container.textContent).not.toContain('用时')
  expect(container.querySelector('button')).toBeNull()
})

it.each([
  [0, '用时 0 分 0 秒'],
  [59000, '用时 0 分 59 秒'],
  [59999, '用时 1 分 0 秒'],
  [60000, '用时 1 分 0 秒'],
  [125000, '用时 2 分 5 秒'],
  [3600000, '用时 60 分 0 秒'],
])('formats %i ms as minutes and whole seconds', async (durationMs, expected) => {
  await act(async () => root.render(createElement(ChatReplyDetails, {
    text: '', status: 'completed', durationMs,
  })))
  expect(container.textContent).toBe(expected)
})
