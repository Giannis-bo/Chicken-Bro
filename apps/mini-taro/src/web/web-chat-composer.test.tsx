// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), streamMessage: vi.fn() }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { chat: api } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id'].includes(key) || key.startsWith('data-'))))
  return { View: host('div'), Text: host('span'), Button: host('button'), ScrollView: host('div'),
    Textarea: (props: { value: string; onInput: (event: { detail: { value: string } }) => void }) =>
      element('textarea', { value: props.value, onChange: (event: { target: { value: string } }) =>
        props.onInput({ detail: { value: event.target.value } }) }) }
})

import WebChatView from './WebChatView'

describe('Web chat composer interactions', () => {
  let container: HTMLDivElement
  let root: Root
  beforeEach(async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    vi.clearAllMocks()
    const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
    const conversation = { id: 'chat-one', title: 'Test', updatedAt: '2026-09-05' }
    api.list.mockResolvedValue(success({ items: [conversation], nextCursor: null }))
    api.get.mockResolvedValue(success({ ...conversation, messages: [] }))
    api.streamMessage.mockReturnValue({ abort: vi.fn() })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => root.render(createElement(WebChatView, {
      auth: { kind: 'web', csrfToken: 'test-csrf' },
    })))
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })
  function input() { return container.querySelector('textarea')! }
  async function draft(value: string) {
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input(), value)
      input().dispatchEvent(new Event('input', { bubbles: true }))
    })
  }
  async function enter(options: KeyboardEventInit = {}) {
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, ...options })
    await act(async () => input().dispatchEvent(event))
    return event
  }

  it('sends once on Enter and keeps the next draft while a reply is pending', async () => {
    await draft('你好')
    expect((await enter()).defaultPrevented).toBe(true)
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(api.streamMessage.mock.calls[0]?.[1].content).toBe('你好')
    expect(input().value).toBe('')
    await draft('下一条')
    await enter()
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(input().value).toBe('下一条')
  })

  it('keeps Shift+Enter as a newline without sending', async () => {
    await draft('第一行')
    expect((await enter({ shiftKey: true })).defaultPrevented).toBe(false)
    expect(api.streamMessage).not.toHaveBeenCalled()
  })

  it.each([{ isComposing: true }, { keyCode: 229 }, { repeat: true }])(
    'does not send while composing or repeating Enter: %j', async (options) => {
      await draft('中文')
      await enter(options)
      expect(api.streamMessage).not.toHaveBeenCalled()
      expect(input().value).toBe('中文')
    },
  )

  it('replaces the arrow with one busy indicator, then restores it on failure', async () => {
    expect(container.textContent).not.toContain('对话⌄')
    await draft('你好')
    const button = container.querySelector<HTMLButtonElement>('button[aria-label="发送消息"]')
    expect(button).not.toBeNull()
    await act(async () => button!.click())
    const busy = container.querySelector<HTMLButtonElement>('button[aria-label="正在回复"]')!
    expect(busy.disabled).toBe(true)
    expect(busy.textContent).not.toContain('↑')
    expect(busy.querySelectorAll('[role="status"]')).toHaveLength(1)
    await act(async () => api.streamMessage.mock.calls[0]?.[2].onFailure('network failed'))
    expect(container.querySelector('button[aria-label="发送消息"]')?.textContent).toContain('↑')
    expect(container.querySelector('[role="status"]')).toBeNull()
  })

  it('shows waiting immediately, elapsed time after ten seconds, then yields to the reply', async () => {
    vi.useFakeTimers()
    await draft('你好')
    await enter()
    const waiting = () => container.querySelector('[role="status"][aria-label="等待回复"]')
    expect(waiting()?.textContent).toContain('鸡哥正在处理')
    expect(waiting()?.textContent).not.toContain('已等待')
    await act(async () => vi.advanceTimersByTime(10000))
    expect(waiting()?.textContent).toContain('已等待 10 秒')
    const onEvent = api.streamMessage.mock.calls[0]?.[2].onEvent
    const envelope = { requestId: 'request', runId: 'run', conversationId: 'chat-one' }
    await act(async () => onEvent({ ...envelope, sequence: 1, type: 'started' }))
    expect(waiting()).not.toBeNull()
    await act(async () => onEvent({ ...envelope, sequence: 2, type: 'delta', text: '你好，勇士' }))
    expect(waiting()).toBeNull()
    expect(container.textContent).toContain('你好，勇士')
    expect(vi.getTimerCount()).toBe(0)
    await act(async () => onEvent({ ...envelope, sequence: 3, type: 'completed', text: '你好，勇士' }))
    expect(container.querySelector('[role="status"]')).toBeNull()
  })

  it.each(['failed', 'disconnected'])('clears waiting and its timer on %s and resets on the next send', async (failure) => {
    vi.useFakeTimers()
    await draft('你好')
    await enter()
    expect(container.querySelector('[aria-label="等待回复"]')).not.toBeNull()
    await act(async () => vi.advanceTimersByTime(10000))
    const stream = api.streamMessage.mock.calls[0]?.[2]
    await act(async () => {
      if (failure === 'disconnected') stream.onFailure('network failed')
      else {
        const envelope = { requestId: 'request', runId: 'run', conversationId: 'chat-one' }
        stream.onEvent({ ...envelope, sequence: 1, type: 'started' })
        stream.onEvent({ ...envelope, sequence: 2, type: 'failed', errorCode: 'TIMEOUT', retryable: true })
      }
    })
    expect(container.querySelector('[aria-label="等待回复"]')).toBeNull()
    expect(container.querySelector('[data-error-code]')).not.toBeNull()
    expect(vi.getTimerCount()).toBe(0)
    await draft('再试一次')
    await enter()
    expect(container.querySelector('[aria-label="等待回复"]')?.textContent).toContain('鸡哥正在处理')
    expect(container.textContent).not.toContain('已等待')
    await act(async () => root.render(null))
    expect(vi.getTimerCount()).toBe(0)
  })
})
