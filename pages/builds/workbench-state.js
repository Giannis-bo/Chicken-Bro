const { specIconUrlFor } = require('../common/wow-spec-assets')

const scenarioOptions = [
  { key: 'single', title: '单体', desc: '固定单目标' },
  { key: 'aoe_5', title: '5目标', desc: '固定多目标' },
  { key: 'mythic_plus', title: '大秘境', desc: '近似地下城' }
]

const statusMeta = {
  ready_to_simulate: { label: '可提交模拟', tone: 'verified' },
  verified: { label: '已验证', tone: 'verified' },
  blocked: { label: '阻断', tone: 'blocked' },
  partial: { label: '部分可用', tone: 'partial' },
  stale: { label: '需刷新', tone: 'stale' },
  source_reference: { label: '来源参考', tone: 'source_reference' },
  loading: { label: '读取中', tone: 'source_reference' }
}

const gearSlotLabels = {
  head: '头部',
  neck: '颈部',
  shoulder: '肩部',
  back: '披风',
  chest: '胸部',
  wrist: '手腕',
  hands: '手',
  waist: '腰部',
  legs: '腿部',
  feet: '脚',
  finger1: '戒指 1',
  finger2: '戒指 2',
  trinket1: '饰品 1',
  trinket2: '饰品 2',
  main_hand: '主手',
  off_hand: '副手'
}

function cleanText(value) {
  return String(value || '').trim()
}

function asArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function firstNumber(...values) {
  for (const value of values) {
    const number = Number(value)
    if (Number.isFinite(number)) return number
  }
  return 0
}

function firstNonEmpty(...values) {
  for (const value of values) {
    const text = cleanText(value)
    if (text) return text
  }
  return ''
}

function toneForStatus(status) {
  return (statusMeta[status] || statusMeta.source_reference).tone
}

function labelForStatus(status) {
  return (statusMeta[status] || statusMeta.source_reference).label
}

function statusClass(status) {
  return `status-${toneForStatus(status)}`
}

function shortStatusLabel(status, statusLabel, key) {
  if (key === 'chickenbro' && cleanText(statusLabel) === '可解释证据') return '解释'
  const labels = {
    ready_to_simulate: '可提交',
    verified: '可用',
    blocked: '阻断',
    partial: '部分',
    stale: '刷新',
    source_reference: '参考',
    loading: '读取'
  }
  return labels[status] || cleanText(statusLabel).slice(0, 3) || '状态'
}

function moduleDockDesc(item) {
  const source = item || {}
  if (source.key === 'talents') {
    if (source.status === 'blocked') return '天赋需补齐'
    if (source.status === 'source_reference') return '等待天赋'
    return cleanText(source.desc).replace(/^可供 SimC · /, '') || source.metric || '待读取'
  }
  if (source.key === 'gear') {
    const missingCount = asArray(source.missingRequiredSlots).length
    if (missingCount) return `缺 ${missingCount} 项装备`
    return firstNonEmpty(source.metric, source.desc, '待读取')
  }
  if (source.key === 'simc') {
    return source.status === 'ready_to_simulate' ? '进入现有 SimC' : firstNonEmpty(source.desc, '待补齐')
  }
  if (source.key === 'chickenbro') {
    return source.status === 'source_reference' ? '等待证据' : '解释阻断和来源'
  }
  return firstNonEmpty(source.desc, source.metric, '待读取')
}

function evidenceValueLabel(value) {
  const text = cleanText(value)
  const labels = {
    simc: '可供 SimC',
    verified: '已验证',
    partial: '部分可用',
    blocked: '阻断',
    stale: '需刷新',
    source_reference: '来源参考',
    unknown: '未知'
  }
  return labels[text] || text || '未知'
}

function formatCount(current, total, unit) {
  const left = firstNumber(current)
  const right = firstNumber(total)
  if (!right) return left ? `${left}${unit || ''}` : '待读取'
  return `${left}/${right}${unit || ''}`
}

