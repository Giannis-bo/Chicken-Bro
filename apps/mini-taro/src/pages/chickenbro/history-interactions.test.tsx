// @vitest-environment jsdom
import { act, createElement, type ComponentType } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { ChatStreamOptions } from '@wow-mini/api-client'

const api = vi.hoisted(() => ({
  show: undefined as (() => void) | undefined,
  modal: vi.fn(), toast: vi.fn(), remove: vi.fn(), abort: vi.fn(),
  feedback: vi.fn(), feedbackEnabled: false,
  resolved: null as boolean | null,
  stream: undefined as ChatStreamOptions | undefined,
  storage: new Map<string, unknown>(),
}))
vi.mock('@tarojs/taro', () => ({ default: { showModal: api.modal, showToast: api.toast }, useDidShow: (fn: () => void) => { api.show = fn } }))
vi.mock('../../use-tab-root-identity', () => ({ useTabRootIdentity: () => undefined }))
vi.mock('../../features/auth/with-mini-test-login', () => ({ withMiniTestLogin: (page: ComponentType) => page }))
vi.mock('../../web/WebMessage', () => ({ default: ({ content }: { content: string }) => createElement('span', {}, content) }))
vi.mock('../../web/WebThemeArt', () => ({ default: () => null }))
vi.mock('../../web/WebReplyStatus', () => ({ default: () => null }))
vi.mock('../../web/WebMiniProgramPromo', () => ({ default: () => null }))
vi.mock('../../web/use-chat-auto-scroll', () => ({ useChatAutoScroll: () => ({ paused: false, jumpToLatest: () => undefined }) }))
vi.mock('../../components/MiniHelp', () => ({ MiniHelpActions: () => null }))
vi.mock('../../components/MiniMessage', () => ({ default: ({ content }: { content: string }) => createElement('span', {}, content) }))
vi.mock('../../components/ChatReplyDetails', () => ({ default: () => null }))
vi.mock('@tarojs/components', async () => {
  const { createElement: h } = await import('react')
  const view = (p: Record<string, unknown>) => h('div', { 'data-chat-phase': p['data-chat-phase'] }, p['children'] as never)
  return { View: view, ScrollView: view, Text: (p: Record<string, unknown>) => h('span', {}, p['children'] as never), Image: () => null,
    Button: (p: Record<string, unknown>) => h('button', { disabled: !!p['disabled'], onClick: p['onClick'] as () => void, 'aria-label': p['aria-label'], 'aria-pressed': p['aria-pressed'] as boolean }, p['children'] as never),
    Textarea: (p: Record<string, unknown>) => h('textarea', { value: p['value'] as string, onChange: () => undefined, onInput: (event: { currentTarget: HTMLTextAreaElement }) => (p['onInput'] as (e: unknown) => void)({ detail: { value: event.currentTarget.value } }) }),
  }
})
vi.mock('@wow-mini/api-client', () => {
  const summary = (id: string) => ({ id, title: `会话${id}`, status: 'active', createdAt: '2026-09-08T00:00:00Z', updatedAt: '2026-09-08T00:00:00Z' })
  const ok = (payload: unknown) => ({ fromFallback: false, payload, error: '', httpStatus: 200 })
  return { taroStorage: { get: (key: string) => api.storage.get(key), set: (key: string, value: unknown) => api.storage.set(key, value), remove: (key: string) => api.storage.delete(key) }, wowApi: { webAuth: {}, chat: {
    list: async () => ok({ items: [summary('A'), summary('B')], nextCursor: null }),
    create: async () => ok(summary('C')),
    get: async (id: string) => ok({ ...summary(id), messages: id === 'C' ? [] : [
      { id: `message-${id}`, role: 'user', content: `${id}历史消息`, createdAt: '2026-09-08T00:00:00Z' },
      ...(api.feedbackEnabled ? [{ id: `reply-${id}`, role: 'assistant', content: '鸡哥的回答', createdAt: '2026-09-08T00:00:01Z', resolved: api.resolved }] : []),
    ] }),
    setFeedback: api.feedback,
    remove: api.remove,
    streamMessage: (_id: string, _body: unknown, options: ChatStreamOptions) => { api.stream = options; return { abort: api.abort } },
  } } }
})
import ChickenbroPage from './index'
import WebChatView from '../../web/WebChatView'
let node: HTMLDivElement
let root: Root
const button = (text: string) => Array.from(node.querySelectorAll('button')).find(b => b.textContent?.includes(text) || b.getAttribute('aria-label') === text)!
async function click(text: string) { await act(async () => button(text).click()) }
async function input(value: string) {
  await act(async () => { const field = node.querySelector('textarea')!; Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, value); field.dispatchEvent(new Event('input', { bubbles: true })) })
}
beforeEach(async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
  HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
  vi.clearAllMocks(); api.storage.clear(); api.stream = undefined; api.feedbackEnabled = false; api.resolved = null
  api.feedback.mockImplementation(async (_conversation: string, _message: string, resolved: boolean) => {
    api.resolved = resolved
    return { fromFallback: false, payload: { resolved }, error: '', httpStatus: 200 }
  })
  api.storage.set('chickenbro.mini.session.v1', { accessToken: 'mini-session-valid-token', expiresAt: '2099-09-08T00:00:00Z' })
  api.modal.mockResolvedValue({ confirm: false }); api.toast.mockResolvedValue({})
  api.remove.mockResolvedValue({ fromFallback: false, payload: { deleted: true }, error: '', httpStatus: 200 })
  node = document.createElement('div'); document.body.append(node); root = createRoot(node)
  await act(async () => root.render(createElement(ChickenbroPage)))
  await act(async () => api.show?.())
})
afterEach(async () => { await act(async () => root.unmount()); node.remove(); vi.unstubAllGlobals() })

