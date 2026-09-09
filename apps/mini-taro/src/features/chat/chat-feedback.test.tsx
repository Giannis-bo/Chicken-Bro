// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const native = vi.hoisted(() => ({ showModal: vi.fn() }))
vi.mock('@tarojs/taro', () => ({ default: native }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag, props)
  return { Button: host('button'), Text: host('span'), View: host('div') }
})
import ChatFeedback from '../../components/ChatFeedback'

let root: Root
let container: HTMLDivElement
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})
afterEach(async () => {
  await act(async () => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})
it('offers only the two choices, prevents duplicate sends and restores server selection', async () => {
  let finish!: () => void
  const onSubmit = vi.fn(() => new Promise<void>(resolve => { finish = resolve }))
  const render = (resolved: boolean | null) => act(async () => root.render(createElement(ChatFeedback, { resolved, onSubmit })))
  await render(null)
  expect(container.textContent).toBe('是否解决')
  expect(container.textContent).not.toMatch(/[👍👎]/u)
  expect(container.querySelectorAll('button')[0]!.getAttribute('aria-label')).toBe('已解决')
  expect(container.querySelectorAll('button')[1]!.getAttribute('aria-label')).toBe('未解决')
  expect(container.querySelector('input, textarea')).toBeNull()
  const buttons = container.querySelectorAll('button')
  await act(async () => { buttons[1]!.click(); buttons[1]!.click() })
  expect(onSubmit).not.toHaveBeenCalled()
  expect(document.querySelector('dialog')?.textContent).toContain('您的反馈会让鸡哥变得更好。')
  await confirm()
  expect(onSubmit).toHaveBeenCalledExactlyOnceWith(false)
  expect(buttons[0]!.disabled).toBe(true)
  await act(async () => finish())
  await render(false)
  expect(buttons[1]!.getAttribute('aria-pressed')).toBe('true')
  expect(buttons[0]!.disabled).toBe(true)
  expect(buttons[1]!.disabled).toBe(true)
  await act(async () => buttons[0]!.click())
  expect(document.querySelector('dialog')).toBeNull()
  expect(onSubmit).toHaveBeenCalledTimes(1)
})
it('keeps the saved selection on failure and allows retry without requesting a reason', async () => {
  const onSubmit = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(undefined)
  await act(async () => root.render(createElement(ChatFeedback, { resolved: null, onSubmit })))
  await act(async () => container.querySelectorAll('button')[1]!.click())
  await confirm()
  expect(container.textContent).toContain('反馈未保存，请重试')
  expect(container.querySelector('button')!.getAttribute('aria-pressed')).toBe('false')
  await act(async () => container.querySelectorAll('button')[1]!.click())
  await confirm()
  expect(onSubmit).toHaveBeenCalledTimes(2)
  expect(container.textContent).not.toContain('反馈未保存')
})

async function confirm() {
  await act(async () => Array.from(document.querySelectorAll('dialog button')).find(button => button.textContent === '确认')!.dispatchEvent(new MouseEvent('click', { bubbles: true })))
}
it('cancelling confirmation never submits feedback', async () => {
  const onSubmit = vi.fn()
  await act(async () => root.render(createElement(ChatFeedback, { resolved: null, onSubmit })))
  await act(async () => container.querySelector('button')!.click())
  await act(async () => Array.from(document.querySelectorAll('dialog button')).find(button => button.textContent === '取消')!.dispatchEvent(new MouseEvent('click', { bubbles: true })))
  expect(onSubmit).not.toHaveBeenCalled()
  expect(document.querySelector('dialog')).toBeNull()
})
