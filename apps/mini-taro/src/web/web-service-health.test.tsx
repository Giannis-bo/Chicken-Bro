// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.hoisted(() => vi.fn())
vi.mock('@wow-mini/api-client', () => ({
  wowApi: { transport: { request } },
  apiV2Path: (path: string) => `/test/api/v2${path}`,
}))
import WebServiceHealth from './WebServiceHealth'

describe('Web service health', () => {
  let container: HTMLDivElement
  let root: Root
  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    vi.useFakeTimers()
    request.mockReset()
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })
  async function render() {
    await act(async () => root.render(createElement(WebServiceHealth)))
  }
  it('checks the active API environment and never reports fallback as healthy', async () => {
    request.mockResolvedValueOnce({ payload: { status: 'ready' }, fromFallback: false })
    await render()
    expect(request).toHaveBeenCalledWith('/test/api/v2/health/readiness', expect.objectContaining({
      auth: { kind: 'public' }, baseUrl: 'web-auth', timeoutMs: 8000,
    }))
    expect(container.querySelector('[role="status"]')?.getAttribute('aria-label')).toBe('服务正常')
    request.mockResolvedValueOnce({ payload: { status: 'ready' }, fromFallback: true })
    await act(async () => vi.advanceTimersByTimeAsync(60_000))
    expect(container.querySelector('[role="status"]')?.getAttribute('aria-label')).toBe('服务连接异常')
  })
  it.each([
    ['partial', '部分服务不可用'], ['blocked', '服务不可用'], ['unexpected', '服务连接异常'],
  ])('shows %s without a false green light', async (status, label) => {
    request.mockResolvedValue({ payload: { status }, fromFallback: false })
    await render()
    expect(container.querySelector('[role="status"]')?.getAttribute('aria-label')).toBe(label)
  })
  it('shows a pending state and cleans up polling after unmount', async () => {
    request.mockReturnValue(new Promise(() => undefined))
    await render()
    expect(container.querySelector('[role="status"]')?.getAttribute('aria-label')).toBe('正在检查服务')
    await act(async () => root.unmount())
    root = createRoot(container)
    await act(async () => vi.advanceTimersByTimeAsync(120_000))
    expect(request).toHaveBeenCalledTimes(1)
  })
})