function checkedAtLabel(value) {
  const text = cleanText(value)
  if (!text) return '未记录'
  const date = new Date(text)
  if (Number.isFinite(date.getTime())) {
    const pad = (part) => String(part).padStart(2, '0')
    return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
  }
  return text.replace('T', ' ').replace(/([+-]\d{2}:\d{2}|Z)$/, '').slice(0, 16)
}

function isOlderThan(value, now, days) {
  const text = cleanText(value)
  if (!text) return false
  const timestamp = new Date(text).getTime()
  const current = now instanceof Date ? now.getTime() : Number(now || Date.now())
  if (!Number.isFinite(timestamp) || !Number.isFinite(current)) return false
  return current - timestamp > days * 24 * 60 * 60 * 1000
}

function selectedSpecLabel(selectedSpec) {
  const source = selectedSpec || {}
  const className = firstNonEmpty(source.className, source.classTitle, source.name)
  const specName = firstNonEmpty(source.specName, source.title)
  if (className && specName) return `${className} · ${specName}`
  return specName || className || '当前专精'
}

function selectedHeroLabel(selectedSpec, talentsPayload) {
  const source = selectedSpec || {}
  const heroSection = asArray(talentsPayload && talentsPayload.treeSections).find((item) => item && item.key === 'hero')
  return firstNonEmpty(
    source.heroLabel,
    source.heroName,
    talentsPayload && talentsPayload.heroName,
    talentsPayload && talentsPayload.heroLabel,
    heroSection && heroSection.title,
    source.heroKey,
    talentsPayload && talentsPayload.heroKey,
    '英雄天赋待选'
  )
}

function selectedScenarioLabel(scenarioKey) {
  const option = scenarioOptions.find((item) => item.key === scenarioKey)
  return option ? option.title : cleanText(scenarioKey) || scenarioOptions[0].title
}

function specMonogram(selectedSpec) {
  const source = selectedSpec || {}
  const className = firstNonEmpty(source.className, source.classTitle, source.name, '专')
  const specName = firstNonEmpty(source.specName, source.title, '精')
  return `${className.slice(0, 1)}${specName.slice(0, 1)}`
}

function selectedSpecIconUrl(selectedSpec) {
  const source = selectedSpec || {}
  const classKey = firstNonEmpty(source.websimClassKey, source.classKey)
  const specKey = firstNonEmpty(source.websimSpecKey, source.specKey)
  return firstNonEmpty(
    source.gameAsset && source.gameAsset.iconUrl,
    source.specIconUrl,
    source.iconUrl,
    specIconUrlFor(specKey, classKey)
  )
}

function missingSlotLabel(slot, gearPayload) {
  const slots = asArray(gearPayload && gearPayload.slots)
  const match = slots.find((item) => item && item.slot === slot)
  return cleanText(match && match.label) || gearSlotLabels[slot] || slot
}

function missingSlotSummary(labels) {
  const list = asArray(labels).map(cleanText).filter(Boolean)
  if (!list.length) return ''
  if (list.length <= 3) return `缺少${list.join('、')}`
  return `缺少 ${list.length} 个装备槽`
}

function missingSlotDetail(labels) {
  const list = asArray(labels).map(cleanText).filter(Boolean)
  if (!list.length) return ''
  if (list.length <= 3) return list.join('、')
  return `${list.slice(0, 3).join('、')}等 ${list.length} 项`
}

function firstTalentIcon(talentsPayload) {
  const prepared = talentsPayload && talentsPayload.firstTalentIcon
  if (prepared && (prepared.iconUrl || prepared.fallbackText)) {
    return {
      iconUrl: cleanText(prepared.iconUrl),
      fallbackText: cleanText(prepared.fallbackText) || '天'
    }
  }
  const node = asArray(talentsPayload && talentsPayload.nodes)
    .find((item) => item && item.gameAsset && item.gameAsset.iconUrl)
  if (!node) return { iconUrl: '', fallbackText: '天' }
  return {
    iconUrl: node.gameAsset.iconUrl,
    fallbackText: cleanText(node.gameAsset.fallbackText) || cleanText(node.name).slice(0, 1) || '天'
  }
}

