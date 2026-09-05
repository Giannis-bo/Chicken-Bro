// @vitest-environment jsdom
import { act, createElement, useRef } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useChatAutoScroll } from './use-chat-auto-scroll'

let host: HTMLDivElement
let root: Root
let height = 900
let top = 0
let resize: () => void
const disconnect = vi.fn()

function Harness({ text, conversation = 'one', sending = true }: { text: string; conversation?: string; sending?: boolean }) {
  const list = useRef<HTMLDivElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const { paused, jumpToLatest } = useChatAutoScroll(list, content, conversation, sending, text)
  return <><div ref={list} data-list tabIndex={0}><div ref={content}>{text}</div></div>
    {paused && <button onClick={jumpToLatest}>回到最新</button>}</>
}
const render = async (text: string, conversation = 'one', sending = true) => {
  await act(async () => root.render(createElement(Harness, { text, conversation, sending })))
}
const list = () => host.querySelector<HTMLDivElement>('[data-list]')!

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback: () => void) { resize = callback }
    observe() { /* Layout changes are driven explicitly in this DOM test. */ }
    disconnect = disconnect
  })
  height = 900
  top = 0
  disconnect.mockClear()
  vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockImplementation(() => height)
  vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(300)
  vi.spyOn(HTMLElement.prototype, 'scrollTop', 'get').mockImplementation(() => top)
  vi.spyOn(HTMLElement.prototype, 'scrollTop', 'set').mockImplementation(value => { top = Math.max(0, Math.min(value, height - 300)) })
  host = document.createElement('div')
  document.body.append(host)
  root = createRoot(host)
})
afterEach(async () => {
  await act(async () => root.unmount())
  window.getSelection()?.removeAllRanges()
  host.remove()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('follows each response update and late layout growth after completion', async () => {
  await render('第一段')
  expect(top).toBe(600)
  height = 1200
  await render('第一段\n第二段')
  expect(top).toBe(900)
  height = 1400
  await render('完整回答', 'one', false)
  expect(top).toBe(1100)
  height = 1600
  await act(async () => resize())
  expect(top).toBe(1300)
  height = 1100
  top = 800 // Browser clamps to the new maximum before ResizeObserver runs.
  await act(async () => list().dispatchEvent(new Event('scroll')))
  await act(async () => resize())
  expect(host.querySelector('button')).toBeNull()
  height = 1300
  await render('继续增长', 'one', false)
  expect(top).toBe(1000)
  await act(async () => root.render(null))
  expect(disconnect).toHaveBeenCalled()
})

it('pauses for reading earlier messages and resumes when the user scrolls to the bottom', async () => {
  await render('第一段')
  await act(async () => list().dispatchEvent(new WheelEvent('wheel', { deltaY: -100 })))
  top = 350
  await act(async () => list().dispatchEvent(new Event('scroll')))
  height = 1200
  await render('第一段\n第二段')
  expect(top).toBe(350)
  expect(host.querySelector('button')).not.toBeNull()
  top = 900
  await act(async () => list().dispatchEvent(new Event('scroll')))
  height = 1300
  await render('第三段')
  expect(top).toBe(1000)
  expect(host.querySelector('button')).toBeNull()
})

it('keeps text selection still during output and supports an explicit return to latest', async () => {
  await render('可以选择的回复')
  const range = document.createRange()
  range.selectNodeContents(list().firstElementChild!)
  window.getSelection()?.addRange(range)
  await act(async () => document.dispatchEvent(new Event('selectionchange')))
  height = 1200
  await act(async () => resize())
  expect(top).toBe(600)
  expect(window.getSelection()?.toString()).toBe('可以选择的回复')
  await act(async () => host.querySelector<HTMLButtonElement>('button')!.click())
  expect(top).toBe(900)
  height = 1300
  await act(async () => resize())
  expect(top).toBe(1000)
})

it('resets following on conversation changes and a new send', async () => {
  await render('旧回答', 'one', false)
  await act(async () => list().dispatchEvent(new KeyboardEvent('keydown', { key: 'PageUp' })))
  top = 0
  await render('新会话', 'two', false)
  expect(top).toBe(600)
  await act(async () => list().dispatchEvent(new WheelEvent('wheel', { deltaY: -50 })))
  top = 0
  await render('新请求', 'two', true)
  expect(top).toBe(600)
})
