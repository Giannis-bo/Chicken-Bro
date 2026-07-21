import type {
  CommunityTemplateReference,
  HeroTalentTree,
  ReadinessState,
  TalentNode,
  TalentNodeAvailabilityPayload,
  TalentValidationPayload,
  TalentTreeSection,
  WebsimBootstrapPayload,
  WebsimSelection,
  WebsimTalentsPayload,
} from '@wow-mini/domain'

export function defaultTalentTemplateTitle(input: {
  classLabel: string
  specLabel: string
  heroLabel: string
  now?: Date
}): string {
  const now = input.now ?? new Date()
  const date = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
    .map((value) => String(value).padStart(2, '0'))
    .join('-')
  const time = [now.getHours(), now.getMinutes()]
    .map((value) => String(value).padStart(2, '0'))
    .join(':')
  return [input.classLabel, input.specLabel, input.heroLabel, `${date} ${time}`]
    .map((value) => value.trim())
    .filter(Boolean)
    .join('-')
}

const communityTalentRegionLabels: Readonly<Record<string, string>> = {
  cn: '国服',
  eu: '欧服',
  us: '美服',
  kr: '韩服',
  tw: '台服',
}

export function communityTalentRegionLabel(region: string | undefined): string {
  const normalized = region?.trim().toLowerCase() ?? ''
  if (!normalized) return '未提供'
  return communityTalentRegionLabels[normalized] ?? normalized.toUpperCase()
}

export function communityTalentTemplateHasPlayerChoices(
  template: Pick<CommunityTemplateReference, 'talentState'>,
): boolean {
  return (template.talentState?.selectedNodes.filter((node) => node.rank > 0).length ?? 0) > 1
}

export function communityTalentWinnerForImport(
  templates: readonly CommunityTemplateReference[],
  heroKey = '',
  preferredTemplateId = '',
): CommunityTemplateReference | undefined {
  const normalizedHeroKey = heroKey.trim()
  const candidates = templates.filter((template) => (
    template.status === 'verified'
    && template.canApplyVisual === true
    && (!normalizedHeroKey || template.heroKey === normalizedHeroKey)
    && (template.talentState?.selectedNodes.length ?? 0) > 0
  ))
  const normalizedTemplateId = preferredTemplateId.trim()
  if (normalizedTemplateId) return candidates.find((template) => template.id === normalizedTemplateId)
  return candidates[0]
}

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

type TalentGraphLayoutMode = 'source_lattice' | 'centered_rows'

export interface TalentPointView {
  cap: number
  spent: number
  remaining: number
}

const loadingGraphWidth = 350
const loadingGraphHeight = 300
const loadingNodeSize = 30
const readyGraphWidth = 350
const readyNodeSize = 36
const readyGraphPad = 18
const readyRowGap = 48
const readyNodeSeparation = 52
const expandedViewportNodeSeparation = 74.5
const expandedHeroViewportNodeSeparation = 90
const readyGraphViewportHeight = 461
const readyGraphViewportInset = 8
const readyGraphContentWidth = readyGraphWidth - readyGraphViewportInset * 2
const readyGraphContentHeight = readyGraphViewportHeight - readyGraphViewportInset * 2
const minReadyRowGap = 38
const maxReadyRowGap = 52
const maxExpandedHeroRowGap = 96
const sourceLatticeMinimumRowGap = 60
const choiceNodeHorizontalRadius = 25
const choiceNodeVerticalRadius = 20
const linkVisibleGap = 0
const linkArrowHead = 6

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

function greatestCommonDivisor(left: number, right: number): number {
  let dividend = Math.abs(left)
  let divisor = Math.abs(right)
  while (divisor > 0) {
    const remainder = dividend % divisor
    dividend = divisor
    divisor = remainder
  }
  return dividend
}