function firstGearIcon(gearPayload) {
  const prepared = gearPayload && gearPayload.firstGearIcon
  if (prepared && (prepared.iconUrl || prepared.fallbackText)) {
    return {
      iconUrl: cleanText(prepared.iconUrl),
      fallbackText: cleanText(prepared.fallbackText) || '装'
    }
  }
  const equipped = Object.values((gearPayload && gearPayload.equippedSet) || {})
  const item = equipped.find((entry) => entry && entry.gameAsset && entry.gameAsset.iconUrl)
  if (!item) return { iconUrl: '', fallbackText: '装' }
  return {
    iconUrl: item.gameAsset.iconUrl,
    fallbackText: cleanText(item.gameAsset.fallbackText) || cleanText(item.displayName || item.name).slice(0, 1) || '装'
  }
}

function sourceCount(templates) {
  return asArray(templates).length
}

function realIdentityIcons(talentState, gearState) {
  return [
    {
      key: 'talent-icon',
      label: '天赋证据',
      iconUrl: talentState.iconUrl,
      fallbackText: talentState.iconFallback,
      statusClass: talentState.statusClass
    },
    {
      key: 'gear-icon',
      label: '装备证据',
      iconUrl: gearState.iconUrl,
      fallbackText: gearState.iconFallback,
      statusClass: gearState.statusClass
    }
  ].filter((item) => item.iconUrl)
}

function canonicalGearCounts(readiness, missingRequiredSlots) {
  const missingCount = asArray(missingRequiredSlots).length
  const rawSelectedCount = firstNumber(readiness && readiness.selectedCount)
  const rawSimcReadyCount = firstNumber(readiness && readiness.simcReadyCount, rawSelectedCount)
  const rawRequiredCount = firstNumber(
    readiness && readiness.requiredSlotCount,
    readiness && readiness.requiredCount,
    readiness && readiness.requiredReadyCount
  )
  const hasAnySignal = Boolean(
    missingCount ||
    rawSelectedCount ||
    rawSimcReadyCount ||
    rawRequiredCount ||
    (readiness && readiness.fullReady === true)
  )
  if (!hasAnySignal) {
    return {
      selectedCount: 0,
      simcReadyCount: 0,
      requiredCount: 0,
      readyCount: 0,
      metric: '待读取'
    }
  }
  const slotLimit = 16
  const maxReadyByMissing = Math.max(0, slotLimit - Math.min(missingCount, slotLimit))
  const selectedCount = Math.min(Math.max(rawSelectedCount, 0), slotLimit)
  const simcReadyCount = Math.min(Math.max(rawSimcReadyCount || selectedCount, 0), maxReadyByMissing)
  const readyCount = simcReadyCount || Math.min(selectedCount, maxReadyByMissing)
  const requiredCount = slotLimit
  return {
    selectedCount,
    simcReadyCount,
    requiredCount,
    readyCount,
    metric: readyCount || requiredCount ? formatCount(readyCount, requiredCount, ' 槽') : '待读取'
  }
}

