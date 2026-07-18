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
  choiceOptionIds: readonly string[]
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

const loadingSourceWidth = 350
const loadingSourceHeight = 300
const loadingGraphWidth = 660
const loadingGraphHeight = 566
const loadingNodeRadius = 27
const talentGridWidth = 660
const talentGridHeights: Readonly<Record<string, number>> = {
  class: 1080,
  spec: 1080,
  hero: 820,
}
const talentNodeRadius = 32
const choiceNodeLinkRadius = 45
const readyMinimumGridDimension = 4
const choiceNodeSpread = 92
const linkVisibleGap = 8
const linkArrowHead = 12
const normalColumnGutter = 8
const choiceColumnGutter = 32
const treeHorizontalInset = 0

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

function nodeMaxRank(node: TalentNode): number {
  return Math.max(1, finiteInteger(node.maxRank, 1))
}

function grantedRankFor(node: TalentNode): number {
  const fallback = node.granted ? Math.max(1, finiteInteger(node.ranks, 1)) : 0
  return Math.min(nodeMaxRank(node), Math.max(0, finiteInteger(node.grantedRank, fallback)))
}

function rankFor(node: TalentNode, ranks: Readonly<Record<string, number>>): number {
  return Math.min(nodeMaxRank(node), Math.max(grantedRankFor(node), Math.max(0, ranks[node.id] ?? 0)))
}

function nodeTreeKey(node: TalentNode): string {
  return node.treeKey || node.treeType || 'class'
}

function nodeShape(node: TalentNode): string {
  if (node.choiceGroup || node.nodeType === 2) return 'choice'
  const shape = (node.shape ?? '').trim().toLowerCase()
  if (shape === 'passive' || shape === 'round') return 'circle'
  if (shape === 'active' || shape === 'rect' || shape === 'rectangle') return 'square'
  if (shape === 'octagon') return 'choice'
  if (shape === 'circle' || shape === 'square' || shape === 'choice' || shape === 'apex') return shape
  return 'square'
}

function nodeLinkRadius(node: Pick<TalentGraphNodeView, 'shape'>): number {
  return node.shape === 'choice' ? choiceNodeLinkRadius : talentNodeRadius
}

interface TalentGridMetrics {
  columnCount: number
  rowCount: number
  planeWidth: number
  planeHeight: number
  columnCenters: readonly number[]
}

function talentNodeColumn(node: TalentNode): number {
  return Math.max(1, finiteInteger(node.column, 1))
}

function talentNodeRow(node: TalentNode): number {
  return Math.max(1, finiteInteger(node.row, 1))
}

function talentNodeVisualRadius(node: TalentNode): number {
  return nodeShape(node) === 'choice' ? choiceNodeLinkRadius : talentNodeRadius
}

function talentColumnCenters(nodes: readonly TalentNode[], columnCount: number): readonly number[] {
  if (columnCount === 1) return [talentGridWidth / 2]

  const gaps = Array.from(
    { length: columnCount - 1 },
    () => talentNodeRadius * 2 + normalColumnGutter,
  )
  const nodesByRow = new Map<number, TalentNode[]>()
  for (const node of nodes) {
    const row = talentNodeRow(node)
    const rowNodes = nodesByRow.get(row) ?? []
    rowNodes.push(node)
    nodesByRow.set(row, rowNodes)
  }
  for (const rowNodes of nodesByRow.values()) {
    const ordered = [...rowNodes].sort((left, right) => talentNodeColumn(left) - talentNodeColumn(right))
    for (let index = 1; index < ordered.length; index += 1) {
      const left = ordered[index - 1]!
      const right = ordered[index]!
      const leftColumn = talentNodeColumn(left)
      if (talentNodeColumn(right) !== leftColumn + 1) continue
      const hasChoice = nodeShape(left) === 'choice' || nodeShape(right) === 'choice'
      const requiredGap = talentNodeVisualRadius(left)
        + talentNodeVisualRadius(right)
        + (hasChoice ? choiceColumnGutter : normalColumnGutter)
      gaps[leftColumn - 1] = Math.max(gaps[leftColumn - 1] ?? 0, requiredGap)
    }
  }

  const normalColumnGap = talentNodeRadius * 2 + normalColumnGutter
  if (!gaps.some((gap) => gap > normalColumnGap)) {
    return Array.from(
      { length: columnCount },
      (_, index) => ((index + 0.5) / columnCount) * talentGridWidth,
    )
  }

  const firstColumnNodes = nodes.filter((node) => talentNodeColumn(node) === 1)
  const lastColumnNodes = nodes.filter((node) => talentNodeColumn(node) === columnCount)
  const leftRadius = Math.max(talentNodeRadius, ...firstColumnNodes.map(talentNodeVisualRadius))
  const rightRadius = Math.max(talentNodeRadius, ...lastColumnNodes.map(talentNodeVisualRadius))
  const requiredWidth = leftRadius + rightRadius + treeHorizontalInset * 2
    + gaps.reduce((total, gap) => total + gap, 0)
  const extraPerGap = Math.max(0, talentGridWidth - requiredWidth) / gaps.length
  const centers = [treeHorizontalInset + leftRadius]
  for (const gap of gaps) {
    centers.push((centers.at(-1) ?? 0) + gap + extraPerGap)
  }
  return centers
}