function rowGapForExpandedViewport(
  maxRow: number,
  nodeBoundsWidth: number,
  maximumRowGap = maxReadyRowGap,
  minimumRowGap = minReadyRowGap,
): number {
  if (maxRow <= 1) return readyRowGap
  const widthScale = Math.min(1, readyGraphContentWidth / nodeBoundsWidth)
  const idealRowGap = (readyGraphContentHeight / widthScale - readyNodeSize) / (maxRow - 1)
  return Math.max(minimumRowGap, Math.min(maximumRowGap, idealRowGap))
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

export function heroTalentOptions(
  bootstrap: WebsimBootstrapPayload | undefined,
  selection: Pick<WebsimSelection, 'classKey' | 'specKey'> | undefined,
): readonly HeroTalentTree[] {
  if (!bootstrap || !selection) return []
  const classMeta = bootstrap.classes.find((item) => item.key === selection.classKey)
  const specMeta = classMeta?.specs?.find((item) => item.key === selection.specKey)
  return specMeta?.heroTrees?.length
    ? specMeta.heroTrees
    : classMeta?.heroTrees ?? []
}

export function heroTalentIcon(nodes: readonly TalentNode[]): string | undefined {
  return [...nodes]
    .filter((node) => nodeTreeKey(node) === 'hero' && node.iconUrl)
    .sort((left, right) => (
      finiteInteger(left.row, Number.MAX_SAFE_INTEGER) - finiteInteger(right.row, Number.MAX_SAFE_INTEGER)
      || finiteInteger(left.column, Number.MAX_SAFE_INTEGER) - finiteInteger(right.column, Number.MAX_SAFE_INTEGER)
    ))[0]?.iconUrl
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

function nodeLinkRadius(
  node: Pick<TalentGraphNodeView, 'shape'>,
  deltaX: number,
  deltaY: number,
): number {
  if (node.shape !== 'choice') return readyNodeSize / 2
  const distance = Math.hypot(deltaX, deltaY)
  if (distance <= 0) return choiceNodeHorizontalRadius
  const unitX = Math.abs(deltaX) / distance
  const unitY = Math.abs(deltaY) / distance
  return 1 / Math.sqrt(
    (unitX * unitX) / (choiceNodeHorizontalRadius * choiceNodeHorizontalRadius)
      + (unitY * unitY) / (choiceNodeVerticalRadius * choiceNodeVerticalRadius),
  )
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
  const spent = nodes.reduce(
    (total, node) => total + Math.max(0, rankFor(node, ranks) - grantedRankFor(node)),
    0,
  )
  return { cap, spent, remaining: Math.max(0, cap - spent) }
}

function nodeState(
  node: TalentNode,
  ranks: Readonly<Record<string, number>>,
  interactive: boolean,
  availability: TalentNodeAvailabilityPayload | undefined,
): TalentGraphNodeState {
  if (rankFor(node, ranks) > 0) return 'selected'
  if (!interactive) return 'blocked'
  return availability?.nodes[node.id]?.state === 'available' ? 'available' : 'blocked'
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
    x,
    y,
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
      from.x + loadingNodeSize / 2,
      from.y + loadingNodeSize / 2,
      to.x + loadingNodeSize / 2,
      to.y + loadingNodeSize / 2,
      loadingNodeSize / 2,
      loadingNodeSize / 2,
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
  availability?: TalentNodeAvailabilityPayload
  routeState: ReadinessState
  loading?: boolean
  layoutMode?: TalentGraphLayoutMode
}): TalentGraphView {
  if (input.loading || input.nodes.length === 0) return buildLoadingGraph()

  const interactive = input.routeState === 'ready' || input.routeState === 'partial'
  const projection = projectTalentNodes(input.nodes, input.ranks)
  const projectedNodes = projection.nodes
  const columnCount = Math.max(
    1,
    ...projectedNodes.map((node) => Math.max(1, finiteInteger(node.column, 1))),
  )
  const maxRow = Math.max(
    1,
    ...projectedNodes.map((node) => Math.max(1, finiteInteger(node.row, 1))),
  )
  const positionCounts = new Map<string, number>()
  for (const node of projectedNodes) {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    const positionKey = `${row}:${column}`
    positionCounts.set(positionKey, (positionCounts.get(positionKey) ?? 0) + 1)
  }
  const projectedOrder = new Map(projectedNodes.map((node, index) => [node.id, index]))
  const nodes = projectedNodes.map((node): TalentGraphNodeView => {
    const row = Math.max(1, finiteInteger(node.row, 1))
    const column = Math.max(1, finiteInteger(node.column, 1))
    return {
      id: node.id,
      label: node.name,
      description: node.description ?? '',
      descriptionStatus: node.descriptionStatus ?? 'unknown',
      row,
      column,
      x: 0,
      y: 0,
      rank: rankFor(node, input.ranks),
      maxRank: nodeMaxRank(node),
      requiredPoints: Math.max(0, finiteInteger(node.requiredPoints, 0)),
      prerequisiteIds: node.prerequisiteIds ?? [],
      parentMode: node.parentMode ?? 'any',
      shape: nodeShape(node),
      choiceOptionIds: projection.choiceOptionIdsByNodeId.get(node.id) ?? [],
      granted: grantedRankFor(node) > 0,
      ...(node.iconUrl ? { iconUrl: node.iconUrl } : {}),
      state: nodeState(node, input.ranks, interactive, input.availability),
      loading: false,
    }
  })

  const nodesByRow = new Map<number, TalentGraphNodeView[]>()
  for (const node of nodes) {
    const row = nodesByRow.get(node.row) ?? []
    row.push(node)
    nodesByRow.set(node.row, row)
  }
  const widestRowNodeCount = Math.max(...[...nodesByRow.values()].map((row) => row.length))
  const isHeroTree = projectedNodes.length > 0 && projectedNodes.every((node) => nodeTreeKey(node) === 'hero')
  const expandsIntoMainViewport = isHeroTree || (maxRow >= 8 && widestRowNodeCount >= 5)
  if (input.layoutMode === 'centered_rows') {
    for (const row of nodesByRow.values()) {
      row.sort((left, right) => (
        left.column - right.column
        || (projectedOrder.get(left.id) ?? 0) - (projectedOrder.get(right.id) ?? 0)
      ))
      const intervalCount = row.length - 1
      const firstRadius = nodeLinkRadius(row[0]!, 1, 0)
      const lastRadius = nodeLinkRadius(row[row.length - 1]!, 1, 0)
      const maximumSeparation = expandsIntoMainViewport && row.length === widestRowNodeCount
        ? isHeroTree
          ? expandedHeroViewportNodeSeparation
          : expandedViewportNodeSeparation
        : readyNodeSeparation
      const centerGap = intervalCount === 0
        ? 0
        : Math.max(0, Math.min(
          maximumSeparation,
          (readyGraphWidth - firstRadius * 2) / intervalCount,
          (readyGraphWidth - lastRadius * 2) / intervalCount,
        ))
      for (const [index, node] of row.entries()) {
        node.x = (readyGraphWidth - readyNodeSize) / 2
          + (index - intervalCount / 2) * centerGap
      }
    }
  } else {
    const sourceColumns = [...new Set(nodes.map((node) => node.column))].sort((left, right) => left - right)
    const sourceColumnStep = Math.max(1, Math.min(
      2,
      sourceColumns.slice(1).reduce(
        (step, column, index) => greatestCommonDivisor(step, column - sourceColumns[index]!),
        0,
      ) || 1,
    ))
    const sourceColumnStart = sourceColumns[0] ?? 1
    const sourceColumnEnd = sourceColumns[sourceColumns.length - 1] ?? sourceColumnStart
    const sourceColumnSpan = Math.max(0, (sourceColumnEnd - sourceColumnStart) / sourceColumnStep)
    const maximumLaneGap = expandsIntoMainViewport
      ? isHeroTree
        ? expandedHeroViewportNodeSeparation
        : expandedViewportNodeSeparation
      : readyNodeSeparation
    const laneGap = sourceColumnSpan > 0
      ? Math.max(0, Math.min(
        maximumLaneGap,
        (readyGraphWidth - readyNodeSize) / sourceColumnSpan,
      ))
      : 0
    const sourceColumnCenter = (sourceColumnStart + sourceColumnEnd) / 2
    const nodesByPosition = new Map<string, TalentGraphNodeView[]>()
    for (const node of nodes) {
      const positionKey = `${node.row}:${node.column}`
      const positionedNodes = nodesByPosition.get(positionKey) ?? []
      positionedNodes.push(node)
      nodesByPosition.set(positionKey, positionedNodes)
    }
    const nodeCenters = new Map<string, number>()
    for (const positionedNodes of nodesByPosition.values()) {
      positionedNodes.sort((left, right) => (
        (projectedOrder.get(left.id) ?? 0) - (projectedOrder.get(right.id) ?? 0)
      ))
      const canonicalCenter = readyGraphWidth / 2
        + ((positionedNodes[0]!.column - sourceColumnCenter) / sourceColumnStep) * laneGap
      for (const [index, node] of positionedNodes.entries()) {
        nodeCenters.set(
          node.id,
          canonicalCenter + (index - (positionedNodes.length - 1) / 2) * readyNodeSeparation,
        )
      }
    }
    const hasChoiceFrame = nodes.some((node) => node.shape === 'choice')
    const horizontalInset = hasChoiceFrame ? 7 : 0
    const minimumNodeCenter = Math.min(...nodeCenters.values())
    const maximumNodeCenter = Math.max(...nodeCenters.values())
    const centerSpan = maximumNodeCenter - minimumNodeCenter
    const availableSpan = readyGraphWidth - readyNodeSize - horizontalInset * 2
    const requiresNormalization = centerSpan > availableSpan
    for (const node of nodes) {
      const center = nodeCenters.get(node.id) ?? readyGraphWidth / 2
      node.x = requiresNormalization
        ? horizontalInset + (center - minimumNodeCenter) * availableSpan / centerSpan
        : center - readyNodeSize / 2
    }
  }
  const minNodeX = Math.min(...nodes.map((node) => node.x))
  const maxNodeX = Math.max(...nodes.map((node) => node.x + readyNodeSize))
  const rowGap = expandsIntoMainViewport
    ? rowGapForExpandedViewport(
      maxRow,
      maxNodeX - minNodeX,
      input.layoutMode === 'source_lattice' && !isHeroTree
        ? sourceLatticeMinimumRowGap
        : isHeroTree ? maxExpandedHeroRowGap : maxReadyRowGap,
      input.layoutMode === 'source_lattice' ? sourceLatticeMinimumRowGap : minReadyRowGap,
    )
    : readyRowGap
  for (const node of nodes) {
    node.y = readyGraphPad + (node.row - 1) * rowGap
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
        parent.x + readyNodeSize / 2,
        parent.y + readyNodeSize / 2,
        node.x + readyNodeSize / 2,
        node.y + readyNodeSize / 2,
        nodeLinkRadius(parent, node.x - parent.x, node.y - parent.y),
        nodeLinkRadius(node, parent.x - node.x, parent.y - node.y),
        state,
      ))
    }
  }

  return {
    nodes,
    edges,
    planeWidth: readyGraphWidth,
    planeHeight: Math.max(
      314,
      readyGraphPad * 2 + (maxRow - 1) * rowGap + readyNodeSize,
    ),
    columnCount,
    nodeCount: nodes.length,
    uniquePositionCount: positionCounts.size,
  }
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