function buildTalentState(talentsPayload, talentTemplates) {
  const source = talentsPayload || {}
  const readiness = source.talentReadiness || {}
  const coverage = readiness.spellCoverage || {}
  const nodeCount = firstNumber(source.nodeCount, asArray(source.nodes).length)
  const templateCount = sourceCount(talentTemplates)
  const blockers = asArray(readiness.blockers).concat(asArray(source.errors))
  const simcReady = readiness.simcReady === true
  const spellReady = readiness.spellReady === true
  const treeReady = readiness.treeReady !== false
  const hasNodes = nodeCount > 0
  const hasReadiness = Object.keys(readiness).length > 0
  let status = 'source_reference'

  if (!hasNodes && !hasReadiness && !blockers.length) status = 'source_reference'
  else if (!hasNodes && blockers.length) status = 'blocked'
  else if (!treeReady || !simcReady) status = 'blocked'
  else if (!spellReady || blockers.length || source.dataStatus === 'blocked') status = 'partial'
  else status = 'verified'

  const icon = firstTalentIcon(source)
  const metric = hasNodes ? `${nodeCount} 节点` : '待读取'
  const spellMetric = coverage.total
    ? `法术覆盖 ${formatCount(coverage.covered, coverage.total)}`
    : '覆盖待读取'

  return {
    key: 'talents',
    title: '天赋',
    status,
    statusLabel: labelForStatus(status),
    statusClass: statusClass(status),
    metric,
    desc: simcReady ? `可供 SimC · ${spellMetric}` : firstNonEmpty(blockers[0], '等待完整天赋'),
    actionLabel: '看天赋',
    iconUrl: icon.iconUrl,
    iconFallback: icon.fallbackText,
    templateCount,
    simcReady,
    blockers,
    evidence: [
      { label: '天赋状态', value: evidenceValueLabel(firstNonEmpty(source.talentStatus, source.dataStatus, 'unknown')), status },
      { label: '节点覆盖', value: metric, status },
      { label: '法术覆盖', value: spellMetric, status: spellReady ? 'verified' : 'partial' },
      { label: '本地模板', value: `${templateCount} 个`, status: templateCount ? 'verified' : 'source_reference' },
      { label: '检查时间', value: checkedAtLabel((source.talentAuthority || {}).checkedAt), status: 'source_reference' }
    ]
  }
}

function buildGearState(gearPayload, gearTemplates) {
  const source = gearPayload || {}
  const readiness = source.readiness || {}
  const statSnapshot = source.statSnapshot || {}
  const missingRequiredSlots = asArray(readiness.missingRequiredSlots)
  const gearCounts = canonicalGearCounts(readiness, missingRequiredSlots)
  const selectedCount = gearCounts.selectedCount
  const simcReadyCount = gearCounts.simcReadyCount
  const requiredReadyCount = gearCounts.requiredCount
  const templateCount = sourceCount(gearTemplates)
  const catalogBlockers = asArray(source.catalogBlockers)
  const statBlockers = asArray(statSnapshot.blockers)
  const missingRequiredSlotLabels = missingRequiredSlots.map((slot) => missingSlotLabel(slot, source))
  const blockerSummary = missingSlotSummary(missingRequiredSlotLabels)
  const blockerDetail = missingSlotDetail(missingRequiredSlotLabels)
  const blockers = []
  if (missingRequiredSlots.length) {
    blockers.push(blockerSummary)
  }
  if (!selectedCount && source.dataStatus === 'blocked') blockers.push('装备读模型不可用')
  const complete = readiness.fullReady === true && missingRequiredSlots.length === 0 && requiredReadyCount > 0 && simcReadyCount >= requiredReadyCount
  let status = 'source_reference'

  if (blockers.length) status = 'blocked'
  else if (complete && source.catalogStatus === 'verified') status = 'verified'
  else if (complete) status = 'partial'
  else if (selectedCount || simcReadyCount) status = 'partial'
  else status = 'source_reference'

  const icon = firstGearIcon(source)
  const itemLevel = readiness.itemLevel && readiness.itemLevel.value ? readiness.itemLevel.value : ''
  const metric = gearCounts.metric
  const desc = status === 'blocked'
    ? firstNonEmpty(blockerSummary, blockers[0], '装备待读取')
    : `${itemLevel ? `装等 ${itemLevel} · ` : ''}${source.catalogStatus || 'catalog 待读取'}`

  return {
    key: 'gear',
    title: '装备',
    status,
    statusLabel: labelForStatus(status),
    statusClass: statusClass(status),
    metric,
    desc,
    actionLabel: '补装备',
    iconUrl: icon.iconUrl,
    iconFallback: icon.fallbackText,
    templateCount,
    missingRequiredSlots,
    missingRequiredSlotLabels,
    blockerSummary,
    blockerDetail,
    catalogBlockers,
    statBlockers,
    complete,
    evidence: [
      { label: '装备槽位', value: metric, status },
      { label: '缺口', value: missingRequiredSlots.length ? blockerDetail : '无', status: missingRequiredSlots.length ? 'blocked' : 'verified' },
      { label: '装备目录', value: evidenceValueLabel(firstNonEmpty(source.catalogStatus, 'unknown')), status: source.catalogStatus === 'verified' ? 'verified' : 'partial' },
      { label: '属性快照', value: evidenceValueLabel(firstNonEmpty(statSnapshot.statStatus, 'unknown')), status: statSnapshot.statStatus === 'verified' ? 'verified' : 'blocked' },
      { label: '本地模板', value: `${templateCount} 个`, status: templateCount ? 'verified' : 'source_reference' },
      { label: '检查时间', value: checkedAtLabel(source.checkedAt || source.catalogCheckedAt), status: 'source_reference' }
    ]
  }
}

