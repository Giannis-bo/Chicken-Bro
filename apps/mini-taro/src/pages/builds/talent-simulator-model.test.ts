import { describe, expect, it } from 'vitest'

import type { TalentNode } from '@wow-mini/domain'

import {
  buildTalentGraph,
  applyTalentValidation,
  initialTalentRanks,
  proposeTalentChoice,
  proposeTalentRank,
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
  it('retains real coordinates and prerequisite edges without presenting local legality as authoritative', () => {
    const ranks = initialTalentRanks(nodes)
    const graph = buildTalentGraph({ nodes, ranks, routeState: 'ready' })

    expect(graph.nodeCount).toBe(3)
    expect(graph.planeWidth).toBe(660)
    expect(graph.planeHeight).toBe(1080)
    expect(graph.uniquePositionCount).toBe(3)
    expect(graph.edges.map((edge) => edge.id)).toEqual(['root->child', 'child->locked'])
    expect(graph.nodes.find((node) => node.id === 'child')).toMatchObject({
      row: 2,
      column: 3,
      state: 'available',
    })
    expect(graph.nodes.find((node) => node.id === 'locked')?.state).toBe('available')
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
    expect(Math.abs((second?.x ?? 0) - (first?.x ?? 0))).toBe(92)
    expect(first?.y).toBe(second?.y)
    expect(Math.min(...graph.nodes.map((node) => node.x - 32))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 32))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('projects a legacy choice group into one visible slot and retains its granted rank', () => {
    const choiceNodes: readonly TalentNode[] = [
      {
        id: 'choice-a',
        name: '选项甲',
        treeKey: 'spec',
        row: 3,
        column: 4,
        maxRank: 1,
        ranks: 0,
        grantedRank: 1,
        choiceGroup: 'spec-row-3',
        nodeType: 2,
        shape: 'square',
      },
      {
        id: 'choice-b',
        name: '选项乙',
        treeKey: 'spec',
        row: 3,
        column: 4,
        maxRank: 1,
        ranks: 0,
        choiceGroup: 'spec-row-3',
        nodeType: 2,
        shape: 'square',
      },
      {
        id: 'follow-up',
        name: '后续节点',
        treeKey: 'spec',
        row: 4,
        column: 4,
        maxRank: 1,
        ranks: 0,
        prerequisiteIds: ['choice-a', 'choice-b'],
      },
    ]

    const graph = buildTalentGraph({
      nodes: choiceNodes,
      ranks: initialTalentRanks(choiceNodes),
      routeState: 'ready',
    })

    expect(initialTalentRanks(choiceNodes)).toEqual({ 'choice-a': 1 })
    expect(graph.nodes.filter((node) => node.row === 3 && node.column === 4)).toHaveLength(1)
    expect(graph.nodes.find((node) => node.id === 'choice-a')).toMatchObject({
      shape: 'choice',
      choiceOptionIds: ['choice-a', 'choice-b'],
    })
  })

  it('keeps canonical column geometry instead of reflowing adjacent branch nodes', () => {
    const crowdedRow: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'left-branch', name: '左分支', row: 1, column: 8, prerequisiteIds: [] },
      { ...nodes[1]!, id: 'right-branch', name: '右分支', row: 1, column: 9, prerequisiteIds: [] },
    ]
    const graph = buildTalentGraph({
      nodes: crowdedRow,
      ranks: initialTalentRanks(crowdedRow),
      routeState: 'ready',
    })
    const sorted = [...graph.nodes].sort((left, right) => left.x - right.x)
    const expectedColumnGap = 660 / 9

    expect(sorted[1]!.x - sorted[0]!.x).toBeCloseTo(expectedColumnGap)
  })

  it('normalizes legacy talent-node shape aliases before rendering', () => {
    const semanticNodes: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'implicit-active', row: 1, column: 1 },
      { ...nodes[0]!, id: 'passive', row: 1, column: 2, shape: 'passive' },
      { ...nodes[0]!, id: 'active', row: 1, column: 3, shape: 'rect' },
      { ...nodes[0]!, id: 'choice', row: 1, column: 4, shape: 'octagon' },
    ]

    const graph = buildTalentGraph({
      nodes: semanticNodes,
      ranks: initialTalentRanks(semanticNodes),
      routeState: 'ready',
    })

    expect(Object.fromEntries(graph.nodes.map((node) => [node.id, node.shape]))).toEqual({
      'implicit-active': 'square',
      passive: 'circle',
      active: 'square',
      choice: 'choice',
    })
  })

  it('uses the legacy normalized tree grid and clears links from node frames', () => {
    const treeNodes: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'root', row: 1, column: 1, prerequisiteIds: [] },
      { ...nodes[1]!, id: 'leaf', row: 8, column: 9, prerequisiteIds: ['root'] },
    ]
    const graph = buildTalentGraph({
      nodes: treeNodes,
      ranks: initialTalentRanks(treeNodes),
      routeState: 'ready',
    })
    const root = graph.nodes.find((node) => node.id === 'root')!
    const leaf = graph.nodes.find((node) => node.id === 'leaf')!
    const edge = graph.edges[0]!
    const centerDistance = Math.hypot(leaf.x - root.x, leaf.y - root.y)

    expect(graph.planeHeight).toBe(1080)
    expect(leaf.y - root.y).toBe(1080 * 7 / 8)
    expect(edge.width).toBeLessThan(centerDistance)
  })

  it('clears incoming and outgoing links around the wider two-choice frame wings', () => {
    const choiceNodes: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'root', row: 1, column: 2, prerequisiteIds: [] },
      {
        ...nodes[1]!,
        id: 'choice-a',
        row: 2,
        column: 1,
        maxRank: 1,
        choiceGroup: 'choice-row-2',
        prerequisiteIds: ['root'],
      },
      {
        ...nodes[1]!,
        id: 'choice-b',
        row: 2,
        column: 1,
        maxRank: 1,
        choiceGroup: 'choice-row-2',
        prerequisiteIds: ['root'],
      },
      {
        ...nodes[2]!,
        id: 'child',
        row: 3,
        column: 1,
        prerequisiteIds: ['choice-a'],
      },
    ]
    const graph = buildTalentGraph({
      nodes: choiceNodes,
      ranks: initialTalentRanks(choiceNodes),
      routeState: 'ready',
    })
    const root = graph.nodes.find((node) => node.id === 'root')!
    const choice = graph.nodes.find((node) => node.id === 'choice-a')!
    const child = graph.nodes.find((node) => node.id === 'child')!
    const incoming = graph.edges.find((edge) => edge.id === 'root->choice-a')!
    const outgoing = graph.edges.find((edge) => edge.id === 'choice-a->child')!
    const incomingDistance = Math.hypot(choice.x - root.x, choice.y - root.y)
    const outgoingDistance = Math.hypot(child.x - choice.x, child.y - choice.y)

    expect(choice.shape).toBe('choice')
    expect(incoming.width).toBeCloseTo(incomingDistance - (32 + 8) - (45 + 8 + 12))
    expect(outgoing.width).toBeCloseTo(outgoingDistance - (45 + 8) - (32 + 8 + 12))
  })

  it('reserves a visible gutter between a two-choice frame and its adjacent column', () => {
    const rowWithChoice: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'root', row: 1, column: 4, prerequisiteIds: [] },
      {
        ...nodes[1]!,
        id: 'choice-a',
        row: 3,
        column: 2,
        maxRank: 1,
        choiceGroup: 'choice-row-3',
        prerequisiteIds: ['root'],
      },
      {
        ...nodes[1]!,
        id: 'choice-b',
        row: 3,
        column: 2,
        maxRank: 1,
        choiceGroup: 'choice-row-3',
        prerequisiteIds: ['root'],
      },
      { ...nodes[1]!, id: 'adjacent', row: 3, column: 3, prerequisiteIds: ['root'] },
      { ...nodes[2]!, id: 'right-boundary', row: 4, column: 7, prerequisiteIds: [] },
    ]
    const graph = buildTalentGraph({
      nodes: rowWithChoice,
      ranks: initialTalentRanks(rowWithChoice),
      routeState: 'ready',
    })
    const choice = graph.nodes.find((node) => node.id === 'choice-a')!
    const adjacent = graph.nodes.find((node) => node.id === 'adjacent')!

    expect(adjacent.x - choice.x).toBeGreaterThanOrEqual(109)
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
    expect(graph.planeWidth).toBe(660)
  })

  it('constructs a rank proposal without locally enforcing prerequisite or point-cap rules', () => {
    const initial = initialTalentRanks(nodes)
    expect(proposeTalentRank({ nodeId: 'locked', nodes, ranks: initial })).toEqual({ root: 1, locked: 1 })
  })

  it('switches the selected alternative within one legacy choice group without spending another point', () => {
    const choiceNodes: readonly TalentNode[] = [
      {
        id: 'choice-a',
        name: '选项甲',
        treeKey: 'spec',
        row: 3,
        column: 4,
        maxRank: 1,
        ranks: 1,
        choiceGroup: 'spec-row-3',
        nodeType: 2,
      },
      {
        id: 'choice-b',
        name: '选项乙',
        treeKey: 'spec',
        row: 3,
        column: 4,
        maxRank: 1,
        ranks: 0,
        choiceGroup: 'spec-row-3',
        nodeType: 2,
      },
    ]

    expect(proposeTalentChoice({
      nodeId: 'choice-b',
      nodes: choiceNodes,
      ranks: initialTalentRanks(choiceNodes),
    })).toEqual({ 'choice-b': 1 })
  })

  it('keeps the previous visible ranks when backend validation rejects a proposal', () => {
    const current = { root: 1 }
    const decision = applyTalentValidation(current, {
      classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
      status: 'failed', source: 'simc', schemaRevision: 'websim-talent-rules-v1',
      errors: ['missing parent talent for locked'], warnings: [], lines: [],
      selectedCounts: { class: 0, spec: 0, hero: 0 },
      talentState: { selectedNodes: [{ id: 'locked', rank: 1 }] },
      talentSchemaRevision: 'websim-talent-rules-v1', blockers: [],
    }, false)

    expect(decision).toEqual({
      accepted: false,
      ranks: current,
      error: 'missing parent talent for locked',
    })
  })

  it('derives point counters from real selected ranks and section caps', () => {
    expect(talentPoints(nodes, { key: 'class', title: '法师', pointCap: 34 }, initialTalentRanks(nodes))).toEqual({
      cap: 34,
      spent: 1,
      remaining: 33,
    })
  })
})
