const STATUS_LABELS = {
  ready_to_simulate: '可提交模拟',
  verified: '可用',
  blocked: '阻断',
  partial: '部分可用',
  stale: '需刷新',
  source_reference: '来源参考',
  unknown: '未知'
}

const STATUS_GLYPHS = {
  ready_to_simulate: 'OK',
  verified: 'OK',
  blocked: '!',
  partial: '!',
  stale: '刷',
  source_reference: '源',
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

function moduleCardStatus(card) {
  return normalizeStatus(card && card.status)
}

function normalizeModuleCards(cards) {
  return normalizeArray(cards).map((card, index) => {
    const status = moduleCardStatus(card)
    return {
      key: cleanText(card.key, `module-${index}`),
      title: cleanText(card.title, '模块'),
      metric: cleanText(card.metric, '待读取'),
      meta: cleanText(card.dockDesc || card.desc || card.statusPillLabel || card.actionLabel),
      status,
      statusLabel: statusLabel(status, card.statusPillLabel || card.statusLabel),
      statusGlyph: statusGlyph(status, card.statusGlyph),
      iconSrc: cleanText(card.iconUrl || card.iconSrc),
      iconText: cleanText(card.iconFallback || card.iconText || card.title, '模').slice(0, 2),
      disabled: Boolean(card.disabled)
    }
  })
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

function normalizeBlockers(blockers) {
  return normalizeArray(blockers).slice(0, 2).map((blocker, index) => {
    const status = normalizeStatus(blocker.status || 'blocked')
    return {
      id: cleanText(blocker.id, `blocker-${index}`),
      title: cleanText(blocker.title, '缺少输入'),
      desc: cleanText(blocker.desc, '补齐后可继续校验。'),
      actionKey: cleanText(blocker.actionKey),
      actionLabel: cleanText(blocker.actionLabel, '去处理'),
      status
    }
  })
}

function buildState(data) {
  const status = normalizeStatus(data.state)
  const moduleCards = normalizeModuleCards(data.moduleCards)
  const expandedRows = normalizeEvidenceRows(data.evidenceRows)
  const previewRows = normalizeEvidenceRows(data.evidencePreviewRows).length
    ? normalizeEvidenceRows(data.evidencePreviewRows)
    : expandedRows.slice(0, 3)
  const blockers = normalizeBlockers(data.secondaryBlockers)
  const action = data.primaryAction || {}
  return {
    rootClass: `state-${status}${data.evidenceExpanded ? ' is-evidence-expanded' : ''}`,
    normalizedStatus: status,
    normalizedStateLabel: statusLabel(status, data.stateLabel),
    normalizedStateGlyph: statusGlyph(status, data.stateGlyph),
    normalizedModuleCards: moduleCards,
    normalizedEvidenceRows: data.evidenceExpanded ? expandedRows : previewRows,
    normalizedEvidenceSummary: data.evidenceExpanded ? `${expandedRows.length} 条证据` : `${previewRows.length}/${expandedRows.length || previewRows.length} 条证据`,
    normalizedSecondaryBlockers: blockers,
    normalizedPrimaryAction: {
      key: cleanText(action.key || action.actionKey),
      label: cleanText(action.label, status === 'ready_to_simulate' ? '去 SimC 校验' : '继续补齐'),
      tone: status === 'blocked' ? 'danger' : status === 'ready_to_simulate' ? 'primary' : 'secondary'
    }
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
    selectedSpecLabel: {
      type: String,
      value: '当前专精'
    },
    selectedHeroLabel: {
      type: String,
      value: '英雄天赋待选'
    },
    selectedScenarioLabel: {
      type: String,
      value: '单体'
    },
    identitySignal: {
      type: String,
      value: ''
    },
    evidenceUpdatedAt: {
      type: String,
      value: ''
    },
    specIconUrl: {
      type: String,
      value: ''
    },
    specMonogram: {
      type: String,
      value: '专'
    },
    classLabel: {
      type: String,
      value: '职业'
    },
    specLabel: {
      type: String,
      value: '专精'
    },
    scenarioOptions: {
      type: Array,
      value: []
    },
    scenarioIndex: {
      type: Number,
      value: 0
    },
    headline: {
      type: String,
      value: '等待证据'
    },
    primaryBlockerLabel: {
      type: String,
      value: '检查项'
    },
    primaryBlockerTitle: {
      type: String,
      value: '待读取'
    },
    summary: {
      type: String,
      value: '读取天赋和装备后给出下一步。'
    },
    secondaryBlockers: {
      type: Array,
      value: []
    },
    primaryAction: {
      type: Object,
      value: {}
    },
    moduleCards: {
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
    templateSourceLabel: {
      type: String,
      value: '本地模板'
    },
    talentTemplateCount: {
      type: Number,
      value: 0
    },
    gearTemplateCount: {
      type: Number,
      value: 0
    },
    heroMaterialSrc: {
      type: String,
      value: ''
    },
    verdictMaterialSrc: {
      type: String,
      value: ''
    },
    moduleMaterialSrc: {
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
    'state, stateLabel, stateGlyph, moduleCards, evidenceRows, evidencePreviewRows, evidenceExpanded, secondaryBlockers, primaryAction': function updateDerivedState() {
      this.setData(buildState(this.data))
    }
  },
  lifetimes: {
    attached() {
      this.setData(buildState(this.data))
    }
  },
  methods: {
    handlePrimaryAction() {
      this.triggerEvent('primaryaction', this.data.normalizedPrimaryAction)
    },
    handleBlockerAction(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('blockeraction', {
        key: dataset.key || '',
        id: dataset.id || ''
      })
    },
    handleModuleTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('moduletap', {
        key: dataset.key || '',
        detail: event.detail || {}
      })
    },
    handleEvidenceToggle() {
      this.triggerEvent('evidencetoggle', {
        expanded: !this.data.evidenceExpanded
      })
    },
    handleScenarioTap(event) {
      const dataset = event.currentTarget.dataset || {}
      this.triggerEvent('scenariochange', {
        index: Number(dataset.index || 0),
        key: dataset.key || ''
      })
    },
    handleClassTap() {
      this.triggerEvent('classchange')
    },
    handleSpecTap() {
      this.triggerEvent('specchange')
    }
  }
})
