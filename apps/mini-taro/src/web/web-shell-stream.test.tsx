// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), streamMessage: vi.fn() }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { chat: api } }))
vi.mock('./WebServiceHealth', () => ({ default: () => null }))
vi.mock('./WebSimcView', () => ({ default: () => createElement('input', { 'aria-label': '模拟草稿' }) }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id'].includes(key)
      || key.startsWith('data-') || key.startsWith('aria-'))))
  return { View: host('div'), Text: host('span'), Button: host('button'), ScrollView: host('div') }
})

import WebShell from './WebShell'

describe('Web business tabs during a chat reply', () => {
  let container: HTMLDivElement
  let root: Root
  const abort = vi.fn()
  const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
  const conversation = { id: 'chat-one', title: '切换标签测试', updatedAt: '2026-09-06' }
  const envelope = { requestId: 'request', runId: 'run', conversationId: conversation.id }

  beforeEach(async () => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    vi.clearAllMocks()
    api.list.mockResolvedValue(success({ items: [conversation], nextCursor: null }))
    api.get.mockResolvedValue(success({ ...conversation, messages: [] }))
    api.streamMessage.mockReturnValue({ abort })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => root.render(createElement(WebShell, {
      accountLabel: '测试', auth: { kind: 'web', csrfToken: 'test-csrf' }, onLogout: vi.fn(),
    })))
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.unstubAllGlobals()
  })
  async function click(label: string) {
    await act(async () => container.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`)!.click())
  }
  async function send() {
    const input = container.querySelector('textarea')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(input, '请继续解释')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    await click('发送消息')
    return api.streamMessage.mock.calls[0]![2].onEvent
  }

  it.each(['waiting', 'streaming'])('keeps a %s reply alive through repeated switches and completes while hidden', async (phase) => {
    const onEvent = await send()
    await act(async () => {
      onEvent({ ...envelope, sequence: 1, type: 'started' })
      if (phase === 'streaming') onEvent({ ...envelope, sequence: 2, type: 'delta', text: '第一段' })
    })
    await click('SimC 模拟')
    expect(abort).not.toHaveBeenCalled()
    await click('队长对话')
    expect(container.querySelector('button[aria-label="正在回复"]')).not.toBeNull()
    if (phase === 'streaming') expect(container.textContent).toContain('第一段')
    await click('SimC 模拟')
    api.get.mockResolvedValue(success({ ...conversation, messages: [
      { id: 'user-one', role: 'user', content: '请继续解释', createdAt: '2026-09-06' },
      { id: 'answer-one', role: 'assistant', content: '完整回答已生成', createdAt: '2026-09-06' },
    ] }))
    await act(async () => onEvent({ ...envelope, sequence: phase === 'streaming' ? 3 : 2,
      type: 'completed', text: '完整回答已生成' }))
    await click('队长对话')
    expect(container.textContent).toContain('完整回答已生成')
    expect(container.querySelector('button[aria-label="正在回复"]')).toBeNull()
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(api.list).toHaveBeenCalledTimes(1)
    expect(abort).not.toHaveBeenCalled()
  })

  it('still aborts a pending reply when the authenticated shell is removed', async () => {
    await send()
    await click('SimC 模拟')
    expect(abort).not.toHaveBeenCalled()
    await act(async () => root.render(null))
    expect(abort).toHaveBeenCalledTimes(1)
  })

  it('mounts simulation on first visit and retains its draft on subsequent visits', async () => {
    expect(container.querySelector('[aria-label="模拟草稿"]')).toBeNull()
    await click('SimC 模拟')
    const draft = container.querySelector<HTMLInputElement>('[aria-label="模拟草稿"]')!
    draft.value = '角色链接草稿'
    await click('队长对话')
    expect(draft.closest('[hidden]')).not.toBeNull()
    await click('SimC 模拟')
    expect(container.querySelector('[aria-label="模拟草稿"]')).toBe(draft)
    expect(draft.value).toBe('角色链接草稿')
    expect(draft.closest('[hidden]')).toBeNull()
    expect(container.querySelector('textarea')!.closest('[hidden]')).not.toBeNull()
  })
})
