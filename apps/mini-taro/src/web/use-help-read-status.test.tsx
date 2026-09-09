// @vitest-environment jsdom
import { act, createElement } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { helpReadKey, useHelpReadStatus, type HelpRevisions } from './use-help-read-status'

let root: Root
let container: HTMLDivElement
let status: ReturnType<typeof useHelpReadStatus>
const revisions = { faq: 'faq-content-v1', changelog: 'release-content-v1' }
function Harness({ versions }: { versions: HelpRevisions }) {
  status = useHelpReadStatus(versions)
  return null
}
const render = (versions = revisions) => act(async () => root.render(createElement(Harness, { versions })))
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  localStorage.clear()
  container = document.createElement('div')
  document.body.append(container)
  root = createRoot(container)
})
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
it('tracks sections independently and retains reads after remount', async () => {
  await render()
  expect(status.unread).toEqual({ faq: true, changelog: true })
  await act(async () => status.markRead('faq'))
  expect(status.unread).toEqual({ faq: false, changelog: true })
  await act(async () => status.markRead('changelog'))
  await act(async () => root.unmount())
  root = createRoot(container)
  await render()
  expect(status.unread).toEqual({ faq: false, changelog: false })
})
it('shows only changed content again, including same-day edits', async () => {
  await render()
  await act(async () => { status.markRead('faq'); status.markRead('changelog') })
  await render({ ...revisions, faq: 'faq-content-v2' })
  expect(status.unread).toEqual({ faq: true, changelog: false })
  await act(async () => status.markRead('faq'))
  await render({ faq: 'faq-content-v2', changelog: 'release-content-v2' })
  expect(status.unread).toEqual({ faq: false, changelog: true })
})
it('syncs another tab and handles cleared or invalid stored values', async () => {
  localStorage.setItem(helpReadKey('faq'), 'invalid')
  await render()
  expect(status.unread.faq).toBe(true)
  await act(async () => {
    localStorage.setItem(helpReadKey('faq'), revisions.faq)
    window.dispatchEvent(new StorageEvent('storage', { key: helpReadKey('faq'), storageArea: localStorage }))
  })
  expect(status.unread).toEqual({ faq: false, changelog: true })
  await act(async () => { localStorage.clear(); window.dispatchEvent(new StorageEvent('storage', { key: null, storageArea: localStorage })) })
  expect(status.unread.faq).toBe(true)
})
it('still clears the current page indicator when storage is unavailable', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota') })
  await render()
  await act(async () => status.markRead('faq'))
  expect(status.unread).toEqual({ faq: false, changelog: true })
})
