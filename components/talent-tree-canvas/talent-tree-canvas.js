const STATUS_LABELS = {
  ready_to_simulate: '可保存',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  loading: '读取中',
  unknown: '未知'
}

const STATUS_GLYPHS = {
  ready_to_simulate: 'OK',
  verified: 'OK',
  blocked: '!',
  partial: '~',
  stale: '刷',
  source_reference: '源',
  loading: '读',
  unknown: '?'
}

function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  return text || fallback
}

function normalizeStatus(value) {
  const status = cleanText(value, 'source_reference')
  if (status === 'ready_to_simulate') return status
  if (status === 'verified') return status
  if (status === 'blocked') return status
  if (status === 'partial') return status
  if (status === 'stale') return status
  if (status === 'loading') return status
  if (status === 'source_reference') return status
  return 'source_reference'
}

function statusLabel(status, fallback) {
  return cleanText(fallback, STATUS_LABELS[status] || STATUS_LABELS.source_reference)
}

function statusGlyph(status, fallback) {
  return cleanText(fallback, STATUS_GLYPHS[status] || STATUS_GLYPHS.source_reference)
}

function normalizeArray(value) {
  return Array.isArray(value) ? value.filter(Boolean) : []
}

function clampPercent(value, fallback) {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.max(0, Math.min(100, number))
}

function normalizeShape(value) {
  const shape = cleanText(value, 'passive')
  if (shape === 'active') return 'active'
  if (shape === 'choice') return 'choice'
  if (shape === 'hero') return 'hero'
  return 'passive'
}

function normalizeNode(node, index) {
  const status = normalizeStatus(node.status || node.state)
  const shape = normalizeShape(node.shape)
  const x = clampPercent(node.x == null ? node.left : node.x, 12 + (index % 4) * 24)
  const y = clampPercent(node.y == null ? node.top : node.y, 12 + Math.floor(index / 4) * 18)
  const rank = Number(node.rank || node.selectedRank || 0)
  const maxRank = Number(node.maxRank || node.ranks || 1)
  const title = cleanText(node.title || node.name, '天赋节点')
  return {
    id: cleanText(node.id || node.key, `node-${index}`),
    title,
    shortTitle: cleanText(node.shortTitle || node.iconText || title, '天').slice(0, 2),
    desc: cleanText(node.desc || node.reason || node.lockReason),
    status,
    statusLabel: statusLabel(status, node.statusLabel),
    shape,
    iconSrc: cleanText(node.iconSrc || node.iconUrl),
    iconName: cleanText(node.iconName),
    fallbackText: cleanText(node.fallbackText || node.iconText || title, '天').slice(0, 2),
    rank: Number.isFinite(rank) ? Math.max(0, rank) : 0,
    maxRank: Number.isFinite(maxRank) ? Math.max(1, maxRank) : 1,
    choiceGroup: cleanText(node.choiceGroup),
    treeKey: cleanText(node.treeKey),
    isGranted: Boolean(node.granted || node.isGranted),
    isSelected: Boolean(node.selected || node.isSelected || rank > 0),
    isLocked: status === 'blocked' || Boolean(node.locked),
    style: `left:${x}%;top:${y}%;`
  }
}

function normalizeLink(link, index) {
  const status = normalizeStatus(link.status || link.state)
  const x1 = clampPercent(link.x1, 0)
  const y1 = clampPercent(link.y1, 0)
  const x2 = clampPercent(link.x2, 0)
  const y2 = clampPercent(link.y2, 0)
  const dx = x2 - x1
  const dy = y2 - y1
  const length = Math.sqrt(dx * dx + dy * dy)
  const angle = Math.atan2(dy, dx) * 180 / Math.PI
  return {
    id: cleanText(link.id || link.key, `link-${index}`),
    status,
    style: `left:${x1}%;top:${y1}%;width:${length}%;transform:rotate(${angle}deg);`
  }
}

function normalizeTreeTab(tab, index) {
  const status = normalizeStatus(tab.status || tab.state)
  return {
    key: cleanText(tab.key || tab.id, `tree-${index}`),
    label: cleanText(tab.label || tab.title, '天赋树'),
    points: cleanText(tab.points || tab.pointText || tab.value, '0/0'),
    status,
    statusLabel: statusLabel(status, tab.statusLabel)
  }
}

