const DEFAULT_POINT_CAPS = {
  class: 34,
  spec: 34,
  hero: 13
}

function numberValue(value, fallback) {
  const next = Number(value)
  return Number.isFinite(next) ? next : fallback
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function nodeId(nodeOrId) {
  return typeof nodeOrId === 'string' ? nodeOrId : (nodeOrId && nodeOrId.id) || ''
}

function treeKeyFor(node) {
  if (!node) return 'spec'
  return node.treeType || node.tree || node.treeId || (node.specKey === 'class' ? 'class' : 'spec')
}

function maxRankFor(node) {
  return Math.max(1, numberValue(node && (node.maxRank || node.rank), 1))
}

function nodeById(nodes, id) {
  return (nodes || []).find((item) => item && item.id === id) || null
}

function grantedRankFor(node, baseTalentRanks) {
  if (!node || !node.id) return 0
  const payload = node.payload || {}
  const nodeGrantedRank = node.grantedRank != null ? node.grantedRank : (node.freeRank != null ? node.freeRank : node.baselineRank)
  const payloadGrantedRank = payload.grantedRank != null ? payload.grantedRank : (payload.freeRank != null ? payload.freeRank : payload.baselineRank)
  const explicit = Math.max(
    numberValue(baseTalentRanks && baseTalentRanks[node.id], 0),
    numberValue(nodeGrantedRank, 0),
    numberValue(payloadGrantedRank, 0)
  )
  const legacy = node.granted || node.free || payload.granted || payload.free
    ? numberValue(node.selectedRank || payload.selectedRank, 1)
    : 0
  return clamp(Math.max(explicit, legacy), 0, maxRankFor(node))
}

function rankFor(nodeOrId, talentRanks, nodes, baseTalentRanks) {
  const id = nodeId(nodeOrId)
  if (!id) return 0
  const node = typeof nodeOrId === 'string' ? nodeById(nodes, id) : nodeOrId
  const rank = Math.max(0, numberValue(talentRanks && talentRanks[id], 0), grantedRankFor(node, baseTalentRanks))
  return node ? clamp(rank, 0, maxRankFor(node)) : rank
}

function initialTalentRanks(nodes, options) {
  const talentRanks = {}
  const baseTalentRanks = {}

  ;(nodes || []).forEach((node) => {
    if (!node || !node.id) return
    const baseRank = grantedRankFor(node, {})
    const selectedRank = clamp(numberValue(node.selectedRank || (node.selected ? 1 : 0), 0), baseRank, maxRankFor(node))
    const rank = Math.max(baseRank, selectedRank)
    if (baseRank > 0) baseTalentRanks[node.id] = baseRank
    if (rank > 0) talentRanks[node.id] = rank
  })

  return {
    talentRanks,
    baseTalentRanks,
    pointCaps: Object.assign({}, DEFAULT_POINT_CAPS, (options && options.pointCaps) || {})
  }
}

function pointRequirementFor(node) {
  const value = node && (node.pointRequirement != null ? node.pointRequirement : node.requiredPoints)
  return Math.max(0, numberValue(value, 0))
}

function talentPoints(treeKey, nodes, talentRanks, baseTalentRanks, exceptIds) {
  const excluded = new Set(exceptIds || [])
  return (nodes || [])
    .filter((node) => treeKeyFor(node) === treeKey && !excluded.has(node.id))
    .reduce((total, node) => total + rankFor(node, talentRanks, nodes, baseTalentRanks), 0)
}

function parentIdsFor(node) {
  const ids = node && (node.parentIds || node.requiredIds || node.parents)
  return Array.isArray(ids) ? ids.filter(Boolean) : []
}

function parentsSatisfied(node, nodes, talentRanks, baseTalentRanks) {
  return parentIdsFor(node).every((id) => rankFor(id, talentRanks, nodes, baseTalentRanks) > 0)
}

function pointRequirementSatisfied(node, nodes, talentRanks, baseTalentRanks) {
  const requirement = pointRequirementFor(node)
  return requirement <= 0 || talentPoints(treeKeyFor(node), nodes, talentRanks, baseTalentRanks, [node.id]) >= requirement
}

function choiceGroupNodes(node, nodes) {
  if (!node || !node.choiceGroup) return []
  return (nodes || [])
    .filter((item) => item && item.choiceGroup === node.choiceGroup && treeKeyFor(item) === treeKeyFor(node))
    .sort((left, right) =>
      numberValue(left.row, 0) - numberValue(right.row, 0)
      || numberValue(left.col, 0) - numberValue(right.col, 0)
      || String(left.id || '').localeCompare(String(right.id || ''))
    )
}

function selectedChoicePeerFor(node, nodes, talentRanks, baseTalentRanks) {
  return choiceGroupNodes(node, nodes).find((item) => item.id !== node.id && rankFor(item, talentRanks, nodes, baseTalentRanks) > 0) || null
}

function setRank(nextRanks, node, rank, baseTalentRanks) {
  const next = clamp(numberValue(rank, 0), grantedRankFor(node, baseTalentRanks), maxRankFor(node))
  if (next > 0) nextRanks[node.id] = next
  else delete nextRanks[node.id]
}

function pointCapFor(node, pointCaps) {
  const treeKey = treeKeyFor(node)
  const cap = numberValue((pointCaps || {})[treeKey], DEFAULT_POINT_CAPS[treeKey] || 0)
  return cap > 0 ? cap : 0
}

function pointCapReached(node, nodes, talentRanks, baseTalentRanks, pointCaps) {
  const cap = pointCapFor(node, pointCaps)
  return cap > 0 && talentPoints(treeKeyFor(node), nodes, talentRanks, baseTalentRanks, [node.id]) >= cap
}

function pruneInvalidRanks(nodes, talentRanks, baseTalentRanks, preferredId) {
  const nextRanks = Object.assign({}, talentRanks || {})
  let changed = true
  while (changed) {
    changed = false
    ;(nodes || []).forEach((node) => {
      if (!node || !node.id) return
      const floor = grantedRankFor(node, baseTalentRanks)
      const current = rankFor(node, nextRanks, nodes, baseTalentRanks)
      if (current > floor && (!parentsSatisfied(node, nodes, nextRanks, baseTalentRanks) || !pointRequirementSatisfied(node, nodes, nextRanks, baseTalentRanks))) {
        setRank(nextRanks, node, floor, baseTalentRanks)
        changed = true
      }
    })

    const selectedGroups = new Map()
    ;(nodes || []).forEach((node) => {
      if (!node || !node.choiceGroup || rankFor(node, nextRanks, nodes, baseTalentRanks) <= 0) return
      const key = `${treeKeyFor(node)}:${node.choiceGroup}`
      const previousId = selectedGroups.get(key)
      if (!previousId) {
        selectedGroups.set(key, node.id)
        return
      }
      const previous = nodeById(nodes, previousId)
      const previousGranted = grantedRankFor(previous, baseTalentRanks) > 0
      const nodeGranted = grantedRankFor(node, baseTalentRanks) > 0
      const dropId = previousGranted && !nodeGranted
        ? node.id
        : nodeGranted && !previousGranted
          ? previousId
          : (preferredId && node.id === preferredId ? previousId : node.id)
      const dropNode = nodeById(nodes, dropId)
      setRank(nextRanks, dropNode, grantedRankFor(dropNode, baseTalentRanks), baseTalentRanks)
      selectedGroups.set(key, dropId === previousId ? node.id : previousId)
      changed = true
    })
  }
  Object.keys(baseTalentRanks || {}).forEach((id) => {
    const node = nodeById(nodes, id)
    if (node) setRank(nextRanks, node, baseTalentRanks[id], baseTalentRanks)
  })
  return nextRanks
}

function adjustTalentRank(context, id, delta) {
  const nodes = (context && context.nodes) || []
  const node = nodeById(nodes, id)
  const talentRanks = Object.assign({}, (context && context.talentRanks) || {})
  const baseTalentRanks = Object.assign({}, (context && context.baseTalentRanks) || {})
  const pointCaps = Object.assign({}, DEFAULT_POINT_CAPS, (context && context.pointCaps) || {})
  if (!node) return { changed: false, reason: 'missing_node', talentRanks }

  const current = rankFor(node, talentRanks, nodes, baseTalentRanks)
  const floor = grantedRankFor(node, baseTalentRanks)
  if (delta < 0 && current <= floor) {
    return { changed: false, reason: floor > 0 ? 'granted' : 'min_rank', talentRanks }
  }
  if (delta > 0 && floor > 0) return { changed: false, reason: 'granted', talentRanks }
  if (delta > 0 && current >= maxRankFor(node)) return { changed: false, reason: 'max_rank', talentRanks }
  if (delta > 0 && !parentsSatisfied(node, nodes, talentRanks, baseTalentRanks)) return { changed: false, reason: 'missing_parent', talentRanks }
  if (delta > 0 && !pointRequirementSatisfied(node, nodes, talentRanks, baseTalentRanks)) return { changed: false, reason: 'point_requirement', talentRanks }

  const selectedPeer = delta > 0 ? selectedChoicePeerFor(node, nodes, talentRanks, baseTalentRanks) : null
  if (delta > 0 && pointCapReached(node, nodes, talentRanks, baseTalentRanks, pointCaps) && !selectedPeer) {
    return { changed: false, reason: 'point_cap', talentRanks }
  }

  const nextRanks = Object.assign({}, talentRanks)
  if (delta > 0 && node.choiceGroup) {
    choiceGroupNodes(node, nodes)
      .filter((item) => item.id !== node.id)
      .forEach((item) => setRank(nextRanks, item, grantedRankFor(item, baseTalentRanks), baseTalentRanks))
  }
  setRank(nextRanks, node, current + delta, baseTalentRanks)
  const prunedRanks = pruneInvalidRanks(nodes, nextRanks, baseTalentRanks, id)
  return { changed: JSON.stringify(prunedRanks) !== JSON.stringify(talentRanks), reason: '', talentRanks: prunedRanks }
}

function tapTalentNode(context, id) {
  const node = nodeById((context && context.nodes) || [], id)
  if (!node) return { changed: false, reason: 'missing_node', talentRanks: (context && context.talentRanks) || {} }
  const rank = rankFor(node, context.talentRanks, context.nodes, context.baseTalentRanks)
  const maxRank = maxRankFor(node)
  const delta = maxRank === 1 && rank > 0 ? -1 : 1
  return adjustTalentRank(context, id, delta)
}

function selectedTalentEntries(nodes, talentRanks, baseTalentRanks) {
  return (nodes || [])
    .map((node) => ({
      id: node.id,
      rank: rankFor(node, talentRanks, nodes, baseTalentRanks),
      tree: treeKeyFor(node),
      name: node.name || node.id
    }))
    .filter((item) => item.id && item.rank > 0)
    .sort((left, right) => left.id.localeCompare(right.id))
}

function buildTalentExportCode(options) {
  const ranks = options && options.talentRanks ? options.talentRanks : {}
  const entries = Object.keys(ranks)
    .filter((id) => Number(ranks[id]) > 0)
    .sort()
    .map((id) => `${id}:${Math.max(1, Math.floor(Number(ranks[id]) || 1))}`)
    .join(',')
  return `websim:${options.classKey || ''}:${options.specKey || ''}:${options.heroKey || ''}:${entries}`
}

function parseTalentExportCode(value) {
  const text = String(value || '').trim()
  if (!text.startsWith('websim:')) return null
  const parts = text.split(':')
  if (parts.length < 5) return null
  const [rankPayload] = parts.slice(4).join(':').split(';')
  const talentRanks = {}
  rankPayload.split(',').forEach((entry) => {
    const [id, rank] = entry.split(':')
    if (!id) return
    const nextRank = Math.max(1, Math.floor(Number(rank || 1) || 1))
    talentRanks[id] = nextRank
  })
  return {
    classKey: parts[1] || '',
    specKey: parts[2] || '',
    heroKey: parts[3] || '',
    talentRanks
  }
}

function treeMetrics(nodes) {
  return {
    cols: Math.max(4, ...(nodes || []).map((node) => numberValue(node.col, 1))),
    rows: Math.max(4, ...(nodes || []).map((node) => numberValue(node.row, 1)))
  }
}

function linkFor(from, to, metrics) {
  const cols = Math.max(1, metrics.cols)
  const rows = Math.max(1, metrics.rows)
  return {
    from: from.id,
    to: to.id,
    x1: ((numberValue(from.col, 1) - 0.5) / cols) * 100,
    y1: ((numberValue(from.row, 1) - 0.5) / rows) * 100,
    x2: ((numberValue(to.col, 1) - 0.5) / cols) * 100,
    y2: ((numberValue(to.row, 1) - 0.5) / rows) * 100
  }
}

function defaultTreeSections() {
  return [
    { key: 'class', title: '职业天赋', pointCap: DEFAULT_POINT_CAPS.class },
    { key: 'spec', title: '专精天赋', pointCap: DEFAULT_POINT_CAPS.spec },
    { key: 'hero', title: '英雄天赋', pointCap: DEFAULT_POINT_CAPS.hero }
  ]
}

function nodeReason(node, nodes, talentRanks, baseTalentRanks, pointCaps) {
  if (rankFor(node, talentRanks, nodes, baseTalentRanks) >= maxRankFor(node)) return ''
  if (grantedRankFor(node, baseTalentRanks) > 0) return 'granted'
  if (!parentsSatisfied(node, nodes, talentRanks, baseTalentRanks)) return 'missing_parent'
  if (!pointRequirementSatisfied(node, nodes, talentRanks, baseTalentRanks)) return 'point_requirement'
  if (pointCapReached(node, nodes, talentRanks, baseTalentRanks, pointCaps) && !selectedChoicePeerFor(node, nodes, talentRanks, baseTalentRanks)) return 'point_cap'
  return ''
}

function buildTalentViewModel(options) {
  const nodes = Array.isArray(options && options.nodes) ? options.nodes : []
  const talentRanks = (options && options.talentRanks) || {}
  const baseTalentRanks = (options && options.baseTalentRanks) || {}
  const pointCaps = Object.assign({}, DEFAULT_POINT_CAPS, (options && options.pointCaps) || {})
  const sections = (Array.isArray(options && options.treeSections) && options.treeSections.length ? options.treeSections : defaultTreeSections())
  const searchTerm = String((options && options.searchTerm) || '').trim().toLowerCase()
  const groups = nodes.reduce((acc, node) => {
    const key = treeKeyFor(node)
    if (!acc[key]) acc[key] = []
    acc[key].push(node)
    return acc
  }, {})
  const searchMatches = []

  const viewSections = sections.map((section) => {
    const key = section.key || section.tree || 'spec'
    const sectionNodes = (groups[key] || []).slice().sort((left, right) =>
      numberValue(left.row, 0) - numberValue(right.row, 0)
      || numberValue(left.col, 0) - numberValue(right.col, 0)
      || String(left.id || '').localeCompare(String(right.id || ''))
    )
    const metrics = treeMetrics(sectionNodes)
    const nodeMap = new Map(sectionNodes.map((node) => [node.id, node]))
    const links = []
    const visualNodes = sectionNodes.map((node) => {
      const rank = rankFor(node, talentRanks, nodes, baseTalentRanks)
      const maxRank = maxRankFor(node)
      const reason = nodeReason(node, nodes, talentRanks, baseTalentRanks, pointCaps)
      const searchText = `${node.name || ''} ${node.id || ''}`.toLowerCase()
      const searchMatch = Boolean(searchTerm && searchText.includes(searchTerm))
      if (searchMatch) searchMatches.push(node.id)
      return {
        ...node,
        tree: key,
        rank,
        maxRank,
        selected: rank > 0,
        granted: grantedRankFor(node, baseTalentRanks) > 0,
        locked: Boolean(reason && reason !== 'granted'),
        lockReason: reason,
        choice: Boolean(node.choiceGroup),
        firstLetter: String(node.name || node.id || '?').slice(0, 1).toUpperCase(),
        leftPercent: ((numberValue(node.col, 1) - 0.5) / metrics.cols) * 100,
        topPercent: ((numberValue(node.row, 1) - 0.5) / metrics.rows) * 100,
        searchMatch,
        searchDimmed: Boolean(searchTerm && !searchMatch)
      }
    })
    sectionNodes.forEach((node) => {
      parentIdsFor(node).forEach((parentId) => {
        const parent = nodeMap.get(parentId)
        if (parent) links.push(linkFor(parent, node, metrics))
      })
    })
    return {
      ...section,
      key,
      pointCap: pointCaps[key] || section.pointCap || 0,
      pointCount: talentPoints(key, nodes, talentRanks, baseTalentRanks),
      metrics,
      nodes: visualNodes,
      links
    }
  })

  return {
    sections: viewSections,
    selectedNodes: selectedTalentEntries(nodes, talentRanks, baseTalentRanks),
    searchMatches,
    websimExportCode: buildTalentExportCode({
      classKey: (options && options.classKey) || '',
      specKey: (options && options.specKey) || '',
      heroKey: (options && options.heroKey) || '',
      talentRanks
    })
  }
}

module.exports = {
  DEFAULT_POINT_CAPS,
  adjustTalentRank,
  buildTalentExportCode,
  buildTalentViewModel,
  choiceGroupNodes,
  defaultTreeSections,
  grantedRankFor,
  initialTalentRanks,
  maxRankFor,
  parentsSatisfied,
  parseTalentExportCode,
  pointCapReached,
  pointRequirementSatisfied,
  rankFor,
  selectedChoicePeerFor,
  selectedTalentEntries,
  tapTalentNode,
  talentPoints,
  treeKeyFor
}
