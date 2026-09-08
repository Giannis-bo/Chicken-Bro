// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
const clipboard = vi.hoisted(() => vi.fn())
vi.mock('@tarojs/taro', () => ({ default: { setClipboardData: clipboard } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: element } = await import('react')
  const host = (tag: string) => ({ selectable, ...props }: Record<string, unknown>) => element(tag, { ...props, ...(selectable ? { 'data-selectable': 'true' } : {}) })
  return { Button: host('button'), Text: host('span'), View: host('div') }
})
import MiniSimcTaskId from '../../components/MiniSimcTaskId'
it('copies the full ID without triggering parent navigation and exposes success and failure', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  const container = document.createElement('div'); document.body.append(container)
  const root = createRoot(container)
  const navigate = vi.fn()
  const id = '2110bcab-8641-4d0d-9374-40bf17534680'
  try {
    await act(async () => root.render(createElement('div', { onClick: navigate }, createElement(MiniSimcTaskId, { id }))))
    expect(container.querySelector('[data-selectable]')?.textContent).toContain(id)
    clipboard.mockResolvedValueOnce({})
    await act(async () => container.querySelector('button')!.click())
    expect(clipboard).toHaveBeenCalledWith({ data: id })
    expect(navigate).not.toHaveBeenCalled()
    expect(container.textContent).toContain('已复制任务 ID')
    clipboard.mockRejectedValueOnce(new Error('denied'))
    await act(async () => container.querySelector('button')!.click())
    expect(container.textContent).toContain('复制失败，请长按任务 ID 复制')
  } finally { await act(async () => root.unmount()); container.remove(); vi.unstubAllGlobals() }
})
