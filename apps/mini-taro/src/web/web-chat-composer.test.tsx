// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), create: vi.fn(), streamMessage: vi.fn(), imageCapabilities: vi.fn(), uploadImage: vi.fn(), getImage: vi.fn(), removeImage: vi.fn(), choose: vi.fn() }))
vi.mock('../features/chat/image-picker', async importOriginal => ({ ...await importOriginal<Record<string, unknown>>(), chooseChatImages: api.choose }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { chat: api } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => (props: Record<string, unknown>) => element(tag,
    Object.fromEntries(Object.entries(props).filter(([key]) =>
      ['children', 'onClick', 'disabled', 'className', 'id'].includes(key) || key.startsWith('data-') || key.startsWith('aria-'))))
  return { Image: host('img'), View: host('div'), Text: host('span'), Button: host('button'), ScrollView: host('div'),
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
    api.create.mockReset()
    const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
    const conversation = { id: 'chat-one', title: 'Test', updatedAt: '2026-09-05' }
    api.imageCapabilities.mockResolvedValue(success({enabled: true, maxImages: 3, maxBytes: 5242880}))
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

  async function firstVisit() {
    api.list.mockResolvedValue({ payload: { items: [], nextCursor: null }, fromFallback: false, error: '' })
    await act(async () => root.render(null))
    await act(async () => root.render(createElement(WebChatView, {
      auth: { kind: 'web', csrfToken: 'test-csrf' },
    })))
  }

  it.each(['click', 'enter'])('sends on the first visit without creating a conversation manually via %s', async method => {
    await firstVisit()
    expect(api.create).not.toHaveBeenCalled()
    const fresh = { id: 'chat-first', title: '新对话', updatedAt: '2026-09-09' }
    api.create.mockResolvedValue({ payload: fresh, fromFallback: false, error: '' })
    api.get.mockResolvedValue({ payload: { ...fresh, messages: [] }, fromFallback: false, error: '' })
    await draft('首次提问')
    const send = container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!
    expect(send.disabled).toBe(false)
    if (method === 'click') await act(async () => send.click())
    else await enter()
    expect(api.create).toHaveBeenCalledTimes(1)
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(api.streamMessage.mock.calls[0]?.[0]).toBe('chat-first')
    expect(api.streamMessage.mock.calls[0]?.[1].content).toBe('首次提问')
  })

  it.each([false, true])('does not duplicate first sends during creation or send after unmount=%s', async unmount => {
    await firstVisit()
    const fresh = { id: 'chat-first', title: '新对话', updatedAt: '2026-09-09' }
    let finish!: (result: unknown) => void
    api.create.mockReturnValue(new Promise(resolve => { finish = resolve }))
    api.get.mockResolvedValue({ payload: { ...fresh, messages: [] }, fromFallback: false, error: '' })
    await draft('首次提问')
    await enter()
    await enter()
    expect(api.create).toHaveBeenCalledTimes(1)
    expect(api.streamMessage).not.toHaveBeenCalled()
    if (unmount) await act(async () => root.render(null))
    await act(async () => finish({ payload: fresh, fromFallback: false, error: '' }))
    expect(api.streamMessage).toHaveBeenCalledTimes(unmount ? 0 : 1)
  })

  it('retains the first draft on creation failure and reuses the creation key on retry', async () => {
    await firstVisit()
    api.create.mockResolvedValueOnce({ payload: null, fromFallback: true, error: '创建失败' })
    await draft('不要丢掉这条消息')
    await enter()
    expect(api.create).toHaveBeenCalledTimes(1)
    expect(api.streamMessage).not.toHaveBeenCalled()
    expect(input().value).toBe('不要丢掉这条消息')
    const fresh = { id: 'chat-first', title: '新对话', updatedAt: '2026-09-09' }
    api.create.mockResolvedValue({ payload: fresh, fromFallback: false, error: '' })
    api.get.mockResolvedValue({ payload: { ...fresh, messages: [] }, fromFallback: false, error: '' })
    await enter()
    expect(api.create).toHaveBeenCalledTimes(2)
    expect(api.create.mock.calls[0]?.[1].idempotencyKey).toBe(api.create.mock.calls[1]?.[1].idempotencyKey)
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
  })

  it('shows the welcome screen after creating a conversation and hides it on the first send', async () => {
    const success = (payload: unknown) => ({ payload, fromFallback: false, error: '' })
    const existing = { id: 'chat-one', title: 'Test', updatedAt: '2026-09-05', messages: [
      { id: 'old-message', role: 'user', content: '已有消息', createdAt: '2026-09-05' },
    ] }
    api.get.mockResolvedValue(success(existing))
    const history = Array.from(container.querySelectorAll('button')).find(button => button.textContent?.includes('Test'))!
    await act(async () => history.click())
    expect(container.textContent).toContain('已有消息')
    expect(container.textContent).not.toContain('准备好了，随时开始')

    const fresh = { id: 'chat-new', title: '新对话', updatedAt: '2026-09-08' }
    api.create.mockResolvedValue(success(fresh))
    api.get.mockResolvedValue(success({ ...fresh, messages: [] }))
    const create = Array.from(container.querySelectorAll('button')).find(button => button.textContent?.includes('+ 新对话'))!
    await act(async () => create.click())
    expect(container.textContent).toContain('准备好了，随时开始')
    expect(container.querySelector('[data-empty="true"]')).not.toBeNull()
    expect(container.textContent).not.toContain('已有消息')
    expect(container.textContent).not.toContain('回到最新')
    const prompt = Array.from(container.querySelectorAll('button')).find(button => button.textContent === '帮我分析WCL的数据')!
    await act(async () => prompt.click())
    expect(input().value).toBe('帮我分析WCL的数据')
    await enter()
    expect(container.textContent).not.toContain('准备好了，随时开始')
    expect(container.querySelector('[data-empty="true"]')).toBeNull()
    expect(container.querySelector('[aria-label="正在回复"]')).not.toBeNull()
  })

  it('streams an expandable summary, collapses at the answer, and restores server timing', async () => {
    await draft('分析日志')
    await enter()
    const onEvent = api.streamMessage.mock.calls[0]?.[2].onEvent
    const base = { requestId: 'request', runId: 'run', conversationId: 'chat-one' }
    await act(async () => {
      onEvent({ ...base, sequence: 1, type: 'started' })
      onEvent({ ...base, sequence: 2, type: 'progress', text: '正在核对日志' })
    })
    expect(container.textContent).toContain('正在核对日志')
    await act(async () => onEvent({ ...base, sequence: 3, type: 'delta', text: '技能覆盖不足' }))
    expect(container.textContent).not.toContain('正在核对日志')
    expect(container.textContent).toContain('技能覆盖不足')
    api.get.mockResolvedValue({ fromFallback: false, error: '', payload: {
      id: 'chat-one', messages: [{ id: 'reply', role: 'assistant', content: '技能覆盖不足',
        createdAt: '2026-09-07T06:32:00Z', progress: { text: '正在核对日志', status: 'completed',
          completedAt: '2026-09-07T06:32:00Z', durationMs: 18000 } }],
    } })
    await act(async () => onEvent({ ...base, sequence: 4, type: 'completed', text: '技能覆盖不足',
      completedAt: '2026-09-07T06:32:00Z', durationMs: 18000 }))
    expect(container.textContent).toContain('用时 0 分 18 秒')
    expect(container.textContent).not.toContain('正在核对日志')
    const toggle = Array.from(container.querySelectorAll('button')).find((button) => button.textContent?.includes('思考摘要'))!
    await act(async () => toggle.click())
    expect(container.textContent).toContain('正在核对日志')
  })

  it('sends once on Enter and keeps the next draft while a reply is pending', async () => {
    await draft('你好')
    expect((await enter()).defaultPrevented).toBe(true)
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(api.streamMessage.mock.calls[0]?.[1].content).toBe('你好')
    expect(input().value).toBe('你好')
    await act(async () => api.streamMessage.mock.calls[0]?.[2].onEvent({
      type: 'started', conversationId: 'chat-one', requestId: 'request', runId: 'run', sequence: 1,
    }))
    expect(input().value).toBe('')
    await draft('下一条')
    await enter()
    expect(api.streamMessage).toHaveBeenCalledTimes(1)
    expect(input().value).toBe('下一条')
  })

  it('waits for image upload, supports image-only sends, and retains images on admission rejection', async () => {
    let finish!: (value: unknown) => void
    api.choose.mockResolvedValue(['data:image/png;base64,aGVsbG8='])
    api.uploadImage.mockReturnValue(new Promise(resolve => {finish = resolve}))
    const add = container.querySelector<HTMLButtonElement>('[aria-label="添加图片"]')!
    await act(async () => add.click())
    expect(container.textContent).toContain('上传中')
    expect(container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!.disabled).toBe(true)
    const image = {id: 'image-one', mimeType: 'image/png', width: 2, height: 2}
    await act(async () => finish({fromFallback: false, payload: image}))
    expect(container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!.disabled).toBe(false)
    api.getImage.mockResolvedValue({fromFallback: false, payload: {dataUrl: 'data:image/png;base64,aGVsbG8='}})
    await enter()
    expect(api.streamMessage.mock.calls[0]?.[1]).toMatchObject({content: '', imageIds: ['image-one']})
    await act(async () => api.streamMessage.mock.calls[0]?.[2].onFailure('CHAT_ACCOUNT_BUSY'))
    expect(container.querySelector('[aria-label="移除图片"]')).not.toBeNull()
    expect(container.textContent).toContain('鸡哥正在回复你的另一条消息')
    expect(api.removeImage).not.toHaveBeenCalled()
  })

  async function transfer(kind: 'paste' | 'drop', files: File[], text = '') {
    const event = new Event(kind, { bubbles: true, cancelable: true })
    const data = { files, items: files.map(file => ({kind: 'file', type: file.type, getAsFile: () => file})), types: files.length ? ['Files'] : ['text/plain'], getData: () => text }
    Object.defineProperty(event, kind === 'paste' ? 'clipboardData' : 'dataTransfer', { value: data })
    await act(async () => { input().dispatchEvent(event); await new Promise(resolve => setTimeout(resolve, 20)) })
    return event
  }
  it.each(['paste', 'drop'] as const)('accepts an image by %s into the composer and sends its uploaded ID', async kind => {
    api.uploadImage.mockResolvedValue({fromFallback: false, payload: {id: 'direct-image', mimeType: 'image/png', width: 2, height: 2}})
    await draft('看看这张图')
    const event = await transfer(kind, [new File(['pixels'], 'screenshot.png', {type: 'image/png'})])
    expect(event.defaultPrevented).toBe(true)
    const composer = input().closest('[aria-label="消息输入区"]')!
    expect(composer.querySelector('[aria-label="移除图片"]')).not.toBeNull()
    expect(input().value).toBe('看看这张图')
    await enter()
    expect(api.streamMessage.mock.calls[0]?.[1]).toMatchObject({content: '看看这张图', imageIds: ['direct-image']})
  })
  it('retries a failed pasted image with the same key, then removes it', async () => {
    api.uploadImage.mockResolvedValueOnce({fromFallback: true, error: '网络暂不可用'})
      .mockResolvedValueOnce({fromFallback: false, payload: {id: 'retry-image', mimeType: 'image/png', width: 2, height: 2}})
    api.removeImage.mockResolvedValue({fromFallback: false, payload: {deleted: true}})
    await transfer('paste', [new File(['pixels'], 'screenshot.png', {type: 'image/png'})])
    expect(container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!.disabled).toBe(true)
    await act(async () => Array.from(container.querySelectorAll('button')).find(button => button.textContent === '重试上传')!.click())
    expect(api.uploadImage.mock.calls[0]?.[1].idempotencyKey).toBe(api.uploadImage.mock.calls[1]?.[1].idempotencyKey)
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!.disabled).toBe(false)
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="移除图片"]')!.click())
    expect(container.querySelector('[aria-label="移除图片"]')).toBeNull()
    expect(container.querySelector<HTMLButtonElement>('[aria-label="发送消息"]')!.disabled).toBe(true)
  })
  it('keeps accompanying clipboard text at the current selection', async () => {
    api.uploadImage.mockResolvedValue({fromFallback: false, payload: {id: 'mixed-image', mimeType: 'image/png', width: 2, height: 2}})
    await draft('前后')
    input().setSelectionRange(1, 1)
    await transfer('paste', [new File(['pixels'], 'screenshot.png', {type: 'image/png'})], '截图')
    expect(input().value).toBe('前截图后')
  })

  it('does not intercept text-only paste', async () => {
    expect((await transfer('paste', [], '普通文字')).defaultPrevented).toBe(false)
    expect(api.uploadImage).not.toHaveBeenCalled()
  })
  it.each([
    [new File(['x'], 'unsupported.gif', {type: 'image/gif'})],
    [new File([new Uint8Array(5242881)], 'large.png', {type: 'image/png'})],
    Array.from({length: 4}, (_, i) => new File(['x'], `${i}.png`, {type: 'image/png'})),
  ])('rejects invalid dropped images without uploading or clearing text: %j', async (...files) => {
    await draft('保留文字')
    await transfer('drop', files)
    expect(api.uploadImage).not.toHaveBeenCalled()
    expect(container.querySelector('[role="alert"]')?.textContent).toMatch(/PNG|三张|5 MiB/)
    expect(input().value).toBe('保留文字')
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
