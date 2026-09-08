// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ConversationSummary } from '@wow-mini/domain'
import WebConversationHistory from './WebConversationHistory'

const conversation = (id: string, updatedAt: string): ConversationSummary => ({
  id, title: `会话 ${id}`, status: 'active', createdAt: updatedAt, updatedAt,
})
describe('Web history day groups', () => {
  let container: HTMLDivElement
  let root: Root
  const onDelete = vi.fn(async () => null as string | null)
  const onOpen = vi.fn()
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    onOpen.mockClear()
    onDelete.mockClear()
    HTMLDialogElement.prototype.showModal = function () { this.open = true }
    HTMLDialogElement.prototype.close = function () { this.open = false }
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.unstubAllGlobals()
  })
  async function render(conversations: ConversationSummary[], activeId = '', hasMore = false) {
    await act(async () => root.render(createElement(WebConversationHistory, { conversations, activeId, hasMore, onOpen, onDelete })))
  }
  const groups = () => Array.from(container.querySelectorAll<HTMLButtonElement>('button[aria-expanded]'))

  it('requires confirmation and cancel does not delete or open the conversation', async () => {
    await render([conversation('one', '2026-09-05T12:00:00+08:00')])
    const trash = container.querySelector<HTMLButtonElement>('[title="删除会话"]')!
    expect(trash).not.toBeNull()
    await act(async () => trash.click())
    expect(onOpen).not.toHaveBeenCalled()
    expect(onDelete).not.toHaveBeenCalled()
    const dialog = container.querySelector<HTMLDialogElement>('dialog')!
    expect(dialog.open).toBe(true)
    const buttons = Array.from(dialog.querySelectorAll('button'))
    await act(async () => buttons.find(b => b.textContent === '取消')!.click())
    expect(onDelete).not.toHaveBeenCalled()
    await act(async () => trash.click())
    await act(async () => Array.from(container.querySelectorAll('dialog button')).find(b => b.textContent === '删除')!.dispatchEvent(new MouseEvent('click', { bubbles: true })))
    expect(onDelete).toHaveBeenCalledExactlyOnceWith('one')
  })

  it('groups offset timestamps in Beijing time, sorts recent first and displays only HH:mm', async () => {
    await render([
      conversation('old', '2026-09-04T13:00:00+08:00'),
      conversation('early', '2026-09-04T16:05:00Z'),
      conversation('late', '2026-09-05T20:14:38.553876+08:00'),
    ])
    expect(groups().map(e => e.textContent)).toEqual(['2026-09-05 · 2 个会话', '2026-09-04 · 1 个会话'])
    expect(groups().map(e => e.getAttribute('aria-expanded'))).toEqual(['true', 'false'])
    expect(Array.from(container.querySelectorAll('time')).map(e => e.textContent)).toEqual(['20:14', '00:05'])
    expect(container.textContent).not.toContain('553876')
    expect(container.textContent).not.toContain('会话 old')
    expect(Array.from(container.querySelectorAll('[data-conversation-id]')).map(e => e.getAttribute('data-conversation-id')))
      .toEqual(['late', 'early'])
  })

  it('toggles each group with accessible buttons without opening a conversation', async () => {
    await render([conversation('one', '2026-09-05T12:00:00+08:00')])
    const button = groups()[0]!
    await act(async () => button.click())
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('[data-conversation-id]')).toBeNull()
    expect(onOpen).not.toHaveBeenCalled()
    await act(async () => button.click())
    expect(container.querySelector(`#${button.getAttribute('aria-controls')}`)).not.toBeNull()
    await act(async () => container.querySelector<HTMLButtonElement>('[data-conversation-id]')!.click())
    expect(onOpen).toHaveBeenCalledWith('one')
  })

  it('merges loaded pages, keeps a collapsed group closed and labels partial counts', async () => {
    const first = conversation('one', '2026-09-05T20:00:00+08:00')
    await render([first], '', true)
    expect(groups()[0]!.textContent).toBe('2026-09-05 · 已加载 1 个')
    await act(async () => groups()[0]!.click())
    await render([first, conversation('two', '2026-09-05T12:00:00+08:00'),
      conversation('old', '2026-09-04T12:00:00+08:00')], '', true)
    expect(groups().map(e => e.textContent)).toEqual(['2026-09-05 · 2 个会话', '2026-09-04 · 已加载 1 个'])
    expect(groups()[0]!.getAttribute('aria-expanded')).toBe('false')
  })

  it('reveals a newly selected or moved active conversation without undoing a manual collapse', async () => {
    const one = conversation('one', '2026-09-05T12:00:00+08:00')
    const old = conversation('old', '2026-09-04T12:00:00+08:00')
    await render([one, old], 'one')
    await render([one, old], 'old')
    expect(container.querySelector('[data-conversation-id="old"]')?.getAttribute('data-active')).toBe('true')
    await act(async () => groups()[1]!.click())
    await render([one, { ...old, title: '标题更新' }], 'old')
    expect(groups()[1]!.getAttribute('aria-expanded')).toBe('false')
    await render([one, { ...old, updatedAt: '2026-09-06T00:01:00+08:00' }], 'old')
    expect(groups()[0]!.textContent).toBe('2026-09-06 · 1 个会话')
    expect(container.querySelector('[data-conversation-id="old"]')).not.toBeNull()
  })
})