function buildSimcState(talentState, gearState) {
  if (talentState.status === 'source_reference' && gearState.status === 'source_reference') {
    return {
      key: 'simc',
      title: 'SimC',
      status: 'source_reference',
      statusLabel: labelForStatus('source_reference'),
      statusClass: statusClass('source_reference'),
      metric: '待证据',
      desc: '等待天赋与装备输入',
      actionLabel: '看证据',
      iconUrl: '',
      iconFallback: 'Sim'
    }
  }
  const talentReady = talentState.status !== 'blocked' && talentState.simcReady === true
  const gearReady = gearState.complete === true
  let status = 'blocked'
  let desc = '先补齐天赋与装备输入'
  if (talentReady && gearReady) {
    status = 'ready_to_simulate'
    desc = '可带入现有 SimC 页面校验'
  } else if (talentReady || gearReady) {
    status = 'partial'
    desc = talentReady ? '装备仍需补齐' : '天赋仍需补齐'
  }
  return {
    key: 'simc',
    title: 'SimC',
    status,
    statusLabel: labelForStatus(status),
    statusClass: statusClass(status),
    metric: status === 'ready_to_simulate' ? '可提交' : '待补齐',
    desc,
    actionLabel: status === 'ready_to_simulate' ? '去校验' : '看阻断',
    iconUrl: '',
    iconFallback: 'Sim'
  }
}

function buildChickenState(talentState, gearState) {
  const hasEvidence = talentState.status !== 'source_reference' || gearState.status !== 'source_reference'
  const status = hasEvidence ? 'partial' : 'source_reference'
  return {
    key: 'chickenbro',
    title: '队长',
    status,
    statusLabel: status === 'partial' ? '可解释证据' : labelForStatus(status),
    statusClass: statusClass(status),
    metric: hasEvidence ? '限证据' : '待证据',
    desc: hasEvidence ? '解释阻断与来源，不替代结论' : '等待天赋或装备证据',
    actionLabel: '追问',
    iconUrl: '',
    iconFallback: '队'
  }
}

function primaryBlockers(talentState, gearState) {
  const blockers = []
  if (gearState.missingRequiredSlots.length) {
    blockers.push({
      id: 'gear-missing-slots',
      type: 'gear',
      title: gearState.blockerSummary || gearState.desc,
      desc: gearState.blockerDetail ? `缺口：${gearState.blockerDetail}` : '装备不完整时只展示阻断和下一步，不输出强结论。',
      actionKey: 'gear',
      actionLabel: '去补装备',
      status: 'blocked',
      statusClass: statusClass('blocked')
    })
  }
  if (talentState.status === 'blocked') {
    blockers.push({
      id: 'talent-blocked',
      type: 'talents',
      title: firstNonEmpty(talentState.blockers[0], '天赋不可编码'),
      desc: '需要先补齐天赋树或编码证据。',
      actionKey: 'talents',
      actionLabel: '去看天赋',
      status: 'blocked',
      statusClass: statusClass('blocked')
    })
  }
  if (!blockers.length && talentState.status === 'partial') {
    blockers.push({
      id: 'talent-partial',
      type: 'talents',
      title: firstNonEmpty(talentState.blockers[0], '天赋描述证据不完整'),
      desc: '可作为构筑输入，但描述、来源或审计仍需展开查看。',
      actionKey: 'evidence',
      actionLabel: '展开证据',
      status: 'partial',
      statusClass: statusClass('partial')
    })
  }
  if (!blockers.length && gearState.catalogBlockers.length) {
    blockers.push({
      id: 'gear-catalog-partial',
      type: 'gear',
      title: gearState.catalogBlockers[0],
      desc: '装备目录仍是部分可信，只能作为参考继续补齐。',
      actionKey: 'evidence',
      actionLabel: '展开证据',
      status: 'partial',
      statusClass: statusClass('partial')
    })
  }
  return blockers.slice(0, 2)
}