function talentGridMetrics(nodes: readonly TalentNode[]): TalentGridMetrics {
  const columnCount = Math.max(
    readyMinimumGridDimension,
    ...nodes.map((node) => Math.max(1, finiteInteger(node.column, 1))),
  )
  const rowCount = Math.max(
    readyMinimumGridDimension,
    ...nodes.map((node) => Math.max(1, finiteInteger(node.row, 1))),
  )
  const treeKey = nodes[0] ? nodeTreeKey(nodes[0]) : 'spec'
  return {
    columnCount,
    rowCount,
    planeWidth: talentGridWidth,
    planeHeight: talentGridHeights[treeKey] ?? talentGridHeights['spec']!,
    columnCenters: talentColumnCenters(nodes, columnCount),
  }
}

function talentNodePosition(
  row: number,
  column: number,
  metrics: TalentGridMetrics,
): { x: number; y: number } {
  return {
    x: metrics.columnCenters[column - 1] ?? metrics.planeWidth / 2,
    y: ((row - 0.5) / metrics.rowCount) * metrics.planeHeight,
  }
}

function choiceSlotKey(node: TalentNode): string {
  if (!node.choiceGroup) return ''
  const row = Math.max(1, finiteInteger(node.row, 1))
  const column = Math.max(1, finiteInteger(node.column, 1))
  return `${nodeTreeKey(node)}:${node.choiceGroup}:${row}:${column}`
}

interface TalentNodeProjection {
  nodes: readonly TalentNode[]
  choiceOptionIdsByNodeId: ReadonlyMap<string, readonly string[]>
}

function projectTalentNodes(
  nodes: readonly TalentNode[],
  ranks: Readonly<Record<string, number>>,
): TalentNodeProjection {
  const candidatesBySlot = new Map<string, TalentNode[]>()
  for (const node of nodes) {
    const slotKey = choiceSlotKey(node)
    if (!slotKey) continue
    const candidates = candidatesBySlot.get(slotKey) ?? []
    candidates.push(node)
    candidatesBySlot.set(slotKey, candidates)
  }

  const emittedSlots = new Set<string>()
  const projectedNodes: TalentNode[] = []
  const choiceOptionIdsByNodeId = new Map<string, readonly string[]>()
  for (const node of nodes) {
    const slotKey = choiceSlotKey(node)
    if (!slotKey) {
      projectedNodes.push(node)
      continue
    }
    if (emittedSlots.has(slotKey)) continue
    emittedSlots.add(slotKey)
    const candidates = candidatesBySlot.get(slotKey) ?? [node]
    const visible = candidates.find((candidate) => rankFor(candidate, ranks) > 0) ?? candidates[0]!
    projectedNodes.push(visible)
    choiceOptionIdsByNodeId.set(visible.id, candidates.map((candidate) => candidate.id))
  }

  return { nodes: projectedNodes, choiceOptionIdsByNodeId }
}

