const DEFAULT_POINT_CAPS = {
  class: 34,
  spec: 34,
  hero: 13
}
const TALENT_SCHEMA_REVISION = 'websim-talent-rules-v1'
const TALENT_GRID_WIDTH_RPX = 660
const TALENT_GRID_HEIGHTS_RPX = {
  class: 1080,
  spec: 1080,
  hero: 820
}
const TALENT_NODE_RADIUS_RPX = 32
const LINK_NODE_VISIBLE_GAP_RPX = 8
const LINK_ARROW_HEAD_RPX = 12
const LINK_NODE_START_CLEARANCE_RPX = TALENT_NODE_RADIUS_RPX + LINK_NODE_VISIBLE_GAP_RPX
const LINK_NODE_END_CLEARANCE_RPX = TALENT_NODE_RADIUS_RPX + LINK_NODE_VISIBLE_GAP_RPX + LINK_ARROW_HEAD_RPX

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

function normalizeTalentNodeShape(node) {
  if (!node) return 'square'
  const payload = node.payload || {}
  if (node.choiceGroup || payload.choiceGroup || node.nodeType === 2 || payload.nodeType === 2) return 'choice'
  const shape = String(
    node.shape ||
    payload.shape ||
    node.nodeShape ||
    payload.nodeShape ||
    ''
  ).trim().toLowerCase()
  if (shape === 'passive' || shape === 'round') return 'circle'
  if (shape === 'active' || shape === 'rect' || shape === 'rectangle') return 'square'
  if (shape === 'octagon') return 'choice'
  if (['circle', 'square', 'choice', 'apex'].includes(shape)) return shape
  return 'square'
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

function purchasedRankFor(nodeOrId, talentRanks, nodes, baseTalentRanks) {
  const id = nodeId(nodeOrId)
  if (!id) return 0
  const node = typeof nodeOrId === 'string' ? nodeById(nodes, id) : nodeOrId
  const selectedRank = rankFor(nodeOrId, talentRanks, nodes, baseTalentRanks)
  return Math.max(0, selectedRank - grantedRankFor(node, baseTalentRanks))
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

function talentPurchasedPoints(treeKey, nodes, talentRanks, baseTalentRanks, exceptIds) {
  const excluded = new Set(exceptIds || [])
  return (nodes || [])
    .filter((node) => treeKeyFor(node) === treeKey && !excluded.has(node.id))
    .reduce((total, node) => total + purchasedRankFor(node, talentRanks, nodes, baseTalentRanks), 0)
}

function pointsAvailableForRequirement(node, nodes, talentRanks, baseTalentRanks, exceptIds) {
  const key = treeKeyFor(node)
  if (key === 'hero') {
    return talentPoints(key, nodes, talentRanks, baseTalentRanks, exceptIds)
  }
  return talentPurchasedPoints(key, nodes, talentRanks, baseTalentRanks, exceptIds)
}

function parentIdsFor(node) {
  const ids = node && (node.parentIds || node.requiredIds || node.parents)
  return Array.isArray(ids) ? ids.filter(Boolean) : []
}

function parentModeFor(node) {
  const payload = (node && node.payload) || {}
  const mode = String((node && (node.parentMode || node.dependencyMode)) || payload.parentMode || payload.dependencyMode || '').toLowerCase()
  return mode === 'all' ? 'all' : 'any'
}

function parentRequirementSatisfied(parentId, nodes, talentRanks, baseTalentRanks) {
  const parent = nodeById(nodes, parentId)
  if (!parent) return false
  return rankFor(parent, talentRanks, nodes, baseTalentRanks) >= maxRankFor(parent)
}

function missingParentIdsFor(node, nodes, talentRanks, baseTalentRanks) {
  const parentIds = parentIdsFor(node)
  if (!parentIds.length) return []
  const selected = parentIds.filter((id) => parentRequirementSatisfied(id, nodes, talentRanks, baseTalentRanks))
  if (parentModeFor(node) === 'all') return parentIds.filter((id) => !selected.includes(id))
  return selected.length ? [] : parentIds
}

function parentsSatisfied(node, nodes, talentRanks, baseTalentRanks) {
  return missingParentIdsFor(node, nodes, talentRanks, baseTalentRanks).length === 0
}

function pointRequirementSatisfied(node, nodes, talentRanks, baseTalentRanks) {
  const requirement = pointRequirementFor(node)
  return requirement <= 0 || pointsAvailableForRequirement(node, nodes, talentRanks, baseTalentRanks, [node.id]) >= requirement
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
  return cap > 0 && talentPurchasedPoints(treeKeyFor(node), nodes, talentRanks, baseTalentRanks) >= cap
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
    if (node && numberValue(nextRanks[id], 0) < numberValue(baseTalentRanks[id], 0)) {
      setRank(nextRanks, node, baseTalentRanks[id], baseTalentRanks)
    }
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

function templatesForScenario(templates, scenarioKey) {
  const key = scenarioKey || 'mythic_plus'
  return (Array.isArray(templates) ? templates : []).filter((template) => {
    if (!template) return false
    const templateScenario = template.scenarioKey || template.scenario || 'mythic_plus'
    return templateScenario === key
  })
}

function talentRankSignature(ranks) {
  return Object.keys(ranks || {})
    .filter((id) => id && Number(ranks[id]) > 0)
    .sort()
    .map((id) => `${id}:${Math.max(1, Math.floor(Number(ranks[id]) || 1))}`)
    .join(',')
}

function selectedNodeRankSignature(template) {
  const state = template && typeof template.talentState === 'object' ? template.talentState : {}
  const selectedNodes = Array.isArray(state.selectedNodes)
    ? state.selectedNodes
    : (Array.isArray(template && template.selectedNodes) ? template.selectedNodes : [])
  const ranks = {}
  selectedNodes.forEach((node) => {
    const id = node && String(node.id || node.nodeId || node.key || '').trim()
    if (!id) return
    ranks[id] = Math.max(1, Math.floor(Number(node.rank || node.selectedRank || 1) || 1))
  })
  return talentRankSignature(ranks)
}

function communityTemplateSignature(template) {
  if (!template) return ''
  const parsed = parseTalentExportCode(template.websimExportCode)
  const parsedRanks = parsed ? talentRankSignature(parsed.talentRanks) : ''
  const selectedRanks = parsedRanks || selectedNodeRankSignature(template)
  const classKey = String(template.classKey || (parsed && parsed.classKey) || '').trim()
  const specKey = String(template.specKey || (parsed && parsed.specKey) || '').trim()
  const heroKey = String(template.heroKey || (parsed && parsed.heroKey) || '').trim()
  if (selectedRanks) return ['visual', classKey, specKey, heroKey, selectedRanks].join('|')
  const rawImportCode = String(template.rawImportCode || '').replace(/\s+/g, '').trim()
  if (rawImportCode) return ['raw', classKey, specKey, heroKey, rawImportCode].join('|')
  return `id|${template.id || ''}`
}

function communityTemplatePublicIdentity(template) {
  if (!template) return ''
  const parsed = parseTalentExportCode(template.websimExportCode)
  const classKey = String(template.classKey || (parsed && parsed.classKey) || '').trim()
  const specKey = String(template.specKey || (parsed && parsed.specKey) || '').trim()
  const heroKey = String(template.heroKey || (parsed && parsed.heroKey) || '').trim()
  const sourceKey = String(template.sourceKey || '').trim().toLowerCase()
  const playerId = String(template.playerId || '').trim()
  const visibleName = playerId || String(template.name || template.id || '').trim()
  const scenarioKey = String(template.scenarioKey || '').trim()
  return [sourceKey, visibleName.toLowerCase(), classKey, specKey, heroKey, scenarioKey].join('|')
}

function communityTemplateQuality(template) {
  const updated = Date.parse((template && template.updatedAt) || '') || 0
  return {
    visual: template && template.canApplyVisual && template.websimExportCode ? 1 : 0,
    maxKeyLevel: Number(template && template.maxKeyLevel) || 0,
    sampleCount: Number(template && template.sampleCount) || 0,
    updated
  }
}

function compareCommunityTemplateQuality(left, right) {
  const leftQuality = communityTemplateQuality(left)
  const rightQuality = communityTemplateQuality(right)
  return rightQuality.visual - leftQuality.visual
    || rightQuality.maxKeyLevel - leftQuality.maxKeyLevel
    || rightQuality.sampleCount - leftQuality.sampleCount
    || rightQuality.updated - leftQuality.updated
    || String(left && left.id || '').localeCompare(String(right && right.id || ''))
}

function templatesForClass(templates, classKey, specKey, options = {}) {
  const key = String(classKey || '').trim()
  const spec = String(specKey || '').trim()
  const limit = Number(options.limit || 0) || 0
  const bySignature = new Map()
  ;(Array.isArray(templates) ? templates : []).forEach((template) => {
    if (!template) return
    const parsed = parseTalentExportCode(template.websimExportCode)
    const templateClass = String(template.classKey || (parsed && parsed.classKey) || '').trim()
    const templateSpec = String(template.specKey || (parsed && parsed.specKey) || '').trim()
    if (key && templateClass !== key) return
    if (spec && templateSpec !== spec) return
    const signature = communityTemplateSignature(template)
    const previous = bySignature.get(signature)
    if (!previous || compareCommunityTemplateQuality(template, previous) < 0) {
      bySignature.set(signature, template)
    }
  })
  const byIdentity = new Map()
  Array.from(bySignature.values()).forEach((template) => {
    const identity = communityTemplatePublicIdentity(template)
    const previous = byIdentity.get(identity)
    if (!previous || compareCommunityTemplateQuality(template, previous) < 0) {
      byIdentity.set(identity, template)
    }
  })
  const byHero = new Map()
  Array.from(byIdentity.values()).forEach((template) => {
    const parsed = parseTalentExportCode(template.websimExportCode)
    const heroKey = String(template.heroKey || (parsed && parsed.heroKey) || template.id || '').trim()
    const previous = byHero.get(heroKey)
    if (!previous || compareCommunityTemplateQuality(template, previous) < 0) {
      byHero.set(heroKey, template)
    }
  })
  const result = Array.from(byHero.values()).sort(compareCommunityTemplateQuality)
  return limit > 0 ? result.slice(0, limit) : result
}

function communityTemplateApplyMode(template) {
  if (!template) return 'blocked'
  if (template.status === 'pending_collection' || template.sourceStatus === 'pending_collection') return 'blocked'
  if (template.canApplyVisual && template.websimExportCode) return 'visual'
  if (template.rawImportCode || template.canUseInSimc) return 'simc_only'
  return 'blocked'
}

function communityTemplateStatusText(syncState) {
  const status = (syncState && syncState.sourceStatus) || 'missing_credentials'
  if (status === 'synced') return '社区模板已同步'
  if (status === 'partial') {
    const sources = (syncState && syncState.sources) || {}
    const missing = Object.keys(sources)
      .filter((key) => sources[key] && sources[key].status === 'missing_credentials')
      .map((key) => {
        if (key === 'raiderio') return 'Raider.IO'
        if (key === 'warcraftlogs') return 'Warcraft Logs'
        return key
      })
    return missing.length
      ? `待补齐 ${missing.join('、')}，当前展示已验证样本`
      : '社区模板已部分同步'
  }
  if (status === 'blocked') return '社区模板同步被阻断'
  return '缺少社区模板 API 凭据'
}

function gridHeightForKey(key) {
  return TALENT_GRID_HEIGHTS_RPX[key] || TALENT_GRID_HEIGHTS_RPX.spec
}

function treeMetrics(nodes, key) {
  return {
    cols: Math.max(4, ...(nodes || []).map((node) => numberValue(node.col, 1))),
    rows: Math.max(4, ...(nodes || []).map((node) => numberValue(node.row, 1))),
    widthRpx: TALENT_GRID_WIDTH_RPX,
    heightRpx: gridHeightForKey(key)
  }
}

function nodeCenterFor(node, metrics) {
  const xRpx = ((numberValue(node.col, 1) - 0.5) / metrics.cols) * metrics.widthRpx
  const yRpx = ((numberValue(node.row, 1) - 0.5) / metrics.rows) * metrics.heightRpx
  return {
    xRpx,
    yRpx,
    xPercent: (xRpx / metrics.widthRpx) * 100,
    yPercent: (yRpx / metrics.heightRpx) * 100
  }
}

function linkFor(from, to, metrics) {
  const fromCenter = nodeCenterFor(from, metrics)
  const toCenter = nodeCenterFor(to, metrics)
  const dx = toCenter.xRpx - fromCenter.xRpx
  const dy = toCenter.yRpx - fromCenter.yRpx
  const distance = Math.sqrt(dx * dx + dy * dy) || 1
  const ux = dx / distance
  const uy = dy / distance
  let startClearance = LINK_NODE_START_CLEARANCE_RPX
  let endClearance = LINK_NODE_END_CLEARANCE_RPX
  if (distance <= startClearance + endClearance + 1) {
    const scale = Math.max(0, distance - 1) / (startClearance + endClearance)
    startClearance *= scale
    endClearance *= scale
  }
  const x1Rpx = fromCenter.xRpx + (ux * startClearance)
  const y1Rpx = fromCenter.yRpx + (uy * startClearance)
  const x2Rpx = toCenter.xRpx - (ux * endClearance)
  const y2Rpx = toCenter.yRpx - (uy * endClearance)
  return {
    from: from.id,
    to: to.id,
    x1: (x1Rpx / metrics.widthRpx) * 100,
    y1: (y1Rpx / metrics.heightRpx) * 100,
    x2: (x2Rpx / metrics.widthRpx) * 100,
    y2: (y2Rpx / metrics.heightRpx) * 100,
    x1Rpx,
    y1Rpx,
    x2Rpx,
    y2Rpx,
    lengthRpx: Math.sqrt((x2Rpx - x1Rpx) ** 2 + (y2Rpx - y1Rpx) ** 2),
    angleDeg: Math.atan2(y2Rpx - y1Rpx, x2Rpx - x1Rpx) * 180 / Math.PI
  }
}

function choiceSlotKey(node) {
  if (!node || !node.choiceGroup) return ''
  return [
    treeKeyFor(node),
    node.choiceGroup,
    numberValue(node.row, 0),
    numberValue(node.col, 0)
  ].join(':')
}

function visualNodesForSection(sectionNodes, nodes, talentRanks, baseTalentRanks) {
  const usedChoiceSlots = new Set()
  return (sectionNodes || []).reduce((acc, node) => {
    const slotKey = choiceSlotKey(node)
    if (!slotKey) {
      acc.push(node)
      return acc
    }
    if (usedChoiceSlots.has(slotKey)) return acc
    usedChoiceSlots.add(slotKey)
    const slotPeers = sectionNodes.filter((item) => choiceSlotKey(item) === slotKey)
    const selectedPeer = slotPeers.find((item) => rankFor(item, talentRanks, nodes, baseTalentRanks) > 0)
    acc.push(selectedPeer || node)
    return acc
  }, [])
}

function defaultTreeSections() {
  return [
    { key: 'class', title: '职业天赋', pointCap: DEFAULT_POINT_CAPS.class },
    { key: 'spec', title: '专精天赋', pointCap: DEFAULT_POINT_CAPS.spec },
    { key: 'hero', title: '英雄天赋', pointCap: DEFAULT_POINT_CAPS.hero }
  ]
}

function pointRequirementProgress(node, nodes, talentRanks, baseTalentRanks) {
  const requirement = pointRequirementFor(node)
  const available = pointsAvailableForRequirement(node, nodes, talentRanks, baseTalentRanks, [node.id])
  return {
    available,
    remaining: Math.max(0, requirement - available),
    requirement
  }
}

function unlockStepsFor(node, nodes, talentRanks, baseTalentRanks, pointCaps) {
  if (!node || rankFor(node, talentRanks, nodes, baseTalentRanks) >= maxRankFor(node)) return []
  const missingParents = missingParentIdsFor(node, nodes, talentRanks, baseTalentRanks)
  if (missingParents.length) {
    return missingParents.map((id) => {
      const parent = nodeById(nodes, id) || { id, name: id }
      return {
        key: `parent:${id}`,
        state: 'required',
        targetId: id,
        title: `先点亮 ${parent.name || id}`,
        detail: parentModeFor(node) === 'all' ? '需要同时满足此前置节点' : '满足任一前置路径即可'
      }
    })
  }
  if (!pointRequirementSatisfied(node, nodes, talentRanks, baseTalentRanks)) {
    const progress = pointRequirementProgress(node, nodes, talentRanks, baseTalentRanks)
    return [{
      key: `gate:${node.id}`,
      state: 'gate',
      targetId: '',
      title: '补足点数门槛',
      detail: `还差 ${progress.remaining} 点`,
      value: `${Math.min(progress.available, progress.requirement)}/${progress.requirement}`
    }]
  }
  if (pointCapReached(node, nodes, talentRanks, baseTalentRanks, pointCaps) && !selectedChoicePeerFor(node, nodes, talentRanks, baseTalentRanks)) {
    const cap = pointCapFor(node, pointCaps)
    return [{
      key: `cap:${treeKeyFor(node)}`,
      state: 'locked',
      targetId: '',
      title: '本树点数已达上限',
      detail: `${cap}/${cap}`
    }]
  }
  return []
}

function nodeReason(node, nodes, talentRanks, baseTalentRanks, pointCaps) {
  if (rankFor(node, talentRanks, nodes, baseTalentRanks) >= maxRankFor(node)) return ''
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
    const metrics = treeMetrics(sectionNodes, key)
    const visualSectionNodes = visualNodesForSection(sectionNodes, nodes, talentRanks, baseTalentRanks)
    const nodeMap = new Map(visualSectionNodes.map((node) => [node.id, node]))
    const links = []
    let searchMatchCount = 0
    const visualNodes = visualSectionNodes.map((node, nodeIndex) => {
      const rank = rankFor(node, talentRanks, nodes, baseTalentRanks)
      const maxRank = maxRankFor(node)
      const reason = nodeReason(node, nodes, talentRanks, baseTalentRanks, pointCaps)
      const nextUnlockSteps = unlockStepsFor(node, nodes, talentRanks, baseTalentRanks, pointCaps)
      const canSelect = rank < maxRank && !reason
      const shape = normalizeTalentNodeShape(node)
      const searchText = `${node.name || ''} ${node.id || ''}`.toLowerCase()
      const searchMatch = Boolean(searchTerm && searchText.includes(searchTerm))
      if (searchMatch) {
        searchMatches.push(node.id)
        searchMatchCount += 1
      }
      const center = nodeCenterFor(node, metrics)
      return {
        ...node,
        renderKey: `${key}:${node.id || 'node'}:${nodeIndex}`,
        tree: key,
        rank,
        maxRank,
        shape,
        selected: rank > 0,
        granted: grantedRankFor(node, baseTalentRanks) > 0,
        purchasedRank: purchasedRankFor(node, talentRanks, nodes, baseTalentRanks),
        canSelect,
        locked: Boolean(reason && reason !== 'granted'),
        lockReason: reason,
        nextUnlockSteps,
        choice: shape === 'choice',
        firstLetter: String(node.name || node.id || '?').slice(0, 1).toUpperCase(),
        leftPercent: center.xPercent,
        topPercent: center.yPercent,
        leftRpx: center.xRpx,
        topRpx: center.yRpx,
        searchMatch,
        searchDimmed: Boolean(searchTerm && !searchMatch)
      }
    })
    const visualStateById = new Map(visualNodes.map((node) => [node.id, node]))
    visualSectionNodes.forEach((node) => {
      parentIdsFor(node).forEach((parentId) => {
        const parent = nodeMap.get(parentId)
        if (parent) {
          const parentRank = rankFor(parent, talentRanks, nodes, baseTalentRanks)
          const nodeRank = rankFor(node, talentRanks, nodes, baseTalentRanks)
          const visualNode = visualStateById.get(node.id) || {}
          const active = parentRank > 0 && nodeRank > 0
          links.push({
            ...linkFor(parent, node, metrics),
            active,
            available: !active && parentRank > 0 && Boolean(visualNode.canSelect),
            renderKey: `${key}:${parentId}:${node.id}:${links.length}`
          })
        }
      })
    })
    return {
      ...section,
      key,
      pointCap: pointCaps[key] || section.pointCap || 0,
      pointCount: talentPurchasedPoints(key, nodes, talentRanks, baseTalentRanks),
      selectedPointCount: talentPoints(key, nodes, talentRanks, baseTalentRanks),
      schemaRevision: TALENT_SCHEMA_REVISION,
      searchMatchCount,
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
  LINK_NODE_END_CLEARANCE_RPX,
  LINK_NODE_START_CLEARANCE_RPX,
  TALENT_SCHEMA_REVISION,
  TALENT_GRID_HEIGHTS_RPX,
  TALENT_GRID_WIDTH_RPX,
  adjustTalentRank,
  buildTalentExportCode,
  buildTalentViewModel,
  choiceGroupNodes,
  communityTemplateApplyMode,
  communityTemplateStatusText,
  defaultTreeSections,
  grantedRankFor,
  initialTalentRanks,
  maxRankFor,
  parentModeFor,
  parentsSatisfied,
  parseTalentExportCode,
  pointCapReached,
  pointRequirementSatisfied,
  purchasedRankFor,
  rankFor,
  selectedChoicePeerFor,
  selectedTalentEntries,
  tapTalentNode,
  talentPurchasedPoints,
  templatesForClass,
  templatesForScenario,
  talentPoints,
  treeKeyFor
}
