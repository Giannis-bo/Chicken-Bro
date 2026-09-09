// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const api = vi.hoisted(() => ({ imageCapabilities: vi.fn(), uploadImage: vi.fn(), removeImage: vi.fn(), choose: vi.fn() }))
vi.mock('@wow-mini/api-client', () => ({ wowApi: { chat: api } }))
vi.mock('./image-picker', () => ({ chooseChatImages: api.choose }))
import { useChatImages } from './use-chat-images'
let value: ReturnType<typeof useChatImages>
let root: Root
let node: HTMLDivElement
const image = {id: 'image-one', mimeType: 'image/png', width: 2, height: 2}
const success = (payload: unknown) => ({payload, fromFallback: false})
function Probe() { value = useChatImages(() => ({kind: 'web', csrfToken: 'csrf'}), true); return null }
beforeEach(async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  vi.resetAllMocks()
  api.imageCapabilities.mockResolvedValue(success({enabled: true, maxImages: 3, maxBytes: 5242880}))
  api.choose.mockResolvedValue(['data:image/png;base64,aGVsbG8='])
  api.removeImage.mockResolvedValue(success({deleted: true}))
  node = document.createElement('div'); root = createRoot(node)
  await act(async () => root.render(createElement(Probe)))
})
afterEach(async () => { await act(async () => root.unmount()); vi.unstubAllGlobals() })
it('retains failed upload and retries using the same idempotency key', async () => {
  api.uploadImage.mockResolvedValueOnce({fromFallback: true, error: '离线'}).mockResolvedValueOnce(success(image))
  await act(async () => value.choose())
  expect(value.pending).toBe(true)
  expect(value.items[0]?.status).toBe('failed')
  await act(async () => value.retry(value.items[0]!.key))
  expect(value.pending).toBe(false)
  expect(value.images).toEqual([image])
  expect(api.uploadImage.mock.calls[0]?.[1]).toEqual(api.uploadImage.mock.calls[1]?.[1])
})
it('keeps sending disabled until upload finishes and cleans a removed in-flight result', async () => {
  let finish!: (value: unknown) => void
  api.uploadImage.mockReturnValue(new Promise(resolve => { finish = resolve }))
  await act(async () => value.choose())
  expect(value.pending).toBe(true)
  await act(async () => value.remove(value.items[0]!.key))
  await act(async () => finish(success(image)))
  expect(value.images).toEqual([])
  expect(api.removeImage).toHaveBeenCalledWith('image-one', {auth: {kind: 'web', csrfToken: 'csrf'}})
})
it('hides and blocks the picker when capability is disabled', async () => {
  await act(async () => root.unmount())
  root = createRoot(node)
  api.imageCapabilities.mockResolvedValue(success({enabled: false}))
  await act(async () => root.render(createElement(Probe)))
  expect(value.enabled).toBe(false)
  await act(async () => value.choose())
  expect(api.choose).not.toHaveBeenCalled()
})
