// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ get: vi.fn(), set: vi.fn(), compress: vi.fn(), read: vi.fn(), chosen: undefined as undefined | ((event: {detail: {avatarUrl: string}}) => void) }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { avatar: api } }))
vi.mock('@tarojs/taro', () => ({ useDidShow: () => undefined, default: { compressImage: api.compress, getFileSystemManager: () => ({ readFile: api.read }) } }))
vi.mock('@tarojs/components', async () => {
  const { createElement: h } = await import('react')
  return { View: (p: Record<string, unknown>) => h('div', {}, p['children'] as never), Text: (p: Record<string, unknown>) => h('span', {}, p['children'] as never),
    Image: (p: Record<string, unknown>) => h('img', {src: p['src'] as string}),
    Button: (p: Record<string, unknown>) => { api.chosen = p['onChooseAvatar'] as typeof api.chosen; return h('button', {disabled: !!p['disabled']}, p['children'] as never) } }
})
import MiniAccountAvatar from './MiniAccountAvatar'
const image = 'data:image/png;base64,iVBORw0KGgoAAA=='
const ok = (avatarDataUrl: string | null) => ({ fromFallback: false, payload: {avatarDataUrl} })
let node: HTMLDivElement
let root: Root
beforeEach(() => {
  Object.assign(globalThis, {IS_REACT_ACT_ENVIRONMENT: true})
  vi.resetAllMocks()
  api.get.mockResolvedValue(ok(null))
  api.set.mockResolvedValue(ok(image))
  api.compress.mockResolvedValue({tempFilePath: 'wxfile://compressed'})
  api.read.mockImplementation(({success}) => success({data: 'iVBORw0KGgoAAA=='}))
  node = document.createElement('div'); document.body.append(node); root = createRoot(node)
})
afterEach(async () => { await act(async () => root.unmount()); node.remove() })
it('saves chosen bytes then displays shared avatar; never uploads temporary path', async () => {
  await act(async () => root.render(createElement(MiniAccountAvatar, {accessToken: 'account-a'})))
  expect(node.textContent).toContain('设置头像')
  await act(async () => api.chosen?.({detail: {avatarUrl: 'wxfile://chosen'}}))
  expect(api.set).toHaveBeenCalledWith(image, {kind: 'mini', accessToken: 'account-a'})
  expect(node.querySelector('img')?.src).toBe(image)
  expect(node.textContent).toContain('已保存，Web 也会显示')
})
it('cancellation and failed upload preserve previous avatar; failure can retry', async () => {
  api.get.mockResolvedValue(ok(image))
  await act(async () => root.render(createElement(MiniAccountAvatar, {accessToken: 'account-a'})))
  await act(async () => api.chosen?.({detail: {avatarUrl: ''}}))
  expect(api.set).not.toHaveBeenCalled()
  api.set.mockResolvedValueOnce({fromFallback: true, payload: {avatarDataUrl: null}})
  await act(async () => api.chosen?.({detail: {avatarUrl: 'wxfile://chosen'}}))
  expect(node.querySelector('img')?.src).toBe(image)
  expect(node.textContent).toContain('头像未保存，请重试')
  expect(node.querySelector('button')?.disabled).toBe(false)
  await act(async () => api.chosen?.({detail: {avatarUrl: 'wxfile://chosen'}}))
  expect(node.textContent).toContain('已保存')
})
it('unmount during compression cannot upload for a former account', async () => {
  let finish: ((value: {tempFilePath: string}) => void) | undefined
  api.compress.mockImplementation(() => new Promise(resolve => {finish = resolve}))
  await act(async () => root.render(createElement(MiniAccountAvatar, {accessToken: 'account-a'})))
  await act(async () => api.chosen?.({detail: {avatarUrl: 'wxfile://chosen'}}))
  await act(async () => root.render(null))
  await act(async () => finish?.({tempFilePath: 'wxfile://compressed'}))
  expect(api.set).not.toHaveBeenCalled()
})

it('icon-only mode restores the saved avatar without a new choice or visible setup copy', async () => {
  api.get.mockResolvedValue(ok(image))
  await act(async () => root.render(createElement(MiniAccountAvatar, {accessToken: 'account-a', iconOnly: true})))
  expect(node.querySelector('img')?.src).toBe(image)
  expect(node.textContent).not.toMatch(/设置头像|更换头像/)
  expect(api.set).not.toHaveBeenCalled()
  await act(async () => api.chosen?.({detail: {avatarUrl: 'wxfile://chosen'}}))
  expect(node.textContent).not.toContain('已保存，Web 也会显示')
})