export function proposeTalentRank(input: {
  nodeId: string
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
}): Readonly<Record<string, number>> {
  const node = input.nodes.find((candidate) => candidate.id === input.nodeId)
  if (!node) return input.ranks
  const current = rankFor(node, input.ranks)
  const floor = grantedRankFor(node)
  const maxRank = nodeMaxRank(node)
  const next = { ...input.ranks }
  setNodeRank(next, node, current < maxRank ? current + 1 : floor)
  return next
}

export function proposeTalentChoice(input: {
  nodeId: string
  nodes: readonly TalentNode[]
  ranks: Readonly<Record<string, number>>
}): Readonly<Record<string, number>> {
  const node = input.nodes.find((candidate) => candidate.id === input.nodeId)
  if (!node || !node.choiceGroup) return input.ranks
  const choices = choiceGroupNodes(node, input.nodes)
  if (choices.length < 2) return input.ranks

  const next = { ...input.ranks }
  for (const choice of choices) {
    const proposedRank = choice.id === node.id
      ? Math.max(1, grantedRankFor(choice))
      : grantedRankFor(choice)
    setNodeRank(next, choice, proposedRank)
  }
  return next
}

export interface TalentValidationDecision {
  accepted: boolean
  ranks: Readonly<Record<string, number>>
  error: string
}