function normalizeEvidenceRows(rows) {
  return normalizeArray(rows).map((row, index) => {
    const status = normalizeStatus(row.status || row.state)
    return {
      key: cleanText(row.key, `evidence-${index}`),
      iconText: cleanText(row.iconText || row.labelInitial, '证').slice(0, 2),
      label: cleanText(row.label, '证据'),
      value: cleanText(row.value, '待读取'),
      status,
      statusLabel: statusLabel(status, row.statusLabel)
    }
  })
}

function normalizeAction(action, fallbackLabel) {
  const data = action || {}
  return {
    key: cleanText(data.key || data.actionKey),
    label: cleanText(data.label, fallbackLabel),
    tone: cleanText(data.tone, 'secondary'),
    disabled: Boolean(data.disabled),
    loading: Boolean(data.loading)
  }
}

function buildState(data) {
  const state = normalizeStatus(data.state)
  const evidenceRows = normalizeEvidenceRows(data.evidenceRows)
  const previewRows = normalizeEvidenceRows(data.evidencePreviewRows).length
    ? normalizeEvidenceRows(data.evidencePreviewRows)
    : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${state}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedState: state,
    normalizedStateLabel: statusLabel(state, data.stateLabel),
    normalizedStateGlyph: statusGlyph(state, data.stateGlyph),
    normalizedTreeTabs: normalizeArray(data.treeTabs).map(normalizeTreeTab),
    normalizedNodes: normalizeArray(data.nodes).map(normalizeNode),
    normalizedLinks: normalizeArray(data.links).map(normalizeLink),
    normalizedEvidenceRows: data.evidenceExpanded ? evidenceRows : previewRows,
    normalizedEvidenceSummary: data.evidenceExpanded ? `${evidenceRows.length} 条证据` : `${previewRows.length}/${evidenceRows.length || previewRows.length} 条证据`,
    normalizedSaveAction: normalizeAction(data.saveAction, state === 'ready_to_simulate' ? '保存模板' : '暂不可保存'),
    normalizedImportAction: normalizeAction(data.importAction, '导入模板'),
    normalizedResetAction: normalizeAction(data.resetAction, '重置')
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: { type: String, value: 'source_reference' },
    stateLabel: { type: String, value: '' },
    stateGlyph: { type: String, value: '' },
    classLabel: { type: String, value: '职业' },
    specLabel: { type: String, value: '专精' },
    heroLabel: { type: String, value: '英雄天赋' },
    activeTreeKey: { type: String, value: 'class' },
    title: { type: String, value: '天赋树' },
    meta: { type: String, value: '' },
    pointSummary: { type: String, value: '' },
    blockerLabel: { type: String, value: '' },
    nodes: { type: Array, value: [] },
    links: { type: Array, value: [] },
    treeTabs: { type: Array, value: [] },
    evidenceRows: { type: Array, value: [] },
    evidencePreviewRows: { type: Array, value: [] },
    evidenceExpanded: { type: Boolean, value: false },
    saveAction: { type: Object, value: {} },
    importAction: { type: Object, value: {} },
    resetAction: { type: Object, value: {} },
    materialSrc: { type: String, value: '' },
    treeMaterialSrc: { type: String, value: '' }
  },
  data: buildState({}),
  observers: {
    'state, stateLabel, stateGlyph, treeTabs, nodes, links, evidenceRows, evidencePreviewRows, evidenceExpanded, saveAction, importAction, resetAction': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleTreeTabTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('treeswitch', { key: dataset.key || '' })
    },
    handleNodeTap(event) {
      const dataset = event.currentTarget.dataset || {}
      const detail = {
        nodeId: dataset.id || '',
        shape: dataset.shape || '',
        status: dataset.status || ''
      }
      this.triggerEvent('nodetap', detail)
      if (detail.shape === 'choice') this.triggerEvent('choicetap', detail)
    },
    handleSaveTap() {
      this.triggerEvent('savetap', this.data.normalizedSaveAction)
    },
    handleImportTap() {
      this.triggerEvent('importtap', this.data.normalizedImportAction)
    },
    handleResetTap() {
      this.triggerEvent('resettap', this.data.normalizedResetAction)
    },
    handleEvidenceToggle(event) {
      this.triggerEvent('evidencetoggle', event.detail || {})
    },
    handleViewportTap() {
      this.triggerEvent('viewportchange', {
        activeTreeKey: this.data.activeTreeKey
      })
    }
  }
})
