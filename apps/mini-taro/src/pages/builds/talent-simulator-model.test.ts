import { describe, expect, it } from 'vitest'

import type { TalentNode } from '@wow-mini/domain'

import {
  buildTalentGraph,
  cycleTalentRank,
  initialTalentRanks,
  talentPoints,
} from './talent-simulator-model'

const nodes: readonly TalentNode[] = [
  {
    id: 'root',
    name: '根节点',
    treeKey: 'class',
    row: 1,
    column: 4,
    maxRank: 1,
    ranks: 1,
    requiredPoints: 0,
    granted: true,
  },
  {
    id: 'child',
    name: '子节点',
    treeKey: 'class',
    row: 2,
    column: 3,
    maxRank: 2,
    ranks: 0,
    requiredPoints: 1,
    prerequisiteIds: ['root'],
    parentMode: 'all',
  },
  {
    id: 'locked',
    name: '锁定节点',
    treeKey: 'class',
    row: 3,
    column: 2,
    maxRank: 1,
    ranks: 0,
    requiredPoints: 4,
    prerequisiteIds: ['child'],
  },
]

describe('talent simulator target model', () => {
  it('retains real coordinates and prerequisite edges', () => {
    const ranks = initialTalentRanks(nodes)
    const graph = buildTalentGraph({ nodes, ranks, routeState: 'ready' })

    expect(graph.nodeCount).toBe(3)
    expect(graph.planeWidth).toBe(600)
    expect(graph.uniquePositionCount).toBe(3)
    expect(graph.edges.map((edge) => edge.id)).toEqual(['root->child', 'child->locked'])
    expect(graph.nodes.find((node) => node.id === 'child')).toMatchObject({
      row: 2,
      column: 3,
      state: 'available',
    })
    expect(graph.nodes.find((node) => node.id === 'locked')?.state).toBe('blocked')
  })

  it('fans choice nodes at one logical position into non-overlapping sockets', () => {
    const choiceNodes: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'choice-a', name: '选项甲', row: 1, column: 1, shape: 'choice' },
      { ...nodes[0]!, id: 'choice-b', name: '选项乙', row: 1, column: 1, shape: 'choice' },
      { ...nodes[1]!, id: 'next', name: '后续节点', row: 2, column: 2, prerequisiteIds: ['choice-a'] },
    ]
    const graph = buildTalentGraph({
      nodes: choiceNodes,
      ranks: initialTalentRanks(choiceNodes),
      routeState: 'ready',
    })
    const [first, second] = graph.nodes

    expect(graph.uniquePositionCount).toBe(2)
    expect(Math.abs((second?.x ?? 0) - (first?.x ?? 0))).toBe(58)
    expect(first?.y).toBe(second?.y)
    expect(Math.min(...graph.nodes.map((node) => node.x))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 36))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('keeps fanned choices clear of adjacent logical columns', () => {
    const crowdedRow: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'choice-a', name: '选项甲', row: 1, column: 5, shape: 'choice' },
      { ...nodes[0]!, id: 'choice-b', name: '选项乙', row: 1, column: 5, shape: 'choice' },
      { ...nodes[1]!, id: 'neighbor', name: '相邻节点', row: 1, column: 6, prerequisiteIds: [] },
    ]
    const graph = buildTalentGraph({
      nodes: crowdedRow,
      ranks: initialTalentRanks(crowdedRow),
      routeState: 'ready',
    })
    const sorted = [...graph.nodes].sort((left, right) => left.x - right.x)

    expect(sorted[1]!.x - sorted[0]!.x).toBeGreaterThanOrEqual(52)
    expect(sorted[2]!.x - sorted[1]!.x).toBeGreaterThanOrEqual(52)
    expect(sorted[0]!.x).toBeGreaterThanOrEqual(8)
    expect(sorted[2]!.x + 36).toBeLessThanOrEqual(graph.planeWidth - 8)
  })

  it('keeps the target nineteen-socket and twenty-four-edge loading density', () => {
    const graph = buildTalentGraph({
      nodes: [],
      ranks: {},
      routeState: 'loading',
      loading: true,
    })

    expect(graph.nodes).toHaveLength(19)
    expect(graph.edges).toHaveLength(24)
    expect(graph.nodes.every((node) => node.loading)).toBe(true)
    expect(graph.planeWidth).toBe(350)
  })

  it('cycles ranks only when prerequisites and point caps allow it', () => {
    const initial = initialTalentRanks(nodes)
    const first = cycleTalentRank({ nodeId: 'child', nodes, ranks: initial, pointCap: 3 })
    const second = cycleTalentRank({ nodeId: 'child', nodes, ranks: first, pointCap: 3 })
    const reset = cycleTalentRank({ nodeId: 'child', nodes, ranks: second, pointCap: 3 })

    expect(first['child']).toBe(1)
    expect(second['child']).toBe(2)
    expect(reset['child']).toBe(0)
    expect(cycleTalentRank({ nodeId: 'locked', nodes, ranks: initial, pointCap: 3 })).toBe(initial)
    expect(cycleTalentRank({ nodeId: 'root', nodes, ranks: initial, pointCap: 3 })).toBe(initial)
  })

  it('derives point counters from real selected ranks and section caps', () => {
    expect(talentPoints(nodes, { key: 'class', title: '法师', pointCap: 34 }, initialTalentRanks(nodes))).toEqual({
      cap: 34,
      spent: 1,
      remaining: 33,
    })
  })
})
