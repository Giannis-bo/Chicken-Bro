import { describe, expect, it } from 'vitest'

import type {
  CommunityTemplateReference,
  TalentNode,
  TalentNodeAvailabilityPayload,
  WebsimBootstrapPayload,
} from '@wow-mini/domain'

import {
  buildTalentGraph,
  heroTalentIcon,
  heroTalentOptions,
  applyTalentValidation,
  communityTalentRegionLabel,
  communityTalentRankingLabel,
  communityTalentTemplateTitle,
  communityTalentTemplateHasPlayerChoices,
  communityTalentWinnerForImport,
  defaultTalentTemplateTitle,
  initialTalentRanks,
  proposeTalentChoice,
  proposeTalentRank,
  runFencedTalentSave,
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

const availability: TalentNodeAvailabilityPayload = {
  schemaRevision: 'websim-talent-node-availability-v1',
  source: 'backend_validation',
  nodes: {
    root: { state: 'selected', reasonCode: 'selected', reason: 'selected by backend validation' },
    child: { state: 'available', reasonCode: 'available', reason: 'available by backend validation' },
    locked: { state: 'blocked', reasonCode: 'missing_parent', reason: 'missing parent talent for locked' },
  },
}

describe('talent simulator target model', () => {
  it('uses an editable, meaningful default title for a saved talent configuration', () => {
    expect(defaultTalentTemplateTitle({
      classLabel: '法师',
      specLabel: '冰霜',
      heroLabel: '霜火',
      now: new Date(2026, 6, 20, 9, 5),
    })).toBe('法师-冰霜-霜火-2026-07-20 09:05')
  })

  it('keeps one stale, backend-selected community winner importable', () => {
    const staleWinner: CommunityTemplateReference = {
      id: 'rio-kr-winner',
      name: 'Raider.IO KR 霜火',
      status: 'verified',
      canApplyVisual: true,
      isStale: true,
      freshnessStatus: 'stale',
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
      playerName: 'TopPlayer',
      serverName: 'Azshara',
      region: 'KR',
      mplusScore: 4123.4,
    }

    expect(communityTalentWinnerForImport([
      { id: 'pending', status: 'pending_collection', canApplyVisual: false },
      staleWinner,
    ])).toBe(staleWinner)
  })

  it('renders known game regions with player-facing labels and preserves unknown regions', () => {
    expect(communityTalentRegionLabel('cn')).toBe('国服')
    expect(communityTalentRegionLabel('EU')).toBe('欧服')
    expect(communityTalentRegionLabel('us')).toBe('美服')
    expect(communityTalentRegionLabel('kr')).toBe('韩服')
    expect(communityTalentRegionLabel('tw')).toBe('台服')
    expect(communityTalentRegionLabel('br')).toBe('BR')
  })

  it('uses player-facing community template titles and only exposes verified Raider.IO ranks', () => {
    const raiderWinner: CommunityTemplateReference = {
      playerName: 'Supermono',
      classLabel: '法师',
      specLabel: '奥术',
      heroLabel: '法术投射者',
      sourceKey: 'raiderio',
      mplusRank: 1,
    }

    expect(communityTalentTemplateTitle(raiderWinner)).toBe('Supermono-法师-奥术-法术投射者')
    expect(communityTalentRankingLabel(raiderWinner)).toBe('Raider.IO 大秘境排名：#1')
    expect(communityTalentRankingLabel({
      ...raiderWinner,
      sourceKey: 'warcraftlogs',
    })).toBeUndefined()
  })

  it('uses only the current hero tree community winner when an older API returns multiple heroes', () => {
    const frostfireWinner: CommunityTemplateReference = {
      id: 'rio-frostfire-winner',
      heroKey: 'frostfire',
      status: 'verified',
      canApplyVisual: true,
      talentState: { selectedNodes: [{ id: 'frostfire-root', rank: 1 }] },
    }
    const spellslingerWinner: CommunityTemplateReference = {
      id: 'rio-spellslinger-winner',
      heroKey: 'spellslinger',
      status: 'verified',
      canApplyVisual: true,
      talentState: { selectedNodes: [{ id: 'spellslinger-root', rank: 1 }] },
    }

    expect(communityTalentWinnerForImport([
      spellslingerWinner,
      frostfireWinner,
    ], 'frostfire')).toBe(frostfireWinner)
  })

  it('does not replace the winner a player selected while refreshing community import data', () => {
    const selectedWinner: CommunityTemplateReference = {
      id: 'winner-visible-when-sheet-opened',
      heroKey: 'spellslinger',
      status: 'verified',
      canApplyVisual: true,
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }, { id: 'child', rank: 1 }] },
    }
    const replacementWinner: CommunityTemplateReference = {
      id: 'newer-winner-arrived-during-refresh',
      heroKey: 'spellslinger',
      status: 'verified',
      canApplyVisual: true,
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }, { id: 'new-child', rank: 1 }] },
    }

    expect(communityTalentWinnerForImport(
      [replacementWinner],
      'spellslinger',
      selectedWinner.id,
    )).toBeUndefined()
  })

  it('rejects a community template that only contains its system-granted root', () => {
    expect(communityTalentTemplateHasPlayerChoices({
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
    })).toBe(false)
    expect(communityTalentTemplateHasPlayerChoices({
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }, { id: 'choice', rank: 1 }] },
    })).toBe(true)
  })

  it('retains real coordinates and prerequisite edges without presenting local legality as authoritative', () => {
    const ranks = initialTalentRanks(nodes)
    const graph = buildTalentGraph({ nodes, ranks, availability, routeState: 'ready' })

    expect(graph.nodeCount).toBe(3)
    expect(graph.planeWidth).toBe(350)
    expect(graph.planeHeight).toBe(314)
    expect(graph.uniquePositionCount).toBe(3)
    expect(graph.edges.map((edge) => edge.id)).toEqual(['root->child', 'child->locked'])
    expect(graph.nodes.find((node) => node.id === 'child')).toMatchObject({
      row: 2,
      column: 3,
      state: 'available',
    })
    expect(graph.nodes.find((node) => node.id === 'locked')?.state).toBe('blocked')
  })

  it('fails closed when backend node availability is missing', () => {
    const graph = buildTalentGraph({
      nodes,
      ranks: initialTalentRanks(nodes),
      routeState: 'ready',
    })

    expect(graph.nodes.find((node) => node.id === 'root')?.state).toBe('selected')
    expect(graph.nodes.find((node) => node.id === 'child')?.state).toBe('blocked')
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
    expect(Math.abs((second?.x ?? 0) - (first?.x ?? 0))).toBe(52)
    expect(first?.y).toBe(second?.y)
    expect(Math.min(...graph.nodes.map((node) => node.x - (node.shape === 'choice' ? 7 : 0)))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + (node.shape === 'choice' ? 43 : 36)))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('keeps duplicate authority nodes at an edge inside the canvas', () => {
    const duplicatedEdgeRow: readonly TalentNode[] = [
      ...[1, 1, 2, 3, 4, 5, 6, 7].map((column, index): TalentNode => ({
        ...nodes[1]!,
        id: `edge-${column}-${index}`,
        name: `边界节点 ${column}-${index}`,
        row: 4,
        column,
        prerequisiteIds: [],
        shape: 'circle',
      })),
    ]
    const graph = buildTalentGraph({
      nodes: duplicatedEdgeRow,
      ranks: initialTalentRanks(duplicatedEdgeRow),
      routeState: 'ready',
    })
    const duplicateNodes = graph.nodes
      .filter((node) => node.column === 1)
      .sort((left, right) => left.x - right.x)

    expect(duplicateNodes[1]!.x - duplicateNodes[0]!.x).toBeGreaterThanOrEqual(36)
    expect(Math.min(...graph.nodes.map((node) => node.x))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 36))).toBeLessThanOrEqual(graph.planeWidth)
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

  it('preserves Wowhead Frost source lanes between the central root and its two branches', () => {
    const frostTopRows: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'root', name: '冰法根节点', row: 1, column: 10, prerequisiteIds: [] },
      { ...nodes[1]!, id: 'left-branch', name: '左分支', row: 2, column: 8, prerequisiteIds: ['root'] },
      { ...nodes[1]!, id: 'right-branch', name: '右分支', row: 2, column: 12, prerequisiteIds: ['root'] },
      { ...nodes[1]!, id: 'outer-left', name: '左外侧', row: 3, column: 6, prerequisiteIds: ['left-branch'] },
      { ...nodes[1]!, id: 'inner-left', name: '左内侧', row: 3, column: 8, prerequisiteIds: ['left-branch'] },
      { ...nodes[1]!, id: 'inner-right', name: '右内侧', row: 3, column: 12, prerequisiteIds: ['right-branch'] },
      { ...nodes[1]!, id: 'outer-right', name: '右外侧', row: 3, column: 14, prerequisiteIds: ['right-branch'] },
    ]
    const graph = buildTalentGraph({
      nodes: frostTopRows,
      ranks: initialTalentRanks(frostTopRows),
      routeState: 'ready',
    })
    const center = (id: string) => graph.nodes.find((node) => node.id === id)!.x + 18

    expect(center('root')).toBe(175)
    expect(center('root') - center('left-branch')).toBe(52)
    expect(center('right-branch') - center('root')).toBe(52)
    expect(center('right-branch') - center('left-branch')).toBe(104)
    expect(center('left-branch')).toBe(center('inner-left'))
    expect(center('right-branch')).toBe(center('inner-right'))
  })

  it('keeps the centered-row fallback available for explicit compatibility callers', () => {
    const frostTopRows: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'root', name: '冰法根节点', row: 1, column: 10, prerequisiteIds: [] },
      { ...nodes[1]!, id: 'left-branch', name: '左分支', row: 2, column: 8, prerequisiteIds: ['root'] },
      { ...nodes[1]!, id: 'right-branch', name: '右分支', row: 2, column: 12, prerequisiteIds: ['root'] },
    ]
    const graph = buildTalentGraph({
      nodes: frostTopRows,
      ranks: initialTalentRanks(frostTopRows),
      routeState: 'ready',
      layoutMode: 'centered_rows',
    })
    const center = (id: string) => graph.nodes.find((node) => node.id === id)!.x + 18

    expect(center('root') - center('left-branch')).toBe(26)
    expect(center('right-branch') - center('root')).toBe(26)
  })

  it('aligns sparse and crowded rows on their shared source lanes', () => {
    const alignedTree: readonly TalentNode[] = [
      ...[2, 3, 4, 5, 6, 7].map((column): TalentNode => ({
        ...nodes[1]!,
        id: `crowded-${column}`,
        name: `拥挤行 ${column}`,
        row: 4,
        column,
        prerequisiteIds: [],
      })),
      {
        ...nodes[1]!,
        id: 'sparse-4',
        name: '稀疏行 4',
        row: 5,
        column: 4,
        prerequisiteIds: [],
      },
    ]
    const graph = buildTalentGraph({
      nodes: alignedTree,
      ranks: initialTalentRanks(alignedTree),
      routeState: 'ready',
    })
    const crowdedColumnFour = graph.nodes.find((node) => node.id === 'crowded-4')!
    const sparseColumnFour = graph.nodes.find((node) => node.id === 'sparse-4')!
    const crowdedRow = graph.nodes
      .filter((node) => node.row === 4)
      .sort((left, right) => left.column - right.column)
    const crowdedCenters = crowdedRow.map((node) => node.x + 18)
    const crowdedGaps = crowdedCenters.slice(1).map((center, index) => (
      center - crowdedCenters[index]!
    ))

    expect(crowdedColumnFour.x).toBe(sparseColumnFour.x)
    expect(sparseColumnFour.x + 18).toBe(149)
    expect(crowdedCenters.reduce((total, center) => total + center, 0) / crowdedCenters.length).toBe(175)
    expect(crowdedGaps.every((gap) => gap === crowdedGaps[0])).toBe(true)
    expect(Math.min(...graph.nodes.map((node) => node.x))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 36))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('uses the complete tree viewport width and height without changing row centering', () => {
    const fullCanvasNodes: readonly TalentNode[] = [
      ...Array.from({ length: 10 }, (_, rowIndex): readonly TalentNode[] => {
        const row = rowIndex + 1
        if (row === 6) {
          return Array.from({ length: 5 }, (_, columnIndex): TalentNode => ({
            ...nodes[1]!,
            id: `full-row-${row}-node-${columnIndex + 1}`,
            name: `完整视图 ${row}-${columnIndex + 1}`,
            row,
            column: columnIndex + 1,
            prerequisiteIds: [],
          }))
        }
        return [{
          ...nodes[1]!,
          id: `full-row-${row}-node-1`,
          name: `完整视图 ${row}-1`,
          row,
          column: 4,
          prerequisiteIds: [],
        }]
      }).flat(),
    ]
    const graph = buildTalentGraph({
      nodes: fullCanvasNodes,
      ranks: initialTalentRanks(fullCanvasNodes),
      routeState: 'ready',
    })
    const minX = Math.min(...graph.nodes.map((node) => node.x))
    const maxX = Math.max(...graph.nodes.map((node) => node.x + 36))
    const minY = Math.min(...graph.nodes.map((node) => node.y))
    const maxY = Math.max(...graph.nodes.map((node) => node.y + 36))
    const displayedScale = Math.min(1, 334 / (maxX - minX), 445 / (maxY - minY))
    const widestRowCenters = graph.nodes
      .filter((node) => node.row === 6)
      .map((node) => node.x + 18)

    expect(maxX - minX).toBeCloseTo(334)
    expect(maxY - minY).toBeCloseTo(445)
    expect((Math.min(...widestRowCenters) + Math.max(...widestRowCenters)) / 2).toBeCloseTo(175)
    expect((maxX - minX) * displayedScale).toBeCloseTo(334)
    expect((maxY - minY) * displayedScale).toBeCloseTo(445)
  })

  it('gives every dense source-lattice tree a roomier vertical row rhythm', () => {
    const frostSampleRows: readonly TalentNode[] = Array.from({ length: 10 }, (_, rowIndex): readonly TalentNode[] => {
      const row = rowIndex + 1
      const columns = row === 6 ? [4, 6, 8, 10, 12, 14, 16] : [10]
      return columns.map((column, columnIndex): TalentNode => ({
        ...nodes[1]!,
        id: `frost-sample-${row}-${columnIndex + 1}`,
        name: `冰法样本 ${row}-${columnIndex + 1}`,
        row,
        column,
        prerequisiteIds: [],
      }))
    }).flat()
    const graph = buildTalentGraph({
      nodes: frostSampleRows,
      ranks: initialTalentRanks(frostSampleRows),
      routeState: 'ready',
      layoutMode: 'source_lattice',
    })
    const rowOne = graph.nodes.find((node) => node.row === 1)!
    const rowTwo = graph.nodes.find((node) => node.row === 2)!

    expect(rowTwo.y - rowOne.y).toBe(60)
    expect(graph.planeHeight).toBe(612)
  })

  it('expands a sparse hero tree across the tree viewport without changing row centering', () => {
    const sparseHeroNodes: readonly TalentNode[] = [
      ...Array.from({ length: 5 }, (_, rowIndex): readonly TalentNode[] => {
        const row = rowIndex + 1
        const columns = row === 1 || row === 5 ? [3] : [1, 2, 3, 4]
        return columns.map((column, columnIndex): TalentNode => ({
          ...nodes[1]!,
          id: `hero-${row}-${columnIndex + 1}`,
          name: `英雄树 ${row}-${columnIndex + 1}`,
          treeKey: 'hero',
          row,
          column,
          prerequisiteIds: [],
        }))
      }).flat(),
    ]
    const graph = buildTalentGraph({
      nodes: sparseHeroNodes,
      ranks: initialTalentRanks(sparseHeroNodes),
      routeState: 'ready',
    })
    const widestRow = graph.nodes.filter((node) => node.row === 2)
    const minX = Math.min(...graph.nodes.map((node) => node.x))
    const maxX = Math.max(...graph.nodes.map((node) => node.x + 36))
    const minY = Math.min(...graph.nodes.map((node) => node.y))
    const maxY = Math.max(...graph.nodes.map((node) => node.y + 36))

    expect(maxX - minX).toBe(306)
    expect(maxY - minY).toBe(420)
    expect(graph.planeHeight).toBe(456)
    expect(widestRow.map((node) => node.x + 18)).toEqual([40, 130, 220, 310])
    expect(widestRow.reduce((total, node) => total + node.x + 18, 0) / widestRow.length).toBe(175)
  })

  it('keeps identical source columns aligned across rows with uniform lane gaps', () => {
    const symmetricRows: readonly TalentNode[] = Array.from({ length: 9 }, (_, rowIndex) => (
      Array.from({ length: rowIndex + 1 }, (_, nodeIndex): TalentNode => ({
        ...nodes[1]!,
        id: `row-${rowIndex + 1}-node-${nodeIndex + 1}`,
        name: `Row ${rowIndex + 1} node ${nodeIndex + 1}`,
        row: rowIndex + 1,
        column: nodeIndex * 2 + 1,
        prerequisiteIds: [],
        ...(rowIndex === 8 && nodeIndex === 0 ? { shape: 'choice' } : {}),
      }))
    )).flat()
    const graph = buildTalentGraph({
      nodes: symmetricRows,
      ranks: initialTalentRanks(symmetricRows),
      routeState: 'ready',
    })

    for (let rowNumber = 1; rowNumber <= 9; rowNumber += 1) {
      const row = graph.nodes
        .filter((node) => node.row === rowNumber)
        .sort((left, right) => left.column - right.column)
      const centers = row.map((node) => node.x + 18)
      const gaps = centers.slice(1).map((center, index) => center - centers[index]!)

      expect(gaps.every((gap) => Math.abs(gap - gaps[0]!) < 0.001)).toBe(true)
      row.forEach((node) => {
        const sameColumn = graph.nodes.find((candidate) => candidate.row === 9 && candidate.column === node.column)
        if (sameColumn) expect(node.x).toBe(sameColumn.x)
      })
    }

    expect(Math.min(...graph.nodes.map((node) => (
      node.x - (node.shape === 'choice' ? 7 : 0)
    )))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => (
      node.x + (node.shape === 'choice' ? 43 : 36)
    )))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('keeps dense and staggered rows aligned inside the compact canvas', () => {
    const staggeredTree: readonly TalentNode[] = [
      ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((column): TalentNode => ({
        ...nodes[1]!,
        id: `dense-${column}`,
        name: `密集行 ${column}`,
        row: 5,
        column,
        prerequisiteIds: [],
        ...(column === 1 ? { shape: 'choice' } : {}),
      })),
      ...[1, 3, 5, 7, 9].map((column): TalentNode => ({
        ...nodes[1]!,
        id: `staggered-${column}`,
        name: `交错行 ${column}`,
        row: 6,
        column,
        prerequisiteIds: [],
      })),
    ]
    const graph = buildTalentGraph({
      nodes: staggeredTree,
      ranks: initialTalentRanks(staggeredTree),
      routeState: 'ready',
    })
    const byId = new Map(graph.nodes.map((node) => [node.id, node]))
    const denseRow = graph.nodes
      .filter((node) => node.row === 5)
      .sort((left, right) => left.column - right.column)
    const staggeredRow = graph.nodes
      .filter((node) => node.row === 6)
      .sort((left, right) => left.column - right.column)
    const denseCenters = denseRow.map((node) => node.x + 18)
    const staggeredCenters = staggeredRow.map((node) => node.x + 18)

    expect(byId.get('dense-1')?.x).toBe(byId.get('staggered-1')?.x)
    expect(byId.get('dense-9')?.x).toBe(byId.get('staggered-9')?.x)
    expect(denseCenters.reduce((total, center) => total + center, 0) / denseCenters.length).toBeCloseTo(175)
    expect(staggeredCenters.reduce((total, center) => total + center, 0) / staggeredCenters.length).toBeCloseTo(175)
    expect(denseRow.slice(1).every((node, index) => (
      node.x - denseRow[index]!.x > 36
    ))).toBe(true)
    expect(Math.min(...graph.nodes.map((node) => (
      node.x - (node.shape === 'choice' ? 7 : 0)
    )))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 36))).toBeLessThanOrEqual(graph.planeWidth)
  })

  it('preserves separated canonical columns for nodes on sparse rows', () => {
    const wideTree: readonly TalentNode[] = [
      { ...nodes[0]!, id: 'far-left', row: 1, column: 1, prerequisiteIds: [] },
      { ...nodes[1]!, id: 'far-right', row: 2, column: 11, prerequisiteIds: [] },
    ]
    const graph = buildTalentGraph({
      nodes: wideTree,
      ranks: initialTalentRanks(wideTree),
      routeState: 'ready',
    })

    expect(graph.nodes.map((node) => node.x + 18)).toEqual([45, 305])
    expect(Math.min(...graph.nodes.map((node) => node.x))).toBeGreaterThanOrEqual(0)
    expect(Math.max(...graph.nodes.map((node) => node.x + 36))).toBeLessThanOrEqual(graph.planeWidth)
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

    expect(graph.planeHeight).toBe(408)
    expect(leaf.y - root.y).toBe(48 * 7)
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
    const incomingUnitX = Math.abs(choice.x - root.x) / incomingDistance
    const incomingUnitY = Math.abs(choice.y - root.y) / incomingDistance
    const incomingChoiceRadius = 1 / Math.sqrt(
      (incomingUnitX * incomingUnitX) / (25 * 25) + (incomingUnitY * incomingUnitY) / (20 * 20),
    )
    const outgoingUnitX = Math.abs(child.x - choice.x) / outgoingDistance
    const outgoingUnitY = Math.abs(child.y - choice.y) / outgoingDistance
    const outgoingChoiceRadius = 1 / Math.sqrt(
      (outgoingUnitX * outgoingUnitX) / (25 * 25) + (outgoingUnitY * outgoingUnitY) / (20 * 20),
    )

    expect(choice.shape).toBe('choice')
    expect(incoming.width).toBeCloseTo(incomingDistance - 18 - (incomingChoiceRadius + 6))
    expect(outgoing.width).toBeCloseTo(outgoingDistance - outgoingChoiceRadius - (18 + 6))
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

    expect(adjacent.x - choice.x).toBeGreaterThanOrEqual(52)
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

  it('treats encoded validation with unavailable rule authority as rejected without throwing', () => {
    const current = { root: 1 }
    expect(applyTalentValidation(current, {
      classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
      status: 'encoded', source: 'simc', schemaRevision: 'websim-talent-rules-v1',
      errors: [], warnings: [], lines: ['class_talents=1:1'],
      selectedCounts: { class: 1, spec: 0, hero: 0 },
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }] },
      talentSchemaRevision: 'websim-talent-rules-v1',
      talentReadiness: {
        treeReady: true,
        ruleReady: false,
        spellReady: false,
        encodingReady: true,
        simcReady: false,
        blockers: ['talent authority unavailable'],
      },
      blockers: ['talent authority unavailable'],
    }, false)).toEqual({
      accepted: false,
      ranks: current,
      error: 'talent authority unavailable',
    })
  })

  it('accepts a backend-encoded edit when only spell presentation evidence is incomplete', () => {
    const current = { root: 1 }
    expect(applyTalentValidation(current, {
      classKey: 'mage', specKey: 'frost', heroKey: 'frostfire',
      status: 'encoded', source: 'simc', schemaRevision: 'websim-talent-rules-v1',
      errors: [], warnings: [], lines: ['class_talents=1:1/2:1'],
      selectedCounts: { class: 2, spec: 0, hero: 0 },
      talentState: { selectedNodes: [{ id: 'root', rank: 1 }, { id: 'child', rank: 1 }] },
      talentSchemaRevision: 'websim-talent-rules-v1',
      talentReadiness: {
        treeReady: true,
        ruleReady: true,
        spellReady: false,
        encodingReady: true,
        simcReady: true,
        blockers: [
          'talent spell descriptions/icons are incomplete',
          'talent spell descriptions contain unresolved formula text for 109 talent nodes',
        ],
      },
      blockers: [
        'talent spell descriptions/icons are incomplete',
        'talent spell descriptions contain unresolved formula text for 109 talent nodes',
      ],
    }, false)).toEqual({
      accepted: true,
      ranks: { root: 1, child: 1 },
      error: '',
    })
  })

  it('drops a save completion when selection changes while persistence is pending', async () => {
    let current = true
    let resolvePersist: ((value: string) => void) | undefined
    const completed: string[] = []
    const operation = runFencedTalentSave({
      isCurrent: () => current,
      exportCurrent: async () => ({ code: 'websim:mage:frost::root:1' }),
      persist: async () => new Promise<string>((resolve) => { resolvePersist = resolve }),
      complete: async (saved) => { completed.push(saved) },
    })
    await Promise.resolve()
    current = false
    resolvePersist?.('saved-old-spec')

    await expect(operation).resolves.toBe('stale')
    expect(completed).toEqual([])
  })

  it('excludes system-granted ranks from the player point counter', () => {
    expect(talentPoints(nodes, { key: 'class', title: '法师', pointCap: 34 }, initialTalentRanks(nodes))).toEqual({
      cap: 34,
      spent: 0,
      remaining: 34,
    })
  })

  it('uses the selected specialization hero trees from the authoritative bootstrap payload', () => {
    const bootstrap = {
      navTitle: 'WebSim',
      classes: [{
        key: 'mage',
        label: '法师',
        heroTrees: [{ key: 'sunfury', label: '烈日之怒' }],
        specs: [{
          key: 'frost',
          label: '冰霜',
          heroTrees: [
            { key: 'frostfire', label: '霜火' },
            { key: 'spellslinger', label: '法术投射者' },
          ],
        }],
      }],
      scenarios: [],
      gearSlots: [],
      defaultSelection: { classKey: 'mage', specKey: 'frost', heroKey: 'frostfire' },
      dataStatus: 'verified',
    } as unknown as WebsimBootstrapPayload

    expect(heroTalentOptions(bootstrap, { classKey: 'mage', specKey: 'frost' })).toEqual([
      { key: 'frostfire', label: '霜火' },
      { key: 'spellslinger', label: '法术投射者' },
    ])
  })

  it('uses the active hero root talent icon for the selector crest', () => {
    const heroNodes: readonly TalentNode[] = [
      {
        ...nodes[1]!,
        id: 'hero-child',
        treeKey: 'hero',
        row: 2,
        column: 2,
        iconUrl: 'https://assets.example/hero-child.jpg',
      },
      {
        ...nodes[0]!,
        id: 'hero-root',
        treeKey: 'hero',
        row: 1,
        column: 2,
        iconUrl: 'https://assets.example/hero-root.jpg',
      },
    ]

    expect(heroTalentIcon(heroNodes)).toBe('https://assets.example/hero-root.jpg')
  })
})