function hasPresentationOnlyTalentBlockers(validation: TalentValidationPayload): boolean {
  const readiness = validation.talentReadiness
  if (!readiness
    || readiness.treeReady !== true
    || readiness.ruleReady !== true
    || readiness.encodingReady !== true
    || readiness.simcReady !== true
    || readiness.spellReady !== false) {
    return false
  }
  const readinessBlockers = new Set(readiness.blockers ?? [])
  return validation.blockers.length > 0
    && validation.blockers.every((blocker) => readinessBlockers.has(blocker))
}

export function applyTalentValidation(
  currentRanks: Readonly<Record<string, number>>,
  validation: TalentValidationPayload,
  fromFallback: boolean,
  transportError = '',
): TalentValidationDecision {
  const blockersAllowValidatedSelection = validation.blockers.length === 0
    || hasPresentationOnlyTalentBlockers(validation)
  const accepted = !fromFallback
    && validation.status === 'encoded'
    && validation.errors.length === 0
    && blockersAllowValidatedSelection
  if (accepted) {
    return {
      accepted: true,
      ranks: Object.fromEntries(validation.talentState.selectedNodes
        .filter((node) => node.id && node.rank > 0)
        .map((node) => [node.id, node.rank])),
      error: '',
    }
  }
  return {
    accepted: false,
    ranks: currentRanks,
    error: [transportError, ...validation.errors, ...validation.blockers].filter(Boolean).join(' / ')
      || '当前天赋修改未通过后端校验',
  }
}

export type FencedTalentSaveOutcome = 'completed' | 'blocked' | 'stale'

export async function runFencedTalentSave<TExport, TSaved>(input: {
  isCurrent(): boolean
  exportCurrent(): Promise<TExport | null>
  persist(exported: TExport): Promise<TSaved>
  complete(saved: TSaved): Promise<void> | void
}): Promise<FencedTalentSaveOutcome> {
  const exported = await input.exportCurrent()
  if (!input.isCurrent()) return 'stale'
  if (!exported) return 'blocked'
  const saved = await input.persist(exported)
  if (!input.isCurrent()) return 'stale'
  await input.complete(saved)
  return 'completed'
}
