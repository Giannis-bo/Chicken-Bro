import {expect, it} from 'vitest'
import {fitTree, hitNode, zoomAt, nodeRadius} from './poe2-tree-canvas'
const node = {id: 1, x: 100, y: 100, name: 'n', stats: [], type: 'Normal', ascendancy: '', allocated: true, allocation: 0, icon: '', size: 40}
it('fits a single point and keeps the zoom anchor under the cursor', () => {
  const view = fitTree([node], 800, 500)
  expect(Number.isFinite(view.scale)).toBe(true)
  const next = zoomAt(view, 2, 200, 100)
  expect((200 - next.x) / next.scale).toBeCloseTo((200 - view.x) / view.scale)
  expect((100 - next.y) / next.scale).toBeCloseTo((100 - view.y) / view.scale)
})
it('selects the nearest visible node and does not select distant nodes', () => {
  expect(hitNode([node], {x: 0, y: 0, scale: 1}, 102, 104)?.id).toBe(1)
  expect(hitNode([node], {x: 0, y: 0, scale: 1}, 500, 500)).toBeUndefined()
})
it('keeps ascendancy icons readable and clickable when fitting the full tree on a phone', () => {
  const asc = {...node, type: 'Notable', ascendancy: 'Gemling Legionnaire'}
  expect(nodeRadius(asc, .02)).toBeGreaterThanOrEqual(16)
  expect(hitNode([asc], {x: 0, y: 0, scale: .02}, 16, 2)?.id).toBe(1)
})