function verdictSummaryForState(state, primaryBlocker, talentState, gearState) {
  if (state === 'ready_to_simulate') return '输入完整，可进入现有 SimC 页面做同 profile 校验。'
  if (state === 'blocked') {
    if (gearState.status === 'blocked') return '缺少核心装备，无法生成有效模拟结果。补齐后即可校验。'
    if (talentState.status === 'blocked') return '天赋输入未通过编码校验，补齐后再进入模拟。'
    return firstNonEmpty(primaryBlocker && primaryBlocker.desc, '缺少关键输入，先处理阻断项。')
  }
  if (state === 'stale') return '证据时间过旧，刷新后再提交模拟或解释结论。'
  if (state === 'source_reference') return '当前只有来源参考，不能输出模拟结论或评分。'
  return '已有部分证据，可展开查看覆盖率和缺口。'
}

function buildWorkbenchState(input) {
  const options = input || {}
  const talentsPayload = options.talentsPayload || {}
  const gearPayload = options.gearPayload || {}
  const talentState = buildTalentState(talentsPayload, options.talentTemplates)
  const gearState = buildGearState(gearPayload, options.gearTemplates)
  const simcState = buildSimcState(talentState, gearState)
  const chickenState = buildChickenState(talentState, gearState)
  const modules = [talentState, gearState, simcState, chickenState].map((item) => ({
    ...item,
    statusPillLabel: shortStatusLabel(item.status, item.statusLabel, item.key),
    dockDesc: moduleDockDesc(item)
  }))
  const blockers = primaryBlockers(talentState, gearState)
  const checkedAt = firstNonEmpty(gearPayload.checkedAt, gearPayload.catalogCheckedAt, (talentsPayload.talentAuthority || {}).checkedAt)
  const stale = isOlderThan(checkedAt, options.now, 14)
  let state = 'partial'

  if (blockers.some((item) => item.status === 'blocked') || talentState.status === 'blocked' || gearState.status === 'blocked') {
    state = 'blocked'
  } else if (stale) {
    state = 'stale'
  } else if (simcState.status === 'ready_to_simulate') {
    state = 'ready_to_simulate'
  } else if (modules.every((item) => item.status === 'source_reference')) {
    state = 'source_reference'
  }

  const primaryAction = (() => {
    if (state === 'ready_to_simulate') return { key: 'simc', label: '去 SimC 校验', desc: '使用现有模拟页面提交' }
    if (gearState.status === 'blocked') return { key: 'gear', label: '补齐装备', desc: gearState.desc }
    if (talentState.status === 'blocked') return { key: 'talents', label: '补齐天赋', desc: firstNonEmpty(talentState.blockers[0], '完善天赋输入') }
    return { key: 'evidence', label: state === 'stale' ? '刷新证据' : '展开证据', desc: blockers[0] ? blockers[0].title : '查看来源与覆盖率' }
  })()

  const headline = (() => {
    if (state === 'ready_to_simulate') return '可提交模拟'
    if (state === 'blocked') return '暂不可模拟'
    if (state === 'stale') return '证据需刷新'
    if (state === 'source_reference') return '仅作来源参考'
    return '部分可用'
  })()

  const evidenceRows = [
    ...talentState.evidence,
    ...gearState.evidence,
    { label: '队长规则', value: '只解释证据和阻断', status: 'source_reference' }
  ].map((row, index) => ({
    ...row,
    key: `${cleanText(row.label) || 'evidence'}-${index}`,
    labelInitial: cleanText(row.label).slice(0, 1) || '证',
    statusLabel: labelForStatus(row.status),
    statusClass: statusClass(row.status)
  }))
  const evidencePreviewRows = [
    {
      label: '天赋构筑参考',
      value: talentState.simcReady ? firstNonEmpty(talentState.desc, talentState.metric) : firstNonEmpty(talentState.blockers[0], talentState.desc),
      status: talentState.status
    },
    {
      label: '装备配置参考',
      value: gearState.status === 'blocked' ? firstNonEmpty(gearState.blockerSummary, gearState.desc) : firstNonEmpty(gearState.desc, gearState.metric),
      status: gearState.status
    },
    {
      label: '模拟设定说明',
      value: simcState.status === 'ready_to_simulate' ? '可进入 SimC 做同 profile 校验' : firstNonEmpty(simcState.desc, '等待输入完整'),
      status: simcState.status
    },
    {
      label: '队长条件说明',
      value: chickenState.status === 'source_reference' ? '只解释证据和阻断' : firstNonEmpty(chickenState.desc, '等待证据上下文'),
      status: chickenState.status
    }
  ].map((row, index) => ({
    ...row,
    key: `preview-${cleanText(row.label) || 'evidence'}-${index}`,
    labelInitial: cleanText(row.label).slice(0, 1) || '证',
    statusLabel: labelForStatus(row.status),
    statusClass: statusClass(row.status)
  }))
  const talentTemplateCount = talentState.templateCount || 0
  const gearTemplateCount = gearState.templateCount || 0
  const primaryBlocker = blockers[0] || {
    label: state === 'ready_to_simulate' ? '检查项' : '关注项',
    title: state === 'ready_to_simulate' ? '输入完整' : primaryAction.desc,
    desc: state === 'ready_to_simulate' ? '可进入现有 SimC 页面做确定性校验。' : '展开证据查看来源、覆盖率和阻断项。',
    statusClass: statusClass(state)
  }
  const primaryBlockerLabel = primaryBlocker.label || '主阻断'
  const summary = verdictSummaryForState(state, primaryBlocker, talentState, gearState)

  return {
    state,
    stateLabel: labelForStatus(state),
    stateClass: statusClass(state),
    headline,
    summary,
    primaryAction,
    primaryBlockerLabel,
    primaryBlockerTitle: primaryBlocker.title,
    primaryBlockerDesc: primaryBlocker.desc,
    blockers,
    secondaryBlockers: blockers.slice(1),
    moduleCards: modules,
    identityIcons: realIdentityIcons(talentState, gearState),
    evidencePreviewRows,
    evidenceRows,
    canShowStrongResult: false,
    templateSummary: {
      talentCount: talentTemplateCount,
      gearCount: gearTemplateCount,
      totalCount: talentTemplateCount + gearTemplateCount,
      status: talentTemplateCount || gearTemplateCount ? 'verified' : 'source_reference',
      statusLabel: talentTemplateCount || gearTemplateCount ? '已有模板' : '暂无模板',
      statusClass: statusClass(talentTemplateCount || gearTemplateCount ? 'verified' : 'source_reference')
    },
    checkedAt: checkedAtLabel(checkedAt),
    evidenceUpdatedAt: checkedAtLabel(checkedAt),
    selectedSpecLabel: selectedSpecLabel(options.selectedSpec),
    identityDesc: '汇总天赋、装备、SimC 与队长证据',
    identitySignal: state === 'ready_to_simulate'
      ? '已具备进入 SimC 校验的输入条件'
      : state === 'blocked'
        ? '阻断原因在下方结论区处理'
        : '展开证据查看来源与覆盖率',
    specMonogram: specMonogram(options.selectedSpec),
    specIconUrl: selectedSpecIconUrl(options.selectedSpec),
    selectedHeroLabel: selectedHeroLabel(options.selectedSpec, talentsPayload),
    selectedScenarioLabel: selectedScenarioLabel(options.scenarioKey)
  }
}

module.exports = {
  buildWorkbenchState,
  scenarioOptions,
  statusMeta
}
