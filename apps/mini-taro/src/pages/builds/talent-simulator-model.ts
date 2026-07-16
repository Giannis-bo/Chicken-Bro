import type {
  ReadinessState,
  TalentNode,
  TalentTreeSection,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

export type TalentGraphNodeState = 'selected' | 'available' | 'unselected' | 'blocked' | 'loading'

export interface TalentGraphNodeView {
  id: string
  label: string
  description: string
  descriptionStatus: string
  row: number
  column: number
  x: number
  y: number
  rank: number
  maxRank: number
  requiredPoints: number
  prerequisiteIds: readonly string[]
  parentMode: string
  shape: string
  granted: boolean
  iconUrl?: string
  state: TalentGraphNodeState
  loading: boolean
}

export interface TalentGraphEdgeView {
  id: string
  fromId: string
  toId: string
  x: number
  y: number
  width: number
  angle: number
  state: 'selected' | 'available' | 'blocked' | 'loading'
}

export interface TalentGraphView {
  nodes: readonly TalentGraphNodeView[]
  edges: readonly TalentGraphEdgeView[]
  planeWidth: number
  planeHeight: number
  columnCount: number
  nodeCount: number
  uniquePositionCount: number
}

export interface TalentPointView {
  cap: number
  spent: number
  remaining: number
}

const loadingGraphWidth = 350
const loadingNodeSize = 30
const readyGraphWidth = 350
const readyNodeSize = 36
const readyGraphPad = 18
const readyRowGap = 48
const choiceNodeSpread = 42
const readyNodeSeparation = 42

const loadingPositions = [
  [168.39, 6.54], [45.37, 32.72], [168.83, 69.36], [293.59, 32.72],
  [88.99, 79.4], [249.53, 79.4], [20.94, 95.54], [318.89, 95.54],
  [168.83, 131.31], [73.72, 150.94], [279.19, 150.94], [168.83, 198.49],
  [26.17, 191.95], [313.22, 191.95], [89.43, 214.19], [249.53, 214.19],
  [50.17, 246.48], [308.42, 246.48], [168.83, 260.44],
] as const

const loadingConnections = [
  [0, 2], [1, 4], [1, 6], [2, 4], [2, 5], [3, 5], [3, 7], [4, 8],
  [5, 8], [6, 9], [7, 10], [8, 9], [8, 10], [9, 11], [10, 11], [9, 12],
  [10, 13], [11, 14], [11, 15], [12, 16], [13, 17], [14, 18], [15, 18], [16, 18],
] as const

function finiteInteger(value: number | undefined, fallback: number): number {
  return Number.isFinite(value) ? Math.trunc(value ?? fallback) : fallback
}

function nodeTreeKey(node: TalentNode): string {
  return node.treeKey || node.treeType || 'class'
}

export function initialTalentRanks(nodes: readonly TalentNode[]): Readonly<Record<string, number>> {
  return Object.fromEntries(nodes.map((node) => [
    node.id,
    Math.max(0, finiteInteger(node.ranks, 0)),
  ]))
}

export function activeTalentNodes(
  payload: WebsimTalentsPayload | undefined,
  activeTree: string,
): readonly TalentNode[] {
  return (payload?.nodes ?? []).filter((node) => nodeTreeKey(node) === activeTree)
}

export function activeTalentSection(
  payload: WebsimTalentsPayload | undefined,
  activeTree: string,
): TalentTreeSection | undefined {
  return payload?.treeSections.find((section) => section.key === activeTree)
}

export function talentPoints(
  nodes: readonly TalentNode[],
  section: TalentTreeSection | undefined,
  ranks: Readonly<Record<string, number>>,
): TalentPointView {
  const cap = Math.max(0, finiteInteger(section?.pointCap ?? section?.maxPoints, 0))
  const spent = nodes.reduce((total, node) => total + Math.max(0, ranks[node.id] ?? 0), 0)
  return { cap, spent, remaining: Math.max(0, cap - spent) }
}

function prerequisitesMet(
  node: TalentNode,
  ranks: Readonly<Record<string, number>>,
): boolean {
  const parentIds = node.prerequisiteIds ?? []
  if (!parentIds.length) return true
  if (node.parentMode === 'all') return parentIds.every((id) => (ranks[id] ?? 0) > 0)
  return parentIds.some((id) => (ranks[id] ?? 0) > 0)
}

function nodeState(
  node: TalentNode,
  ranks: Readonly<Record<string, number>>,
  spent: number,
  interactive: boolean,
): TalentGraphNodeState {
  if ((ranks[node.id] ?? 0) > 0) return 'selected'
  if (!interactive) return 'blocked'
  const parentsReady = prerequisitesMet(node, ranks)
  const requirement = Math.max(0, finiteInteger(node.requiredPoints, 0))
  if (parentsReady && requirement <= spent) return 'available'
  if (parentsReady) return 'unselected'
  return 'blocked'
}

function edgeGeometry(
  id: string,
  fromId: string,
  toId: string,
  fromX: number,
  fromY: number,
  toX: number,
  toY: number,
  nodeCenter: number,
  state: TalentGraphEdgeView['state'],
): TalentGraphEdgeView {
  const x = fromX + nodeCenter
  const y = fromY + nodeCenter
  const dx = toX - fromX
  const dy = toY - fromY
  return {
    id,
    fromId,
    toId,
    x,
    y,
    width: Math.sqrt(dx * dx + dy * dy),
    angle: Math.atan2(dy, dx) * (180 / Math.PI),
    state,
  }
}

function buildLoadingGraph(): TalentGraphView {
  const nodes = loadingPositions.map(([x, y], index): TalentGraphNodeView => ({
    id: `loading-${index + 1}`,
    label: '',
    description: '',
    descriptionStatus: 'loading',
    row: index + 1,
    column: 1,
    x,
    y,
    rank: 0,
    maxRank: 1,
    requiredPoints: 0,
    prerequisiteIds: [],
    parentMode: 'any',
    shape: index === 0 ? 'choice' : 'circle',
    granted: false,
    state: 'loading',
    loading: true,
  }))
  const edges = loadingConnections.map(([fromIndex, toIndex], index) => {
    const from = nodes[fromIndex]
    const to = nodes[toIndex]
    if (!from || !to) throw new Error('invalid loading graph connection')
    return edgeGeometry(
      `loading-edge-${index + 1}`,
      from.id,
      to.id,
      from.x,
      from.y,
      to.x,
      to.y,
      loadingNodeSize / 2,
      'loading',
    )
  })
  return {
    nodes,
    edges,
    planeWidth: loadingGraphWidth,
    planeHeight: 300,
    columnCount: 7,
    nodeCount: nodes.length,
    uniquePositionCount: nodes.length,
  }
}

export function buildTalentGraph(input: {
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
  routeState: ReadinessState
  loading?: boolean
}): TalentGraphView {
  if (input.loading || input.nodes.length === 0) return buildLoadingGraph()

  const interactive = input.routeState === 'ready' || input.routeState === 'partial'
  const columnCount = Math.max(1, ...input.nodes.map((node) => Math.max(1, finiteInteger(node.column, 1))))
  const maxRow = Math.max(1, ...input.nodes.map((node) => Math.max(1, finiteInteger(node.row, 1))))
  const positionCounts = new Map<string, number>()
  for (const node of input.nodes) {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    const positionKey = `${row}:${column}`
    positionCounts.set(positionKey, (positionCounts.get(positionKey) ?? 0) + 1)
  }
  const maxPositionUse = Math.max(1, ...positionCounts.values())
  const fanExtent = ((maxPositionUse - 1) * choiceNodeSpread) / 2
  const graphPad = Math.max(readyGraphPad, fanExtent + 8)
  const columnGap = columnCount === 1
    ? 0
    : (readyGraphWidth - readyNodeSize - graphPad * 2) / (columnCount - 1)
  const spent = input.nodes.reduce((total, node) => total + Math.max(0, input.ranks[node.id] ?? 0), 0)
  const positionUse = new Map<string, number>()
  const nodes = input.nodes.map((node): TalentGraphNodeView => {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    const positionKey = `${row}:${column}`
    const duplicateIndex = positionUse.get(positionKey) ?? 0
    positionUse.set(positionKey, duplicateIndex + 1)
    const duplicateCount = positionCounts.get(positionKey) ?? 1
    const duplicateOffset = (duplicateIndex - (duplicateCount - 1) / 2) * choiceNodeSpread
    return {
      id: node.id,
      label: node.name,
      description: node.description ?? '',
      descriptionStatus: node.descriptionStatus ?? 'unknown',
      row,
      column,
      x: graphPad + (column - 1) * columnGap + duplicateOffset,
      y: graphPad + (row - 1) * readyRowGap,
      rank: Math.max(0, input.ranks[node.id] ?? 0),
      maxRank: Math.max(1, finiteInteger(node.maxRank, 1)),
      requiredPoints: Math.max(0, finiteInteger(node.requiredPoints, 0)),
      prerequisiteIds: node.prerequisiteIds ?? [],
      parentMode: node.parentMode ?? 'any',
      shape: node.shape ?? 'circle',
      granted: node.granted === true,
      ...(node.iconUrl ? { iconUrl: node.iconUrl } : {}),
      state: nodeState(node, input.ranks, spent, interactive),
      loading: false,
    }
  })

  const rowNodeIndexes = new Map<number, number[]>()
  nodes.forEach((node, index) => {
    const indexes = rowNodeIndexes.get(node.row) ?? []
    indexes.push(index)
    rowNodeIndexes.set(node.row, indexes)
  })
  for (const indexes of rowNodeIndexes.values()) {
    indexes.sort((left, right) => (nodes[left]?.x ?? 0) - (nodes[right]?.x ?? 0))
    for (let index = 1; index < indexes.length; index += 1) {
      const previous = nodes[indexes[index - 1] ?? -1]
      const current = nodes[indexes[index] ?? -1]
      if (previous && current && current.x < previous.x + readyNodeSeparation) {
        current.x = previous.x + readyNodeSeparation
      }
    }
    const first = nodes[indexes[0] ?? -1]
    const last = nodes[indexes[indexes.length - 1] ?? -1]
    if (!first || !last) continue
    const rightOverflow = last.x + readyNodeSize - (readyGraphWidth - 8)
    if (rightOverflow > 0) {
      for (const index of indexes) {
        const node = nodes[index]
        if (node) node.x -= rightOverflow
      }
    }
    const leftOverflow = 8 - first.x
    if (leftOverflow > 0) {
      for (const index of indexes) {
        const node = nodes[index]
        if (node) node.x += leftOverflow
      }
    }
  }

  const byId = new Map(nodes.map((node) => [node.id, node]))
  const edges: TalentGraphEdgeView[] = []
  for (const node of nodes) {
    for (const parentId of node.prerequisiteIds) {
      const parent = byId.get(parentId)
      if (!parent) continue
      const state = parent.rank > 0 && node.rank > 0
        ? 'selected'
        : node.state === 'available'
          ? 'available'
          : 'blocked'
      edges.push(edgeGeometry(
        `${parentId}->${node.id}`,
        parentId,
        node.id,
        parent.x,
        parent.y,
        node.x,
        node.y,
        readyNodeSize / 2,
        state,
      ))
    }
  }

  return {
    nodes,
    edges,
    planeWidth: readyGraphWidth,
    planeHeight: Math.max(314, graphPad * 2 + (maxRow - 1) * readyRowGap + readyNodeSize),
    columnCount,
    nodeCount: nodes.length,
    uniquePositionCount: positionUse.size,
  }
}

function selectedDependentsRemainValid(
  nodeId: string,
  nodes: readonly TalentNode[],
  nextRanks: Readonly<Record<string, number>>,
): boolean {
  return nodes.every((candidate) => {
    if ((nextRanks[candidate.id] ?? 0) <= 0 || !candidate.prerequisiteIds?.includes(nodeId)) return true
    return prerequisitesMet(candidate, nextRanks)
  })
}

export function cycleTalentRank(input: {
  nodeId: string
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
  pointCap: number
}): Readonly<Record<string, number>> {
  const node = input.nodes.find((candidate) => candidate.id === input.nodeId)
  if (!node || node.granted) return input.ranks
  const current = Math.max(0, input.ranks[node.id] ?? 0)
  const maxRank = Math.max(1, finiteInteger(node.maxRank, 1))
  const spent = input.nodes.reduce((total, candidate) => total + Math.max(0, input.ranks[candidate.id] ?? 0), 0)

  if (current < maxRank) {
    if (!prerequisitesMet(node, input.ranks)) return input.ranks
    if (Math.max(0, finiteInteger(node.requiredPoints, 0)) > spent) return input.ranks
    if (spent >= input.pointCap) return input.ranks
    return { ...input.ranks, [node.id]: current + 1 }
  }

  const next = { ...input.ranks, [node.id]: 0 }
  return selectedDependentsRemainValid(node.id, input.nodes, next) ? next : input.ranks
}
