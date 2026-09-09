// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { expect, it, vi } from 'vitest'
const fs = vi.hoisted(() => ({ readdir: vi.fn(), unlink: vi.fn(), writeFile: vi.fn() }))
vi.mock('@tarojs/taro', () => ({ default: {env: {USER_DATA_PATH: '/sandbox'}, getFileSystemManager: () => fs} }))
import { useImageSource } from './use-image-source.weapp'
it('passes only a temporary path to Mini rendering and deletes it after unmount', async () => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  fs.readdir.mockImplementation(options => options.success({files: ['chickenbro-preview-old.png', 'unrelated.png']}))
  fs.unlink.mockImplementation(options => options.complete?.())
  fs.writeFile.mockImplementation(options => options.success())
  let result!: ReturnType<typeof useImageSource>
  function Probe() { result = useImageSource('data:image/png;base64,aGVsbG8='); return null }
  const root = createRoot(document.createElement('div'))
  await act(async () => root.render(createElement(Probe)))
  expect(result.source).toMatch(/^\/sandbox\/chickenbro-preview-.*\.png$/u)
  expect(result.source).not.toContain('base64')
  expect(fs.writeFile.mock.calls[0]?.[0]).toMatchObject({data: 'aGVsbG8=', encoding: 'base64'})
  expect(fs.unlink.mock.calls.some(call => call[0].filePath === '/sandbox/unrelated.png')).toBe(false)
  const path = result.source
  await act(async () => root.unmount())
  expect(fs.unlink.mock.calls.some(call => call[0].filePath === path)).toBe(true)
  vi.unstubAllGlobals()
})