it.each(['mini', 'web'])('saves the two-choice feedback from the %s reply and restores it on reopening', async (platform) => {
  api.feedbackEnabled = true
  if (platform === 'web') {
    await act(async () => root.render(createElement(WebChatView, { auth: { kind: 'web', csrfToken: 'csrf-token' } })))
  } else {
    await act(async () => api.show?.())
  }
  expect(node.textContent).toContain('是否解决')
  expect(node.querySelectorAll('[aria-pressed]')).toHaveLength(2)
  await click('未解决')
  await click('确认')
  expect(api.feedback).toHaveBeenCalledWith('A', 'reply-A', false, { auth: platform === 'mini'
    ? { kind: 'mini', accessToken: 'mini-session-valid-token' } : { kind: 'web', csrfToken: 'csrf-token' } })
  expect(button('未解决').getAttribute('aria-pressed')).toBe('true')
  if (platform === 'mini') await click('历史对话')
  await click('会话B')
  if (platform === 'mini') await click('历史对话')
  await click('会话A')
  expect(button('未解决').getAttribute('aria-pressed')).toBe('true')
  expect(button('已解决').disabled).toBe(true)
  expect(button('未解决').disabled).toBe(true)
  await click('已解决')
  expect(api.feedback).toHaveBeenCalledTimes(1)
  expect(button('未解决').getAttribute('aria-pressed')).toBe('true')
  expect(node.querySelectorAll('textarea')).toHaveLength(1)
})