export function initialTalentRanks(nodes: readonly TalentNode[]): Readonly<Record<string, number>> {
  return Object.fromEntries(nodes.flatMap((node) => {
    const rank = Math.max(grantedRankFor(node), Math.max(0, finiteInteger(node.ranks, 0)))
    return rank > 0 ? [[node.id, rank]] : []
  }))
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
  const spent = nodes.reduce((total, node) => total + rankFor(node, ranks), 0)
  return { cap, spent, remaining: Math.max(0, cap - spent) }
}

function prerequisitesMet(
  node: TalentNode,
  ranks: Readonly<Record<string, number>>,
): boolean {
  const parentIds = node.prerequisiteIds ?? []
  if (!parentIds.length) return true
  const parentRank = (id: string) => Math.max(0, ranks[id] ?? 0)
  if (node.parentMode === 'all') return parentIds.every((id) => parentRank(id) > 0)
  return parentIds.some((id) => parentRank(id) > 0)
}

function nodeState(
  node: TalentNode,
  ranks: Readonly<Record<string, number>>,
  spent: number,
  interactive: boolean,
): TalentGraphNodeState {
  if (rankFor(node, ranks) > 0) return 'selected'
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
  fromNodeRadius: number,
  toNodeRadius: number,
  state: TalentGraphEdgeView['state'],
): TalentGraphEdgeView {
  const dx = toX - fromX
  const dy = toY - fromY
  const distance = Math.hypot(dx, dy)
  if (distance <= 0) {
    return { id, fromId, toId, x: fromX, y: fromY, width: 0, angle: 0, state }
  }
  const unitX = dx / distance
  const unitY = dy / distance
  let startClearance = fromNodeRadius + linkVisibleGap
  let endClearance = toNodeRadius + linkVisibleGap + linkArrowHead
  if (distance <= startClearance + endClearance + 1) {
    const scale = Math.max(0, distance - 1) / (startClearance + endClearance)
    startClearance *= scale
    endClearance *= scale
  }
  return {
    id,
    fromId,
    toId,
    x: fromX + unitX * startClearance,
    y: fromY + unitY * startClearance,
    width: Math.max(0, distance - startClearance - endClearance),
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
    x: ((x + 15) / loadingSourceWidth) * loadingGraphWidth,
    y: ((y + 15) / loadingSourceHeight) * loadingGraphHeight,
    rank: 0,
    maxRank: 1,
    requiredPoints: 0,
    prerequisiteIds: [],
    parentMode: 'any',
    shape: index === 0 ? 'choice' : 'circle',
    choiceOptionIds: [],
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
      loadingNodeRadius,
      loadingNodeRadius,
      'loading',
    )
  })
  return {
    nodes,
    edges,
    planeWidth: loadingGraphWidth,
    planeHeight: loadingGraphHeight,
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
  const projection = projectTalentNodes(input.nodes, input.ranks)
  const projectedNodes = projection.nodes
  const grid = talentGridMetrics(projectedNodes)
  const positionCounts = new Map<string, number>()
  for (const node of projectedNodes) {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    const positionKey = `${row}:${column}`
    positionCounts.set(positionKey, (positionCounts.get(positionKey) ?? 0) + 1)
  }
  const spent = projectedNodes.reduce((total, node) => total + rankFor(node, input.ranks), 0)
  const positionUse = new Map<string, number>()
  const nodes = projectedNodes.map((node): TalentGraphNodeView => {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    const positionKey = `${row}:${column}`
    const duplicateIndex = positionUse.get(positionKey) ?? 0
    positionUse.set(positionKey, duplicateIndex + 1)
    const duplicateCount = positionCounts.get(positionKey) ?? 1
    const duplicateOffset = (duplicateIndex - (duplicateCount - 1) / 2) * choiceNodeSpread
    const position = talentNodePosition(row, column, grid)
    return {
      id: node.id,
      label: node.name,
      description: node.description ?? '',
      descriptionStatus: node.descriptionStatus ?? 'unknown',
      row,
      column,
      x: position.x + duplicateOffset,
      y: position.y,
      rank: rankFor(node, input.ranks),
      maxRank: nodeMaxRank(node),
      requiredPoints: Math.max(0, finiteInteger(node.requiredPoints, 0)),
      prerequisiteIds: node.prerequisiteIds ?? [],
      parentMode: node.parentMode ?? 'any',
      shape: nodeShape(node),
      choiceOptionIds: projection.choiceOptionIdsByNodeId.get(node.id) ?? [],
      granted: grantedRankFor(node) > 0,
      ...(node.iconUrl ? { iconUrl: node.iconUrl } : {}),
      state: nodeState(node, input.ranks, spent, interactive),
      loading: false,
    }
  })

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
        nodeLinkRadius(parent),
        nodeLinkRadius(node),
        state,
      ))
    }
  }

  return {
    nodes,
    edges,
    planeWidth: grid.planeWidth,
    planeHeight: grid.planeHeight,
    columnCount: grid.columnCount,
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
    if (rankFor(candidate, nextRanks) <= 0 || !candidate.prerequisiteIds?.includes(nodeId)) return true
    return prerequisitesMet(candidate, nextRanks)
  })
}

