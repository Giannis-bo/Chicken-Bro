// @vitest-environment jsdom
import {act, createElement} from 'react'
import {createRoot, type Root} from 'react-dom/client'
import {afterEach, beforeEach, expect, it, vi} from 'vitest'
const getTree = vi.hoisted(() => vi.fn())
vi.mock('@wow-mini/api-client', () => ({wowApi: {poe2: {getTree}}}))
import Poe2PassiveTree from './Poe2PassiveTree'
const node = {id: 1, x: 0, y: 0, name: 'Strength', stats: ['+5 Strength'], type: 'Normal', ascendancy: '', allocated: true, allocation: 1, icon: '', size: 40}
const tree = {buildId: 'a', treeVersion: '0_5', engineVersion: 'test', inputSha256: 'a'.repeat(64), className: 'Mercenary', ascendancy: 'Gemling Legionnaire', secondaryAscendancy: '', nodes: [node, {...node, id: 2, ascendancy: 'Gemling Legionnaire', name: 'Adaptive Capability', allocation: 0}], edges: []}
const auth = {kind: 'web' as const, csrfToken: 'x'}
let container: HTMLDivElement, root: Root
beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
  vi.stubGlobal('ResizeObserver', class {observe() {} disconnect() {}})
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
  getTree.mockReset(); getTree.mockResolvedValue({payload: tree, fromFallback: false})
  container = document.createElement('div'); document.body.append(container); root = createRoot(container)
})
afterEach(async () => {await act(async () => root.unmount()); container.remove(); vi.restoreAllMocks(); vi.unstubAllGlobals()})
const render = async (buildId = 'a') => act(async () => root.render(createElement(Poe2PassiveTree, {auth, buildId})))
it('renders current ascendancy and node details without any calculation submission', async () => {
  await render()
  expect(container.textContent).toContain('天赋树')
  const asc = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.includes('升华'))!
  await act(async () => asc.click())
  const entry = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.includes('Adaptive Capability'))!
  await act(async () => entry.click())
  expect(container.querySelector('[aria-label="节点详情"]')?.textContent).toContain('Adaptive Capability')
  expect(getTree).toHaveBeenCalledWith('a', auth, undefined)
})
it('does not display a late response belonging to the previously selected build', async () => {
  let resolve!: (value: unknown) => void
  getTree.mockImplementationOnce(() => new Promise(done => {resolve = done}))
  await render('a')
  getTree.mockResolvedValueOnce({payload: {...tree, buildId: 'b', nodes: [{...node, name: 'new-build'}]}, fromFallback: false})
  await render('b')
  await act(async () => resolve({payload: tree, fromFallback: false}))
  expect(container.textContent).toContain('new-build')
  expect(container.textContent).not.toContain('Adaptive Capability')
})
it('offers retry when the tree cannot be loaded', async () => {
  getTree.mockResolvedValueOnce({fromFallback: true, problemCode: 'POE2_TREE_VERSION_MISMATCH'})
  await render()
  expect(container.textContent).toContain('版本')
  expect(Array.from(container.querySelectorAll('button')).some(b => b.textContent === '重试加载')).toBe(true)
})