it('cancels deletion without changing selected messages or server history', async () => {
  await click('历史对话')
  expect(button('删除')).toBeDefined()
  await click('删除')
  expect(api.modal).toHaveBeenCalled()
  expect(api.remove).not.toHaveBeenCalled()
  expect(node.textContent).toContain('A历史消息')
  expect(button('会话A')).toBeDefined()
})
it('confirms deletion through the Mini session and removes the selected view', async () => {
  api.modal.mockResolvedValue({ confirm: true })
  await input('待发送草稿'); await click('历史对话')
  expect(button('删除')).toBeDefined()
  await click('删除')
  expect(api.remove).toHaveBeenCalledExactlyOnceWith('A', { auth: { kind: 'mini', accessToken: 'mini-session-valid-token' } })
  expect(button('会话A')).toBeUndefined()
  expect(node.textContent).not.toContain('A历史消息')
  expect(node.querySelector('textarea')!.value).toBe('待发送草稿')
})
it('keeps history and draft when the server rejects deletion of a replying conversation', async () => {
  api.modal.mockResolvedValue({ confirm: true })
  api.remove.mockResolvedValue({ fromFallback: true, problemCode: 'CHAT_CONVERSATION_BUSY', payload: { deleted: false } })
  await input('草稿'); await click('历史对话')
  expect(button('删除')).toBeDefined()
  await click('删除')
  expect(node.textContent).toContain('A历史消息')
  expect(button('会话A')).toBeDefined()
  expect(node.textContent).toContain('请等待回复结束后再删除')
  expect(node.querySelector('textarea')!.value).toBe('草稿')
})
it('switches history during a reply, retains the draft and ignores background deltas in the selected view', async () => {
  await input('开始回复'); await click('发送'); await input('下一条草稿')
  expect(button('历史对话').disabled).toBe(false)
  await click('历史对话'); await click('会话B')
  expect(node.textContent).toContain('B历史消息')
  expect(node.querySelector('textarea')!.value).toBe('下一条草稿')
  expect(api.abort).not.toHaveBeenCalled()
  await act(async () => api.stream!.onEvent({ type: 'delta', text: 'A后台回答', conversationId: 'A', requestId: 'request-a', runId: 'run-a', sequence: 2 }))
  expect(node.textContent).not.toContain('A后台回答')
  expect(node.textContent).toContain('B历史消息')
})

it('keeps the selected history on a network deletion failure and allows retry', async () => {
  api.modal.mockResolvedValue({ confirm: true })
  api.remove.mockRejectedValueOnce(new Error('network offline'))
  await click('历史对话'); await click('删除')
  expect(node.textContent).toContain('删除失败')
  expect(node.textContent).toContain('A历史消息')
  expect(button('删除').disabled).toBe(false)
  await click('删除')
  expect(button('会话A')).toBeUndefined()
})


it('creates an empty Mini conversation during a reply without aborting the original stream', async () => {
  await input('开始回复'); await click('发送')
  expect(button('新对话').disabled).toBe(false)
  await click('新对话')
  expect(node.textContent).toContain('今天想和鸡哥聊什么')
  expect(node.textContent).not.toContain('A历史消息')
  expect(api.abort).not.toHaveBeenCalled()
  await act(async () => api.stream!.onEvent({ type: 'delta', text: 'A后台回答', conversationId: 'A', requestId: 'request-a', runId: 'run-a', sequence: 2 }))
  expect(node.textContent).not.toContain('A后台回答')
  await click('历史对话')
  expect(button('会话C')).toBeDefined()
})

it('creates an empty Web conversation during a reply without aborting the original stream', async () => {
  await act(async () => root.render(createElement(WebChatView, { auth: { kind: 'web', csrfToken: 'csrf-token' } })))
  await act(async () => {
    const field = node.querySelector('textarea')!
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, '开始回复')
    field.dispatchEvent(new Event('input', { bubbles: true }))
  })
  const send = node.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!
  expect(send).not.toBeNull()
  await act(async () => send.click())
  expect(api.stream).toBeDefined()
  expect(button('新对话').disabled).toBe(false)
  await click('新对话')
  expect(node.textContent).not.toContain('A历史消息')
  expect(node.querySelector('[data-conversation-id="C"]')).not.toBeNull()
  expect(api.abort).not.toHaveBeenCalled()
  await act(async () => api.stream!.onEvent({ type: 'delta', text: 'A后台回答', conversationId: 'A', requestId: 'request-a', runId: 'run-a', sequence: 2 }))
  expect(node.textContent).not.toContain('A后台回答')
})


it('closes the history drawer by backdrop or close button without losing the draft', async () => {
  await input('保留我的草稿')
  await click('历史对话')
  await act(async () => node.querySelector<HTMLButtonElement>('[aria-label="关闭历史抽屉遮罩"]')!.click())
  expect(button('会话B')).toBeUndefined()
  expect(node.querySelector('textarea')!.value).toBe('保留我的草稿')
  await click('历史对话')
  await act(async () => node.querySelector<HTMLButtonElement>('[aria-label="关闭历史会话"]')!.click())
  expect(button('会话B')).toBeUndefined()
  expect(api.abort).not.toHaveBeenCalled()
})