function setNodeRank(
  ranks: Record<string, number>,
  node: TalentNode,
  requestedRank: number,
): void {
  const rank = Math.min(nodeMaxRank(node), Math.max(grantedRankFor(node), requestedRank))
  if (rank > 0) ranks[node.id] = rank
  else delete ranks[node.id]
}

function choiceGroupNodes(node: TalentNode, nodes: readonly TalentNode[]): readonly TalentNode[] {
  if (!node.choiceGroup) return []
  return nodes.filter((candidate) => (
    candidate.choiceGroup === node.choiceGroup
    && nodeTreeKey(candidate) === nodeTreeKey(node)
  ))
}

function pruneInvalidRanks(
  nodes: readonly TalentNode[],
  ranks: Readonly<Record<string, number>>,
): Readonly<Record<string, number>> {
  const next = { ...ranks }
  let changed = true
  while (changed) {
    changed = false
    for (const node of nodes) {
      if (rankFor(node, next) <= grantedRankFor(node) || prerequisitesMet(node, next)) continue
      setNodeRank(next, node, grantedRankFor(node))
      changed = true
    }
  }
  return next
}

export function cycleTalentRank(input: {
  nodeId: string
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
  pointCap: number
}): Readonly<Record<string, number>> {
  const node = input.nodes.find((candidate) => candidate.id === input.nodeId)
  if (!node) return input.ranks
  const current = rankFor(node, input.ranks)
  const floor = grantedRankFor(node)
  const maxRank = nodeMaxRank(node)
  const spent = input.nodes.reduce((total, candidate) => total + rankFor(candidate, input.ranks), 0)

  if (current < maxRank) {
    if (!prerequisitesMet(node, input.ranks)) return input.ranks
    if (Math.max(0, finiteInteger(node.requiredPoints, 0)) > spent) return input.ranks
    if (spent >= input.pointCap) return input.ranks
    const next = { ...input.ranks }
    setNodeRank(next, node, current + 1)
    return next
  }

  if (current <= floor) return input.ranks
  const next = { ...input.ranks }
  setNodeRank(next, node, floor)
  return selectedDependentsRemainValid(node.id, input.nodes, next) ? next : input.ranks
}

export function selectTalentChoice(input: {
  nodeId: string
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
  pointCap: number
}): Readonly<Record<string, number>> {
  const node = input.nodes.find((candidate) => candidate.id === input.nodeId)
  if (!node || !node.choiceGroup || grantedRankFor(node) > 0) return input.ranks
  const choices = choiceGroupNodes(node, input.nodes)
  if (choices.length < 2 || rankFor(node, input.ranks) > 0) return input.ranks
  if (!prerequisitesMet(node, input.ranks)) return input.ranks

  const spent = input.nodes.reduce((total, candidate) => total + rankFor(candidate, input.ranks), 0)
  const switching = choices.some((candidate) => candidate.id !== node.id && rankFor(candidate, input.ranks) > 0)
  if (!switching && spent >= input.pointCap) return input.ranks

  const next = { ...input.ranks }
  for (const choice of choices) {
    setNodeRank(next, choice, choice.id === node.id ? 1 : grantedRankFor(choice))
  }
  return pruneInvalidRanks(input.nodes, next)
}
