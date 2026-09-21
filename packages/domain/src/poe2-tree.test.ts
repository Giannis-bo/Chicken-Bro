import {expect, it} from 'vitest'
import {isPoe2Tree, treeNodesForView, nodeIsAllocated} from './poe2-tree'

const node = {id: 1, x: 0, y: 10, name: 'Strength', stats: ['+5 Strength'], type: 'Normal', ascendancy: '', allocated: true, allocation: 1, icon: '', size: 40}
const tree = {buildId: 'b', engineVersion: 'pinned', inputSha256: 'a'.repeat(64), treeVersion: '0_5', className: 'Mercenary', ascendancy: 'Gemling Legionnaire', secondaryAscendancy: '', nodes: [node], edges: []}
it('rejects invalid geometry and unknown allocation modes at the transport boundary', () => {
  expect(isPoe2Tree(tree)).toBe(true)
  expect(isPoe2Tree({...tree, nodes: [{...node, x: Infinity}]})).toBe(false)
  expect(isPoe2Tree({...tree, nodes: [{...node, allocation: 3}]})).toBe(false)
  expect(isPoe2Tree({...tree, edges: [{from: 1, to: 999}]})).toBe(false)
})
it('filters ascendancy without confusing weapon groups or dropping common points', () => {
  const asc = {...node, id: 2, ascendancy: 'Gemling Legionnaire', allocation: 0}
  expect(treeNodesForView({...tree, nodes: [node, asc]}, '')).toEqual([node])
  expect(treeNodesForView({...tree, nodes: [node, asc]}, 'Gemling Legionnaire')).toEqual([asc])
  expect(nodeIsAllocated(node, 2)).toBe(false)
  expect(nodeIsAllocated(node, 1)).toBe(true)
  expect(nodeIsAllocated(asc, 2)).toBe(true)
})
