const STATUS_LABELS = {
  ready_to_simulate: '可提交模拟',
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
  partial: '!',
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

function normalizeChip(chip, index) {
  return {
    key: cleanText(chip.key || chip.label, `chip-${index}`),
    label: cleanText(chip.label, '指标'),
    value: cleanText(chip.value, '待读取')
  }
}

function normalizeSwitcherOptions(options) {
  return normalizeArray(options).map((item, index) => ({
    key: cleanText(item.key || item.id || item.value, `option-${index}`),
    label: cleanText(item.label || item.title || item.name, '选项'),
    status: normalizeStatus(item.status || item.state)
  }))
}

function normalizeModuleCard(card, index) {
  const status = normalizeStatus(card.status || card.state)
  return {
    key: cleanText(card.key, `module-${index}`),
    title: cleanText(card.title, '模块'),
    metric: cleanText(card.metric, '待读取'),
    meta: cleanText(card.meta || card.desc || card.statusLabel || card.actionLabel),
    status,
    statusLabel: statusLabel(status, card.statusLabel || card.statusPillLabel),
    statusGlyph: statusGlyph(status, card.statusGlyph),
    iconSrc: cleanText(card.iconUrl || card.iconSrc),
    iconText: cleanText(card.iconFallback || card.iconText || card.title, '模').slice(0, 2),
    disabled: Boolean(card.disabled)
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

function normalizeWorkbenchEntry(entry, status) {
  const action = entry.action || entry.primaryAction || {}
  return {
    title: cleanText(entry.title, '当前专精工作台'),
    desc: cleanText(entry.desc || entry.readinessText, '读取天赋、装备与模板证据后给出下一步。'),
    meta: cleanText(entry.meta || entry.blockerLabel, '缺证据时只给补齐动作'),
    status,
    statusLabel: statusLabel(status, entry.statusLabel),
    statusGlyph: statusGlyph(status, entry.statusGlyph),
    actionLabel: cleanText(entry.actionLabel || action.label, '进入工作台'),
    facts: normalizeArray(entry.facts).map(normalizeChip).slice(0, 3)
  }
}

function buildState(data) {
  const status = normalizeStatus(data.state)
  const workflowCards = normalizeArray(data.workflowCards).map(normalizeModuleCard)
  const evidenceRows = normalizeEvidenceRows(data.evidenceRows)
  const previewRows = normalizeEvidenceRows(data.evidencePreviewRows).length
    ? normalizeEvidenceRows(data.evidencePreviewRows)
    : evidenceRows.slice(0, 3)
  return {
    rootClass: `state-${status}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedStatus: status,
    normalizedStateLabel: statusLabel(status, data.stateLabel),
    normalizedStateGlyph: statusGlyph(status, data.stateGlyph),
    normalizedClassOptions: normalizeSwitcherOptions(data.classOptions),
    normalizedSpecOptions: normalizeSwitcherOptions(data.specOptions),
    normalizedHeroOptions: normalizeSwitcherOptions(data.heroOptions),
    normalizedOverviewChips: normalizeArray(data.overviewChips).map(normalizeChip),
    normalizedWorkbenchEntry: normalizeWorkbenchEntry(data.workbenchEntry || {}, status),
    normalizedWorkflowCards: workflowCards,
    normalizedEvidenceRows: data.evidenceExpanded ? evidenceRows : previewRows,
    normalizedEvidenceSummary: data.evidenceExpanded ? `${evidenceRows.length} 条证据` : `${previewRows.length}/${evidenceRows.length || previewRows.length} 条证据`
  }
}

Component({
  externalClasses: ['ext-class'],
  properties: {
    state: {
      type: String,
      value: 'source_reference'
    },
    stateLabel: {
      type: String,
      value: ''
    },
    stateGlyph: {
      type: String,
      value: ''
    },
    kicker: {
      type: String,
      value: '职业专精'
    },
    selectedClassLabel: {
      type: String,
      value: '法师'
    },
    selectedSpecLabel: {
      type: String,
      value: '冰霜'
    },
    selectedHeroLabel: {
      type: String,
      value: '英雄天赋待选'
    },
    currentSpecTitle: {
      type: String,
      value: '法师 · 冰霜'
    },
    currentSpecDesc: {
      type: String,
      value: '选择职业和专精后进入工作台。'
    },
    classKey: {
      type: String,
      value: ''
    },
    specKey: {
      type: String,
      value: ''
    },
    specIconUrl: {
      type: String,
      value: ''
    },
    specFallbackText: {
      type: String,
      value: '冰'
    },
    classOptions: {
      type: Array,
      value: []
    },
    specOptions: {
      type: Array,
      value: []
    },
    heroOptions: {
      type: Array,
      value: []
    },
    overviewChips: {
      type: Array,
      value: []
    },
    workbenchEntry: {
      type: Object,
      value: {}
    },
    workflowCards: {
      type: Array,
      value: []
    },
    evidenceRows: {
      type: Array,
      value: []
    },
    evidencePreviewRows: {
      type: Array,
      value: []
    },
    evidenceExpanded: {
      type: Boolean,
      value: false
    },
    materialSrc: {
      type: String,
      value: ''
    },
    consoleMaterialSrc: {
      type: String,
      value: ''
    },
    workbenchMaterialSrc: {
      type: String,
      value: ''
    },
    workflowMaterialSrc: {
      type: String,
      value: ''
    },
    evidenceMaterialSrc: {
      type: String,
      value: ''
    }
  },
  data: buildState({}),
  observers: {
    'state, stateLabel, stateGlyph, classOptions, specOptions, heroOptions, overviewChips, workbenchEntry, workflowCards, evidenceRows, evidencePreviewRows, evidenceExpanded': function updateState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handleWorkbenchTap() {
      this.triggerEvent('workbenchtap', {
        state: this.data.normalizedStatus,
        specKey: this.data.specKey
      })
    },
    handleClassTap(event) {
      this.triggerEvent('classchange', {
        key: event.currentTarget.dataset.key || '',
        label: event.currentTarget.dataset.label || ''
      })
    },
    handleSpecTap(event) {
      this.triggerEvent('specchange', {
        key: event.currentTarget.dataset.key || '',
        label: event.currentTarget.dataset.label || ''
      })
    },
    handleHeroTap(event) {
      this.triggerEvent('herochange', {
        key: event.currentTarget.dataset.key || '',
        label: event.currentTarget.dataset.label || ''
      })
    },
    handleWorkflowTap(event) {
      this.triggerEvent('entrytap', {
        key: event.currentTarget.dataset.key || ''
      })
    },
    handleEvidenceToggle(event) {
      this.triggerEvent('evidencetoggle', event.detail || {})
    },
    handleRefreshTap() {
      this.triggerEvent('refresh', {
        state: this.data.normalizedStatus
      })
    }
  }
})
